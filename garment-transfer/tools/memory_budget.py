#!/usr/bin/env python3
"""
memory_budget.py — MODELO DE TRIAGEM GROSSEIRA (screening model) de memória por candidata.
NÍVEL DE EVIDÊNCIA: ESTIMADO. NÃO é preciso o bastante para descartar candidatas perto do limite.

O que ele faz: soma o tamanho dos pesos por componente em diferentes precisões, acrescenta uma estimativa de ordem de
grandeza para ativações (dependente de tokens, hidden, nº de camadas residentes e implementação de atenção) e para o
VAE, e classifica cada candidata em três faixas com uma FAIXA DE INCERTEZA explícita:
  VRAM: FITS_RESIDENT — mesmo a banda alta cabe residente na VRAM utilizável (com margem de 30%)
        NEAR_LIMIT    — a faixa cruza o limite → só medição decide se cabe residente
        NEEDS_OFFLOAD — nem a banda baixa cabe residente → roda SÓ com offload/streaming (DynamicVRAM), mais lento;
                        NÃO significa inviável: QIE-2511 Q5 rodou na RTX 5070 do usuário com ~10–15 min/imagem a ~0.5 MP.
  RAM (caminho legado com cópia): CLEARLY_FITS / NEAR_LIMIT / CLEARLY_EXCEEDS; com mmap/DynamicVRAM não se aplica.
Calibração conhecida: FitDiT reporta ~19.5 GB fp16 em 1024×768 (paper) contra estimativa central ~10 GB e banda alta ~13 GB
aqui (dual DiT, caches de features da peça entre passos, encoders CLIP-L+bigG). O estimador SUBESTIMA sistematicamente.
Por isso: faixa de ativações [0.5×, 4×] e "CLEARLY_FITS" só quando a banda alta fica abaixo de 70% do disponível.
Use NEAR_LIMIT como "medir", nunca como "descartar"; use CLEARLY_EXCEEDS apenas quando até a banda baixa excede.

Uso:
    python tools/memory_budget.py --config tools/budget_configs.json
    python tools/memory_budget.py --params-b 20 --precision q5_k_m --text-encoder-params-b 7 --text-encoder-precision fp8 --latent-tokens 4096 --hidden 3072 --layers 60
"""
import argparse
import json

BYTES_PER_PARAM = {
    "fp32": 4.0, "bf16": 2.0, "fp16": 2.0,
    "fp8": 1.0, "fp8_e4m3fn": 1.0, "fp8_scaled": 1.06,
    "nvfp4": 0.56, "int4_svdq": 0.6,  # SVDQuant guarda low-rank em 16 bits: ~0.6 B/param efetivo
    "q8": 1.07, "q8_0": 1.07, "q6_k": 0.82, "q5_k_m": 0.69, "q5_k_s": 0.66, "q4_k_m": 0.58, "q4_k_s": 0.55, "q3_k_m": 0.45,
}

HW = {"vram_gb": 12.0, "ram_gb": 16.0,
      # reservas típicas; medir com inventory_windows.ps1. 600 MB é o EXTRA_RESERVED_VRAM do ComfyUI no Windows;
      # contexto CUDA + display somam mais 0.3–0.8 GB (variável).
      "vram_reserved_os_display_gb": 1.0, "ram_os_and_comfy_baseline_gb": 4.5}

ACT_UNCERTAINTY = (0.5, 4.0)  # fator multiplicativo aplicado às ativações (calibração: FitDiT subestimado ~2× no total)
FITS_SAFETY = 0.7  # "CLEARLY_FITS" só se o limite superior da faixa ficar abaixo de 70% do disponível (viés de subestimação conhecido)


def gb(x):
    return x / 2**30


