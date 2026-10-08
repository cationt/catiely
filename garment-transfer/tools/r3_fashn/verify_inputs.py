#!/usr/bin/env python3
"""Confere bytes de A/B contra a referencia Klein/R1-EI e a decisao R3, sem GPU."""
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = Path(__file__).with_name("expected_inputs.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(person, garment, decision=None):
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    actual = {"person": sha256_file(person), "garment": sha256_file(garment)}
    if actual != expected["inputs_sha256"]:
        raise ValueError("A/B divergem dos SHA256 esperados do Klein/R1-EI")
    if decision:
        d = json.loads(Path(decision).read_text(encoding="utf-8-sig"))
        for key in ("category", "garment_photo_type", "scope", "inputs_sha256"):
            if d.get(key) != expected[key]:
                raise ValueError("inputs_decision.json divergente ou antigo: " + key)
    return {"ok": True, "expected_source": str(EXPECTED), "inputs_sha256": actual,
            "scope": expected["scope"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--person", required=True)
    ap.add_argument("--garment", required=True)
    ap.add_argument("--decision")
    a = ap.parse_args()
    try:
        print(json.dumps(verify(a.person, a.garment, a.decision)))
    except (OSError, ValueError, KeyError) as e:
        ap.exit(2, "[r3 inputs] " + str(e) + "\n")


if __name__ == "__main__":
    main()
