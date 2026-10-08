#!/usr/bin/env python3
"""Testes estáticos (CPU, sem torch, sem modelos) da preparação R1-EI. Rodar: python tests/test_r1ei_static.py"""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
R1 = os.path.join(ROOT, "tools", "r1ei")
sys.path.insert(0, HERE)
from _fixtures import Checker  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "tools"))
import freeze_check as fz  # noqa: E402


def main():
    c = Checker()
    man = json.load(open(os.path.join(R1, "r1ei_manifest.json"), encoding="utf-8"))
    # vendor byte-idêntico ao pin do upstream
    vsha = fz.sha256_file(os.path.join(R1, "vendor", "easy_insert_utils.py"))
    c.ok("vendor_utils_sha_igual_ao_pin", vsha == man["easy_insert"]["files_sha256"]["utils.py"] == "d84f0cbc0a85de804ad1bf65955d6ad0fd213a4b70f9ddc620f898fd54dd300f", vsha)
    c.ok("manifest_pins_presentes", all(man[k] for k in ("easy_insert", "lora", "base_model")) and len(man["lora"]["sha256"]) == 64 and man["easy_insert"]["upstream_defaults"]["num_inference_steps"] == 15 and man["easy_insert"]["upstream_defaults"]["guidance_scale"] == 4.0, "")
    c.ok("requirements_pinadas", all("==" in l for l in open(os.path.join(R1, "requirements-r1ei.txt")) if l.strip() and not l.startswith("#") and not l.startswith("psutil") and not l.startswith("pynvml")), "")
    with tempfile.TemporaryDirectory() as d:
        A = np.full((1600, 1200, 3), 190, np.uint8); A[300:1300, 300:900] = (210, 170, 150); Ap = os.path.join(d, "A.png"); Image.fromarray(A).save(Ap)
        B = np.full((1200, 900, 3), 240, np.uint8); B[200:1000, 150:750] = (30, 60, 200); Bp = os.path.join(d, "B.png"); Image.fromarray(B).save(Bp)
        # máscaras por bbox
        r = subprocess.run([sys.executable, os.path.join(R1, "make_masks.py"), "--image", Ap, "--bbox", "0.25,0.18,0.75,0.72", "--out", os.path.join(d, "A_m.png")], capture_output=True, text=True)
        m = Image.open(os.path.join(d, "A_m.png")); arr = np.asarray(m)
        c.ok("make_masks_bbox_grade_de_A", r.returncode == 0 and m.mode == "L" and m.size == (1200, 1600) and set(np.unique(arr)) <= {0, 255} and m.getbbox() == (300, 288, 900, 1152), (r.stdout.strip()[-80:], m.getbbox()))
        r = subprocess.run([sys.executable, os.path.join(R1, "make_masks.py"), "--image", Bp, "--bbox-px", "150,200,750,1000", "--out", os.path.join(d, "B_m.png")], capture_output=True, text=True)
        c.ok("make_masks_bbox_px", r.returncode == 0 and Image.open(os.path.join(d, "B_m.png")).getbbox() == (150, 200, 750, 1000), r.stdout.strip()[-80:])
        r = subprocess.run([sys.executable, os.path.join(R1, "make_masks.py"), "--image", Ap, "--bbox", "0.9,0.1,0.5,0.2", "--out", os.path.join(d, "bad.png")], capture_output=True, text=True)
        c.ok("make_masks_bbox_invalida_rejeitada", r.returncode != 0, r.stderr.strip()[-80:] or r.stdout.strip()[-80:])
        # modelo falso: estrutura de diretórios com tamanhos errados → dry-run deve reprovar os pins (exit 3)
        mdl = os.path.join(d, "model"); lora = os.path.join(d, "lora"); os.makedirs(lora)
        for rel in list(man["base_model"]["files_needed_by_runner"]) + man["base_model"]["small_files_needed"]:
            p = os.path.join(mdl, *rel.split("/")); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b"x")
        open(os.path.join(lora, man["lora"]["file"]), "wb").write(b"not-a-lora")
        base_cmd = [sys.executable, os.path.join(R1, "run_easy_insert.py"), "--a", Ap, "--b", Bp, "--insert-mask", os.path.join(d, "A_m.png"), "--ref-mask", os.path.join(d, "B_m.png"),
                    "--model-dir", mdl, "--lora-dir", lora, "--dry-run"]
        r = subprocess.run(base_cmd + ["--out", os.path.join(d, "o1.png")], capture_output=True, text=True)
        j = json.load(open(os.path.join(d, "o1.png.json")))
        c.ok("dry_run_pins_divergentes_exit3", r.returncode == 3 and j["verdict"].startswith("FAIL:pins") and j["pin_check"]["lora"]["status"] == "sha256_divergente", (r.returncode, j["verdict"], j["pin_check"]["lora"]["status"]))
        # pré-processamento upstream: entradas exatas gravadas (1024², buraco branco onde a máscara, referência sobre branco)
        inp = os.path.join(d, "o1_inputs")
        bg = Image.open(os.path.join(inp, "image1_background_masked_1024.png")); ref = Image.open(os.path.join(inp, "image2_reference_on_white_1024.png"))
        bga = np.asarray(bg); refa = np.asarray(ref)
        c.ok("preprocess_1024_quadrado", bg.size == (1024, 1024) and ref.size == (1024, 1024), (bg.size, ref.size))
        c.ok("preprocess_buraco_branco_e_contexto", (bga == 255).all(axis=2).mean() > 0.3 and (bga == 255).all(axis=2).mean() < 0.9 and (bga[5, 5] != 255).any(), round(float((bga == 255).all(axis=2).mean()), 3))
        c.ok("preprocess_referencia_sobre_branco", (refa == 255).all(axis=2).mean() > 0.05 and (np.abs(refa[512, 512].astype(int) - np.array([30, 60, 200])).max() <= 2), refa[512, 512].tolist())
        c.ok("preprocess_crop_box_1_2x", j["preprocess"]["crop_side_px"] == int(round(max(600, 864) * 1.2)), j["preprocess"])
        # paste_back round-trip (utils do upstream): colar o próprio crop GT devolve A idêntica
        sys.path.insert(0, os.path.join(R1, "vendor")); import easy_insert_utils as u  # noqa: E402
        Aim = Image.open(Ap).convert("RGB"); mk = Image.open(os.path.join(d, "A_m.png")).convert("L")
        bgi, gt, box, mc = u.process_source(Aim, mk, 1024)
        back = u.paste_back(gt, Aim, box, mc, feather=0)
        diff = np.abs(np.asarray(back).astype(int) - np.asarray(Aim).astype(int))
        # upstream reamostra o crop duas vezes (LANCZOS 1037→1024→1037): erro só DENTRO da máscara (fora, pixels de A intactos)
        outside = np.asarray(mk) == 0
        c.ok("paste_back_roundtrip_fora_da_mascara_identico", diff[outside].max() == 0 and diff.max() <= 8 and (diff > 0).mean() < 0.02, (int(diff[outside].max()), int(diff.max()), round(float((diff > 0).mean()), 4)))
        # máscara fora da grade de A → erro de uso
        wrong = os.path.join(d, "wrong.png"); Image.fromarray(np.zeros((100, 100), np.uint8) + 255).save(wrong)
        r = subprocess.run(base_cmd[:base_cmd.index("--insert-mask") + 1] + [wrong] + base_cmd[base_cmd.index("--insert-mask") + 2:] + ["--out", os.path.join(d, "o2.png")], capture_output=True, text=True)
        c.ok("mascara_fora_da_grade_rejeitada", r.returncode != 0 and "grade de A" in (r.stderr + r.stdout), (r.stderr + r.stdout).strip()[-100:])
        # vendor adulterado → recusa importar
        vend = os.path.join(d, "ei"); os.makedirs(vend); open(os.path.join(vend, "utils.py"), "w").write("def process_source(*a, **k): pass\n")
        r = subprocess.run(base_cmd + ["--easy-insert-dir", vend, "--out", os.path.join(d, "o3.png")], capture_output=True, text=True)
        c.ok("utils_divergente_recusado", r.returncode != 0 and "difere do pin" in (r.stderr + r.stdout), (r.stderr + r.stdout).strip()[-100:])
    return c.done("test_r1ei_static")


if __name__ == "__main__":
    sys.exit(main())