def activations_bytes(hidden, latent_tokens, batch, cfg_batch, layers, resident_layers, attn_impl, n_heads=24):
    """Ordem de grandeza das ativações vivas durante um passo de denoise.

    - act_per_layer: tensores residuais + qkv + MLP (~6× hidden) por token, bf16.
    - resident_layers: quantas camadas têm ativações vivas simultaneamente (checkpointing/streaming → 2; execução
      padrão em inferência mantém poucas; com DynamicVRAM a estimativa de pesos residentes muda, não a de ativações).
      Se None, usa max(2, layers // 8): modelos mais profundos tendem a ter mais buffers vivos (KV de refs, skip).
    - atenção: SDPA/flash não materializa N×N; "naive" materializa tokens² por cabeça em fp16.
    """
    tok = latent_tokens * batch * cfg_batch
    act_per_layer = hidden * tok * 2 * 6
    if resident_layers is None:
        resident_layers = max(2, layers // 8)
    if attn_impl == "naive":
        attn = tok * tok * 2 * n_heads
    else:
        attn = hidden * tok * 2 * 2
    return act_per_layer * resident_layers + attn, resident_layers


def estimate(params_b, precision, te_params_b, te_precision, vae_mb, latent_tokens, hidden, layers,
             batch, cfg_batch, attn_impl, tiled_vae, load_path, resident_layers=None):
    w_model = params_b * 1e9 * BYTES_PER_PARAM[precision]
    w_te = te_params_b * 1e9 * BYTES_PER_PARAM[te_precision]
    w_vae = vae_mb * 2**20
    acts_c, resident = activations_bytes(hidden, latent_tokens, batch, cfg_batch, layers, resident_layers, attn_impl)
    acts_lo, acts_hi = acts_c * ACT_UNCERTAINTY[0], acts_c * ACT_UNCERTAINTY[1]
    vae_act = (latent_tokens * 64) * 3 * 4 * 8  # decode fp32 por pixel com buffers; tiles reduzem ~4×
    if tiled_vae:
        vae_act /= 4
    load_mult = {"mmap_direct": 1.05, "convert_on_load": 2.1, "gguf_dequant_on_gpu": 1.05}[load_path]
    ram_peak_load = (w_model + w_te) * load_mult

    vram_avail = HW["vram_gb"] - HW["vram_reserved_os_display_gb"]
    ram_avail = HW["ram_gb"] - HW["ram_os_and_comfy_baseline_gb"]

    def band(acts):
        return {
            "all_resident": gb(w_model + w_te + w_vae + acts),
            "sequential": gb(max(w_model + acts, w_te, w_vae + vae_act)),
        }
    lo, c, hi = band(acts_lo), band(acts_c), band(acts_hi)

    def classify(lo_v, hi_v, limit):
        if hi_v <= limit * FITS_SAFETY:
            return "FITS_RESIDENT"
        if lo_v > limit:
            return "NEEDS_OFFLOAD"
        return "NEAR_LIMIT"

    out = {
        "weights_gb": {"model": gb(w_model), "text_encoder": gb(w_te), "vae": gb(w_vae)},
        "activations_gb_est": {"low": gb(acts_lo), "central": gb(acts_c), "high": gb(acts_hi), "resident_layers_assumed": resident},
        "vae_activations_gb_est": gb(vae_act),
        "vram_all_resident_gb": {"low": lo["all_resident"], "central": c["all_resident"], "high": hi["all_resident"]},
        "vram_sequential_gb": {"low": lo["sequential"], "central": c["sequential"], "high": hi["sequential"]},
        "ram_peak_load_gb_est": gb(ram_peak_load),
        "ram_if_model_offloaded_gb_est": gb(w_model + w_te) + HW["ram_os_and_comfy_baseline_gb"],
        "screen_vram_all_resident": classify(lo["all_resident"], hi["all_resident"], vram_avail),
        "screen_vram_sequential": classify(lo["sequential"], hi["sequential"], vram_avail),
        "screen_ram_load_legacy_path": "CLEARLY_FITS" if gb(ram_peak_load) <= ram_avail else ("NEAR_LIMIT" if gb(ram_peak_load) <= ram_avail * 1.3 else "CLEARLY_EXCEEDS"),
        "note_ram": "Com DynamicVRAM/mmap (ComfyUI ≥ 0.16) os pesos são páginas file-backed e não entram no commit; a linha RAM vale para o caminho legado com cópia/conversão.",
        "assumptions": {
            "hw": HW, "bytes_per_param": {precision: BYTES_PER_PARAM[precision], te_precision: BYTES_PER_PARAM[te_precision]},
            "latent_tokens": latent_tokens, "hidden": hidden, "layers": layers, "batch": batch, "cfg_batch": cfg_batch,
            "attn_impl": attn_impl, "tiled_vae": tiled_vae, "load_path": load_path, "act_uncertainty": ACT_UNCERTAINTY,
            "status": "SCREENING MODEL — ESTIMADO. NEAR_LIMIT = medir; NEEDS_OFFLOAD = roda só com offload (tempo decide), nunca = inviável. Medir com tools/measure_run.py.",
        },
    }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="JSON com lista de candidatas")
    ap.add_argument("--params-b", type=float)
    ap.add_argument("--precision", default="bf16", choices=sorted(BYTES_PER_PARAM))
    ap.add_argument("--text-encoder-params-b", type=float, default=0.0)
    ap.add_argument("--text-encoder-precision", default="fp8", choices=sorted(BYTES_PER_PARAM))
    ap.add_argument("--vae-mb", type=float, default=320)
    ap.add_argument("--latent-tokens", type=int, default=4096, help="1024x1024 com patch 16px (VAE f8 + patch 2) = 4096")
    ap.add_argument("--hidden", type=int, default=3072)
    ap.add_argument("--layers", type=int, default=57)
    ap.add_argument("--resident-layers", type=int, default=None, help="camadas com ativações vivas simultaneamente (padrão: max(2, layers//8))")
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--cfg-batch", type=int, default=2)
    ap.add_argument("--attn", default="sdpa", choices=["sdpa", "naive"])
    ap.add_argument("--tiled-vae", action="store_true")
    ap.add_argument("--load-path", default="mmap_direct", choices=["mmap_direct", "convert_on_load", "gguf_dequant_on_gpu"])
    ap.add_argument("--markdown", action="store_true", help="imprime tabela Markdown (só com --config)")
    args = ap.parse_args()

    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfgs = json.load(f)
        rows = []
        for cc in cfgs:
            e = estimate(cc["params_b"], cc["precision"], cc.get("te_params_b", 0), cc.get("te_precision", "fp8"), cc.get("vae_mb", 320),
                         cc.get("latent_tokens", 4096), cc.get("hidden", 3072), cc.get("layers", 57), cc.get("batch", 1), cc.get("cfg_batch", 2),
                         cc.get("attn", "sdpa"), cc.get("tiled_vae", False), cc.get("load_path", "mmap_direct"), cc.get("resident_layers"))
            rows.append({"name": cc["name"], **{k: v for k, v in e.items() if k not in ("assumptions", "note_ram")}})
        if args.markdown:
            print("| Candidata (precisão) | Pesos modelo GB | TE GB | VRAM seq. GB [baixo–central–alto] | VRAM tudo residente GB [baixo–alto] | Triagem VRAM seq. | RAM load legado GB | Triagem RAM (legado) |")
            print("|---|---|---|---|---|---|---|---|")
            for r in rows:
                vs, va = r["vram_sequential_gb"], r["vram_all_resident_gb"]
                print(f"| {r['name']} | {r['weights_gb']['model']:.1f} | {r['weights_gb']['text_encoder']:.1f} | {vs['low']:.1f}–{vs['central']:.1f}–{vs['high']:.1f} | {va['low']:.1f}–{va['high']:.1f} | {r['screen_vram_sequential']} | {r['ram_peak_load_gb_est']:.1f} | {r['screen_ram_load_legacy_path']} |")
        else:
            print(json.dumps(rows, indent=1))
    else:
        if args.params_b is None:
            ap.error("--params-b ou --config")
        print(json.dumps(estimate(args.params_b, args.precision, args.text_encoder_params_b, args.text_encoder_precision, args.vae_mb,
                                  args.latent_tokens, args.hidden, args.layers, args.batch, args.cfg_batch, args.attn, args.tiled_vae,
                                  args.load_path, args.resident_layers), indent=1))


if __name__ == "__main__":
    main()
