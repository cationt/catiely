#!/usr/bin/env python3
"""Testes metamórficos do auditor de ocupação (sem GPU). Rodar: python tests/test_occupancy_audit.py
Cada teste constrói máscaras sintéticas consistentes e verifica o veredito ESPERADO do auditor — são controles do AUDITOR, não das rotas."""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "tools", "occupancy_audit.py")


def mk(d):
    H, W = 120, 80
    A = np.full((H, W, 3), 200, np.uint8); A[30:90, 25:55] = (220, 180, 160)
    FO = np.zeros((H, W), bool); FO[55:62, 20:60] = True; A[FO] = (210, 170, 150)
    BMIN = np.zeros((H, W), bool); BMIN[35:85, 27:53] = True; BMIN[FO] = False
    BMAXB = np.zeros((H, W), bool); BMAXB[30:90, 25:55] = True; BMAXB[FO] = False
    FS = np.zeros((H, W), bool); FS[28:92, 18:25] = True; FS[28:92, 55:62] = True; FS[FO] = False
    UNC = np.zeros((H, W), bool); UNC[70:85, 14:18] = True
    BC = BMAXB.copy(); PR = np.zeros((H, W), bool); PR[:20, :] = True
    G = np.zeros((H, W), bool); G[33:87, 24:56] = True; G[FO] = False
    m = dict(A=A, FO=FO, BMIN=BMIN, BMAXB=BMAXB, FS=FS, UNC=UNC, BC=BC, PR=PR, G=G)
    for n, a in m.items():
        Image.fromarray((a * 255).astype(np.uint8) if a.dtype == bool else a).save(os.path.join(d, n + ".png"))
    return m


def run(d, o_engine, g="G", extra=()):
    args = [sys.executable, TOOL, "--a", f"{d}/A.png", "--o-engine", o_engine, "--garment-mask", f"{d}/{g}.png",
            "--front-occluders", f"{d}/FO.png", "--band-min", f"{d}/BMIN.png", "--band-max-body", f"{d}/BMAXB.png",
            "--free-space", f"{d}/FS.png", "--uncertain", f"{d}/UNC.png", "--body-coverable", f"{d}/BC.png",
            "--protected", f"{d}/PR.png", "--contact-fringe-px", "2", "--tol", "4", *extra]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode in (0, 1, 3), r.stderr[-800:]
    return json.loads(r.stdout)["engine"]


def save(d, name, arr):
    Image.fromarray(arr).save(os.path.join(d, name)); return os.path.join(d, name)


