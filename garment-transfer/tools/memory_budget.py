#!/usr/bin/env python3
"""
memory_budget.py — Estimador de orçamento de memória (VRAM/RAM) por candidata. NÍVEL DE EVIDÊNCIA: ESTIMADO.

Calcula o tamanho dos pesos por componente em diferentes precisões e compara com o hardware-alvo,
separando: pesos residentes, pico transitório de carregamento (cópia em RAM durante load/quantização),
ativações (estimativa grosseira por tokens de imagem), buffers de atenção, VAE em tiles ou não.

NÃO substitui medição (tools/measure_run.py). Serve para eliminar candidatas claramente inviáveis e para
planejar offload. Todas as hipóteses estão explícitas nos parâmetros.

Uso:
    python tools/memory_budget.py --config tools/budget_configs.json
    python tools/memory_budget.py --params-b 20 --precision q5_k_m --text-encoder-params-b 7 --text-encoder-precision q8 --vae-mb 300 --latent-tokens 4096 --hidden 3072 --layers 60
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
      # reservas típicas; medir com inventory_windows.ps1
      "vram_reserved_os_display_gb": 0.8, "ram_os_and_comfy_baseline_gb": 4.5}


def gb(x):
    return x / 2**30


def estimate(params_b, precision, te_params_b, te_precision, vae_mb, latent_tokens, hidden, layers,
             batch, cfg_batch, attn_impl, tiled_vae, load_path):
    w_model = params_b * 1e9 * BYTES_PER_PARAM[precision]
    w_te = te_params_b * 1e9 * BYTES_PER_PARAM[te_precision]
    w_vae = vae_mb * 2**20
    # Ativações grosseiras: por camada, hidden*tokens*batch*bf16, com fator 6 (qkv, mlp, residual) — ordem de grandeza.
    tok = latent_tokens * batch * cfg_batch
    act_layer = hidden * tok * 2 * 6
    # Atenção: SDPA/flash não materializa NxN; "naive" materializa tokens^2 por cabeça em fp16 (estimamos 1 cabeça de cada vez x heads~24)
    if attn_impl == "naive":
        attn = tok * tok * 2 * 24
    else:
        attn = hidden * tok * 2 * 2
    acts = act_layer * 2 + attn  # ~2 camadas residentes + atenção
    vae_act = (latent_tokens * 64) * 3 * 4 * 8  # decode fp32 por pixel com buffers; tiles reduzem ~4x
    if tiled_vae:
        vae_act /= 4
    # Pico de RAM de carregamento: safetensors via mmap ~ tamanho do arquivo (page cache) + cópias se converter precisão
    load_mult = {"mmap_direct": 1.05, "convert_on_load": 2.1, "gguf_dequant_on_gpu": 1.05}[load_path]
    ram_peak_load = (w_model + w_te) * load_mult
    out = {
        "weights_gb": {"model": gb(w_model), "text_encoder": gb(w_te), "vae": gb(w_vae)},
        "activations_gb_est": gb(acts),
        "vae_activations_gb_est": gb(vae_act),
        "vram_all_resident_gb_est": gb(w_model + w_te + w_vae + acts),
        "vram_sequential_gb_est": gb(max(w_model + acts, w_te, w_vae + vae_act)),
        "ram_peak_load_gb_est": gb(ram_peak_load),
        "ram_if_model_offloaded_gb_est": gb(w_model + w_te) + HW["ram_os_and_comfy_baseline_gb"],
    }
    vram_avail = HW["vram_gb"] - HW["vram_reserved_os_display_gb"]
    ram_avail = HW["ram_gb"] - HW["ram_os_and_comfy_baseline_gb"]
    out["fits_vram_all_resident"] = out["vram_all_resident_gb_est"] <= vram_avail
    out["fits_vram_sequential"] = out["vram_sequential_gb_est"] <= vram_avail
    out["fits_ram_load_without_pagefile"] = out["ram_peak_load_gb_est"] <= ram_avail
    out["fits_ram_full_offload_without_pagefile"] = out["ram_if_model_offloaded_gb_est"] <= HW["ram_gb"]
    out["assumptions"] = {
        "hw": HW, "bytes_per_param": {precision: BYTES_PER_PARAM[precision], te_precision: BYTES_PER_PARAM[te_precision]},
        "latent_tokens": latent_tokens, "hidden": hidden, "layers": layers, "batch": batch, "cfg_batch": cfg_batch,
        "attn_impl": attn_impl, "tiled_vae": tiled_vae, "load_path": load_path,
        "note": "ESTIMADO. Ativações são ordem de grandeza; medir com measure_run.py no hardware-alvo.",
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
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--cfg-batch", type=int, default=2)
    ap.add_argument("--attn", default="sdpa", choices=["sdpa", "naive"])
    ap.add_argument("--tiled-vae", action="store_true")
    ap.add_argument("--load-path", default="mmap_direct", choices=["mmap_direct", "convert_on_load", "gguf_dequant_on_gpu"])
    args = ap.parse_args()

    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfgs = json.load(f)
        rows = []
        for c in cfgs:
            e = estimate(c["params_b"], c["precision"], c.get("te_params_b", 0), c.get("te_precision", "fp8"), c.get("vae_mb", 320),
                         c.get("latent_tokens", 4096), c.get("hidden", 3072), c.get("layers", 57), c.get("batch", 1), c.get("cfg_batch", 2),
                         c.get("attn", "sdpa"), c.get("tiled_vae", False), c.get("load_path", "mmap_direct"))
            rows.append({"name": c["name"], **{k: v for k, v in e.items() if k != "assumptions"}})
        print(json.dumps(rows, indent=1))
    else:
        if args.params_b is None:
            ap.error("--params-b ou --config")
        print(json.dumps(estimate(args.params_b, args.precision, args.text_encoder_params_b, args.text_encoder_precision, args.vae_mb,
                                  args.latent_tokens, args.hidden, args.layers, args.batch, args.cfg_batch, args.attn, args.tiled_vae,
                                  args.load_path), indent=1))


if __name__ == "__main__":
    main()
