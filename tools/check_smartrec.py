#!/usr/bin/env python3
# tools/check_smartrec.py
import sys, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sources.smartrec import fetch_smartrec

def main():
    cfg_path = ROOT / "config.yml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    comps = (cfg.get("sources", {}) or {}).get("smartrec_companies", []) or []

    if not comps:
        print("[check] No smartrec_companies in config.yml")
        return

    total = 0
    nonzero = 0
    for comp in comps:
        label = comp.get("company") if isinstance(comp, dict) else str(comp)
        payload = comp if isinstance(comp, dict) else {"company": label}
        try:
            jobs = fetch_smartrec(payload) or []
            n = len([j for j in jobs if isinstance(j, dict)])
            total += 1
            if n > 0:
                nonzero += 1
                print(f"[HAS]  {label:<35} -> {n}")
            else:
                print(f"[zero] {label}")
        except Exception as e:
            print(f"[ERR]  {label} -> {e}")

    print(f"\n[summary] companies checked: {total}, with jobs: {nonzero}")

if __name__ == "__main__":
    main()