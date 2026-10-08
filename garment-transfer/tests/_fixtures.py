"""Fixture sintética CONGELADA para os testes do harness do Prototype 0 (CPU, sem modelos).

Constrói, num diretório temporário: A, B, máscaras nomeadas, máscaras por elemento (incl. split must_cover/must_stay_visible), máscara da peça em B,
manifesto JSONL com sha256 REAIS, PREREG.md, g0_case_roles.json e FREEZE.json (via tools/freeze_proto0.py). Casos:
  synth_easy_01      EASY, occlusion ["none"], sem front_certain  (eixo D = NOT_APPLICABLE)
  synth_hard_01      HARD, hand_R front_certain, upper_arm_L split_by_garment_edge (com máscaras), torso behind_must_cover
  synth_hard_nosplit HARD como acima, mas o elemento split SEM máscaras congeladas (exige adjudicação humana cega)
  synth_core_a..d    réplicas de synth_hard_01 para completar os 6 casos core do gate sintético
  synth_ctrl_identity_01  controle (identity_output) — papel auditor_control
"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")
AUDIT = os.path.join(TOOLS, "occupancy_audit.py")
FIDELITY = os.path.join(TOOLS, "garment_fidelity_audit.py")
GATE = os.path.join(TOOLS, "g0_gate.py")
FREEZE = os.path.join(TOOLS, "freeze_proto0.py")
sys.path.insert(0, TOOLS)
import freeze_check as fz  # noqa: E402

H, W = 120, 80
GARMENT_RGB = (30, 60, 200)


def save_mask(path, m):
    Image.fromarray((m.astype(np.uint8) * 255)).save(path)


def save_rgb(path, a):
    Image.fromarray(np.asarray(a, dtype=np.uint8)).save(path)


def build_masks(with_occluder=True):
    A = np.full((H, W, 3), 200, np.uint8); A[30:90, 25:55] = (220, 180, 160)
    A[:20, :] = (90, 120, 160)  # faixa PROTECTED (rosto/fundo distante) com textura leve
    A[5:15, 10:70] = (140, 150, 170)
    FO = np.zeros((H, W), bool)
    if with_occluder:
        FO[55:62, 20:60] = True; A[FO] = (210, 170, 150)
    BMIN = np.zeros((H, W), bool); BMIN[35:85, 27:53] = True; BMIN &= ~FO
    BMAXB = np.zeros((H, W), bool); BMAXB[30:90, 25:55] = True; BMAXB &= ~FO
    FS = np.zeros((H, W), bool); FS[28:92, 18:25] = True; FS[28:92, 55:62] = True; FS &= ~FO
    UNC = np.zeros((H, W), bool); UNC[70:85, 14:18] = True
    BC = BMAXB.copy()
    PR = np.zeros((H, W), bool); PR[:20, :] = True
    # elemento split: upper_arm_L = bloco rows 33:60, cols 50:55; proximal (must_cover) rows 33:44; distal (visible) rows 48:60; zona rows 44:48
    EL_ARM = np.zeros((H, W), bool); EL_ARM[33:60, 50:55] = True; EL_ARM &= ~FO  # elemento não sobrepõe o oclusor frontal
    MC = np.zeros((H, W), bool); MC[33:44, 50:55] = True
    MV = np.zeros((H, W), bool); MV[48:60, 50:55] = True; MV &= ~FO  # parte visível não pode sobrepor o oclusor (regra própria)
    BMIN_split = BMIN & ~(MV | (EL_ARM & ~MC & ~MV))
    TORSO = BMIN.copy()
    G = np.zeros((H, W), bool); G[33:87, 24:56] = True; G &= ~FO
    G_split = G & ~MV & ~(EL_ARM & ~MC & ~MV)  # cobre must_cover, não cobre a parte visível nem a zona de fronteira
    B = np.full((H, W, 3), 230, np.uint8); BG = np.zeros((H, W), bool); BG[20:100, 20:60] = True; B[BG] = GARMENT_RGB
    return dict(A=A, B=B, BG=BG, FO=FO, BMIN=BMIN, BMIN_split=BMIN_split, BMAXB=BMAXB, FS=FS, UNC=UNC, BC=BC, PR=PR,
                EL_ARM=EL_ARM, MC=MC, MV=MV, TORSO=TORSO, G=G, G_split=G_split)


def src(rel, d):
    return {"source_type": "local_private", "local_path": rel, "license": "synthetic-generated", "redistributable_in_repo": False,
            "sha256": fz.sha256_file(os.path.join(d, rel)), "consent_adult_non_explicit": True}


def perfect_output(m, G=None, base=None):
    """saída 'perfeita': base (A, ou A_ref = nula da rota) com o tecido pintado em G."""
    O = (m["A"] if base is None else base).copy(); O[(m["G"] if G is None else G)] = GARMENT_RGB
    return O


def engine_output(m, aref, G=None, seed=0, extra_noise=1):
    """saída realista de motor: regiões não editadas ≈ nula da rota (A_ref) com ruído residual pequeno; tecido em G."""
    return noisy(perfect_output(m, G, base=aref), extra_noise, seed)


def noisy(a, amp, seed):
    rng = np.random.default_rng(seed)
    return np.clip(a.astype(int) + rng.integers(-amp, amp + 1, a.shape), 0, 255).astype(np.uint8)


ATTRS = [{"name": "category", "value": "t-shirt", "state": "observed", "expected_visible_in_O": "yes"},
         {"name": "sleeve_length", "value": "short", "state": "observed", "expected_visible_in_O": "yes"}]


def build_case_dir(d):
    """Cria todos os arquivos + manifesto + PREREG + roles + FREEZE em d. Retorna dict com caminhos e máscaras (hard e easy)."""
    hard = build_masks(True); easy = build_masks(False)
    files = {}
    def put(name, arr, kind):
        p = os.path.join(d, name); (save_mask if kind == "m" else save_rgb)(p, arr); files[name] = p; return name
    # hard
    for k in ("FO", "BMIN", "BMIN_split", "BMAXB", "FS", "UNC", "BC", "PR", "EL_ARM", "MC", "MV", "TORSO", "BG"):
        put(f"hard_{k}.png", hard[k], "m")
    put("hard_A.png", hard["A"], "r"); put("hard_B.png", hard["B"], "r")
    put("hard_EL_hand_R.png", hard["FO"], "m")
    # easy
    for k in ("BMIN", "BMAXB", "FS", "UNC", "BC", "PR", "TORSO", "BG"):
        put(f"easy_{k}.png", easy[k], "m")
    put("easy_A.png", easy["A"], "r"); put("easy_B.png", easy["B"], "r")

    def fa_hard(split_masks=True, bmin="hard_BMIN_split.png"):
        arm = {"element": "upper_arm_L", "relation": "split_by_garment_edge", "basis": "observed_in_A", "mask": src("hard_EL_ARM.png", d)}
        if split_masks:
            arm["split_must_cover_mask"] = src("hard_MC.png", d); arm["split_must_stay_visible_mask"] = src("hard_MV.png", d)
        return {"annotator": "synthetic", "freeze_tag": "synth-frozen-v1", "front_occluders_mask": src("hard_FO.png", d),
                "body_coverable_mask": src("hard_BC.png", d), "protected_mask": src("hard_PR.png", d),
                "plausible_occupancy_band": {"min_mask": src(bmin, d), "max_body_mask": src("hard_BMAXB.png", d)},
                "free_space_mask": src("hard_FS.png", d), "uncertain_occupancy_mask": src("hard_UNC.png", d), "contact_fringe_px": 2,
                "envelope_class": "E2_surface_plus_silhouette",
                "z_order": [{"element": "hand_R", "relation": "front_certain", "basis": "observed_in_A", "mask": src("hard_EL_hand_R.png", d)},
                            arm, {"element": "torso_front_skin", "relation": "behind_must_cover", "basis": "category_rule", "mask": src("hard_TORSO.png", d)}]}

    def fa_easy():
        return {"annotator": "synthetic", "freeze_tag": "synth-frozen-v1", "front_occluders_mask": None, "body_coverable_mask": src("easy_BC.png", d),
                "protected_mask": src("easy_PR.png", d),
                "plausible_occupancy_band": {"min_mask": src("easy_BMIN.png", d), "max_body_mask": src("easy_BMAXB.png", d)},
                "free_space_mask": src("easy_FS.png", d), "uncertain_occupancy_mask": src("easy_UNC.png", d), "contact_fringe_px": 2,
                "envelope_class": "E1_observed_surface",
                "z_order": [{"element": "torso_front_skin", "relation": "behind_must_cover", "basis": "category_rule", "mask": src("easy_TORSO.png", d)}]}

    def row(cid, level, occl, fa, kind, negctrl=None):
        r = {"case_id": cid, "split": "proto0", "level": level, "A": src(f"{kind}_A.png", d), "B": src(f"{kind}_B.png", d),
             "spec": {"mode": "add", "garments": [{"category": "top"}], "garment_of_category_present_in_A": False},
             "coverage": {"occlusion": occl, "operation": "add_over_skin"},
             "expected": {"garment_attributes": ATTRS, "frozen_annotation": fa, "b_garment_mask": src(f"{kind}_BG.png", d), "has_ground_truth": False},
             "provenance": {"person_group_id": f"p_{kind}"}}
        if negctrl:
            r["expected"]["negative_control"] = negctrl
        return r
    rows = [row("synth_easy_01", "EASY", ["none"], fa_easy(), "easy"),
            row("synth_hard_01", "HARD", ["arms_crossing"], fa_hard(True), "hard"),
            row("synth_hard_nosplit", "HARD", ["arms_crossing"], fa_hard(False), "hard"),
            row("synth_core_a", "MEDIUM", ["arms_crossing"], fa_hard(True), "hard"),
            row("synth_core_b", "HARD", ["arms_crossing"], fa_hard(True), "hard"),
            row("synth_core_c", "HARD", ["arms_crossing"], fa_hard(True), "hard"),
            row("synth_core_d", "HARD", ["arms_crossing"], fa_hard(True), "hard"),
            row("synth_ctrl_identity_01", "HARD", ["arms_crossing"], fa_hard(True), "hard", "identity_output"),
            row("synth_easy_badoccl", "EASY", ["furniture"], fa_easy(), "easy")]  # oclusão declarada sem front_certain: anotação contraditória
    manifest = os.path.join(d, "manifest.jsonl")
    with open(manifest, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    prereg = os.path.join(d, "PREREG.md")
    open(prereg, "w", encoding="utf-8").write("# PREREG sintético\ncore: synth_easy_01, synth_core_a, synth_hard_01, synth_core_b, synth_core_c, synth_core_d\n")
    roles = {"version": 1, "gate": "G0", "frozen_before_first_run": True, "core_cases": ["synth_easy_01", "synth_core_a", "synth_hard_01", "synth_core_b", "synth_core_c", "synth_core_d"],
             "core_rule": {"min_pass": 4, "of": 6, "levels_counted": ["EASY", "MEDIUM", "HARD"], "seeds": [1, 2, 3]},
             "progression": {"EASY->MEDIUM": {"cases": ["synth_easy_01"], "min_cases": 1, "min_seeds_axis_A": 2, "of_seeds": 3},
                             "MEDIUM->HARD": {"cases": ["synth_core_a"], "min_cases": 1, "min_seeds_axis_A": 2, "of_seeds": 3},
                             "HARD->EXTREME": {"cases": ["synth_hard_01", "synth_core_b", "synth_core_c", "synth_core_d"], "min_cases": 2, "min_seeds_axis_A": 2, "of_seeds": 3}},
             "roles": {"synth_easy_01": "gate_core", "synth_hard_01": "gate_core", "synth_core_a": "gate_core", "synth_core_b": "gate_core", "synth_core_c": "gate_core",
                       "synth_core_d": "gate_core", "synth_hard_nosplit": "replication", "synth_ctrl_identity_01": "auditor_control", "synth_easy_badoccl": "replication"}}
    roles_p = os.path.join(d, "g0_case_roles.json"); json.dump(roles, open(roles_p, "w"), indent=1)
    freeze = os.path.join(d, "FREEZE.json")
    r = subprocess.run([sys.executable, FREEZE, "--manifest", manifest, "--prereg", prereg, "--roles", roles_p, "--tag", "synth-frozen-v1",
                        "--out", freeze, "--data-root", d, "--allow-dirty", "--skip-validator"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    # keypoints (iguais em A e O′)
    kp = {"hands": [[40, 58, 0.9]], "forearms": [[30, 58, 0.9]], "counts": {"hands": 1, "forearms": 1}}
    json.dump(kp, open(os.path.join(d, "kpA.json"), "w")); json.dump(kp, open(os.path.join(d, "kpE.json"), "w"))
    kp2 = dict(kp, counts={"hands": 2, "forearms": 1}); json.dump(kp2, open(os.path.join(d, "kpE_dup.json"), "w"))
    # adjudicações genéricas (sem case_id/output_sha256): só servem para testar a REJEIÇÃO no perfil g0
    adj = {"blind": True, "evaluator_id": "ev1", "date": "2026-10-08", "catch_trials_passed": True, "answers": {"category": "yes", "sleeve_length": "yes", "split_edge:upper_arm_L": "yes"}}
    json.dump(adj, open(os.path.join(d, "adj_unbound.json"), "w"))
    return {"d": d, "hard": hard, "easy": easy, "manifest": manifest, "prereg": prereg, "roles": roles_p, "freeze": freeze, "files": files}


def run_audit(fx, case_id, o_engine, g_path, extra=(), profile="g0", a=None, with_occ=True, with_kp=True, a_ref=None, o_composed=None):
    d = fx["d"]; kind = "easy" if case_id.startswith("synth_easy") else "hard"
    args = [sys.executable, AUDIT, "--a", a or fx["files"][f"{kind}_A.png"], "--o-engine", o_engine, "--garment-mask", g_path, "--profile", profile,
            "--contact-fringe-px", "2"]
    if profile == "g0":
        args += ["--manifest", fx["manifest"], "--case-id", case_id, "--data-root", d, "--prereg", fx["prereg"], "--freeze", fx["freeze"], "--roles", fx["roles"], "--allow-dirty-freeze"]
    if a_ref:
        args += ["--a-ref", a_ref]
    if kind == "hard" and with_occ:
        args += ["--occluder-mask-engine", fx["files"]["hard_FO.png"]]
    if kind == "hard" and with_kp:
        args += ["--keypoints-a", os.path.join(d, "kpA.json"), "--keypoints-engine", os.path.join(d, "kpE.json")]
    if o_composed:
        args += ["--o-composed", o_composed]
    args += list(extra)
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode in (0, 1, 3), r.stderr[-1500:]
    try:
        return json.loads(r.stdout), r.returncode
    except json.JSONDecodeError:
        raise AssertionError(r.stdout[-1500:] + r.stderr[-1500:])


class Checker:
    def __init__(self):
        self.fails = 0; self.n = 0

    def ok(self, name, cond, detail=""):
        self.n += 1
        print(("ok   " if cond else "FAIL ") + name + ((" → " + str(detail)[:300]) if detail else ""))
        if not cond:
            self.fails += 1

    def done(self, label):
        print(f"\n[{label}] {self.n - self.fails}/{self.n} ok — " + ("TODOS OS TESTES PASSARAM" if self.fails == 0 else f"{self.fails} FALHARAM"))
        return 1 if self.fails else 0


ADJ_YES = {"category": "yes", "sleeve_length": "yes", "split_edge:upper_arm_L": "yes"}
ADJ_NO = {"category": "no", "sleeve_length": "yes", "split_edge:upper_arm_L": "no"}


def make_adj(d, name, case_id, o_path, answers=ADJ_YES, **overrides):
    """adjudicação humana CEGA ligada ao caso e à saída julgada (sha256 de O′), como o perfil g0 exige."""
    adj = {"blind": True, "evaluator_id": "ev1", "date": "2026-10-08", "catch_trials_passed": True, "case_id": case_id,
           "output_sha256": fz.sha256_file(o_path), "answers": dict(answers)}
    adj.update(overrides)
    p = os.path.join(d, name); json.dump(adj, open(p, "w")); return p