def main():
    fails = 0
    with tempfile.TemporaryDirectory() as d:
        m = mk(d); A, G, FO, UNC, BMIN = m["A"], m["G"], m["FO"], m["UNC"], m["BMIN"]
        def expect(name, res, verdict, causes_any=()):
            nonlocal fails
            ok = res["verdict"] == verdict and all(any(c.startswith(x) for c in res["causes"]) for x in causes_any)
            print(("ok   " if ok else "FAIL ") + name, "→", res["verdict"], res["causes"][:4])
            if not ok: fails += 1
        # 1 perfeito (com ruído ±3 simulando VAE) → PASS
        rng = np.random.default_rng(0)
        Oe = A.copy(); Oe[G] = (30, 60, 200); Oe = np.clip(Oe.astype(int) + rng.integers(-3, 4, Oe.shape), 0, 255).astype(np.uint8)
        expect("perfeito+ruido_vae", run(d, save(d, "o1.png", Oe)), "PASS")
        # 2 O = A com G falso = BMIN → FAIL garment_not_created
        save(d, "GB.png", (BMIN * 255).astype(np.uint8))
        expect("identity_output_com_G_falso", run(d, save(d, "o2.png", A.copy()), "GB"), "FAIL", ["garment_not_created"])
        # 3 tecido sobre oclusor → FAIL bad_occlusion
        G3 = G | FO; O3 = A.copy(); O3[G3] = (30, 60, 200); save(d, "G3.png", (G3 * 255).astype(np.uint8))
        expect("tecido_sobre_oclusor", run(d, save(d, "o3.png", O3), "G3"), "FAIL", ["bad_occlusion"])
        # 4 ruído acima do piso em toda a imagem (corpo "reconstruído") → FAIL
        O4 = A.copy(); O4[G] = (30, 60, 200); O4 = np.clip(O4.astype(int) + rng.integers(-12, 13, O4.shape), 0, 255).astype(np.uint8)
        expect("ruido_acima_do_piso", run(d, save(d, "o4.png", O4)), "FAIL", ["background_drift_or_unauthorized_change", "body_reconstruction_probable"])
        # 5 mesmo ruído, mas com referência nula (--a-ref = A ruidosa igual) → PASS (isola piso do VAE)
        Aref = np.clip(A.astype(int) + rng.integers(-12, 13, A.shape), 0, 255).astype(np.uint8); O5 = Aref.copy(); O5[G] = (30, 60, 200)
        expect("ruido_com_referencia_nula", run(d, save(d, "o5.png", O5), extra=("--a-ref", save(d, "aref.png", Aref))), "PASS")
        # 6 envelope totalmente preenchido → não-FAIL por envelope (flag de anotação)
        allowed = m["BMIN"] | m["BMAXB"] | m["FS"] | m["UNC"]; O6 = A.copy(); O6[allowed] = (30, 60, 200); save(d, "G6.png", (allowed * 255).astype(np.uint8))
        r6 = run(d, save(d, "o6.png", O6), "G6"); ok6 = (r6["verdict"] == "INCONCLUSIVO" and not r6["causes"] and "envelope_too_tight_probable" in r6["inconclusive"])
        print(("ok   " if ok6 else "FAIL ") + "envelope_cheio_nao_e_falha_do_motor →", r6["verdict"], r6["causes"], r6.get("flags")); fails += int(not ok6)
        # 7 máscaras inconsistentes (BMIN ∩ FO) → INCONCLUSIVO:annotation_inconsistent
        bad = BMIN | FO; save(d, "BMINbad.png", (bad * 255).astype(np.uint8))
        r7 = subprocess.run([sys.executable, TOOL, "--a", f"{d}/A.png", "--o-engine", f"{d}/o1.png", "--garment-mask", f"{d}/G.png", "--front-occluders", f"{d}/FO.png", "--band-min", f"{d}/BMINbad.png", "--band-max-body", f"{d}/BMAXB.png", "--tol", "4"], capture_output=True, text=True)
        j7 = json.loads(r7.stdout)["engine"]; ok7 = ("annotation_inconsistent" in j7["inconclusive"]) and j7["verdict"] == "INCONCLUSIVO"
        print(("ok   " if ok7 else "FAIL ") + "mascaras_inconsistentes →", j7["verdict"], j7["inconclusive"]); fails += int(not ok7)
        # 8 pele descoberta alterada + invenção em UNCERTAIN → FAIL
        O8 = A.copy(); O8[G] = (30, 60, 200); O8[30:32, 26:54] = (120, 120, 120); O8[UNC] = (0, 255, 0)
        expect("pele_descoberta_alterada", run(d, save(d, "o8.png", O8)), "FAIL", ["body_reconstruction_probable", "unexplained_synthesis_in_uncertain"])
        # 9 membro duplicado (keypoints) → FAIL duplicate_limb
        json.dump({"hands": [[40, 58, 0.9]], "forearms": [[30, 58, 0.9]], "counts": {"hands": 1, "forearms": 1}}, open(f"{d}/kpA.json", "w"))
        json.dump({"hands": [[40, 58, 0.9]], "forearms": [[30, 58, 0.9]], "counts": {"hands": 2, "forearms": 1}}, open(f"{d}/kpE.json", "w"))
        expect("membro_duplicado", run(d, f"{d}/o1.png", extra=("--keypoints-a", f"{d}/kpA.json", "--keypoints-engine", f"{d}/kpE.json")), "FAIL", ["duplicate_limb"])
    print("\n" + ("TODOS OS TESTES PASSARAM" if fails == 0 else f"{fails} TESTE(S) FALHARAM"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
