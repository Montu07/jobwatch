#!/usr/bin/env python3
# tools/check_sources.py
import sys, pathlib, yaml
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sources.greenhouse import fetch_greenhouse
from sources.lever import fetch_lever
from sources.ashby import fetch_ashby
from sources.smartrec import fetch_smartrec
from sources.workday import fetch_workday

def safe_len(objs): return len([o for o in (objs or []) if isinstance(o, dict)])

def main():
    cfg = yaml.safe_load((ROOT/"config.yml").read_text(encoding="utf-8")) or {}
    srcs = cfg.get("sources", {}) or {}

    def check_list(name, items, fetch_fn, fmt=lambda x: x):
        if not items: return
        print(f"\n== {name} ==")
        for it in items:
            label = it.get("company") if isinstance(it, dict) else str(it)
            payload = fmt(it)
            try:
                jobs = fetch_fn(payload)
                print(f"[{name}] {label:<35} -> {safe_len(jobs)}")
            except Exception as e:
                print(f"[{name}] {label:<35} -> ERR: {e}")

    check_list("greenhouse", srcs.get("greenhouse_orgs", []), fetch_greenhouse, lambda x: str(x))
    check_list("lever",      srcs.get("lever_orgs", []),      fetch_lever,      lambda x: str(x))
    check_list("ashby",      srcs.get("ashby_orgs", []),      fetch_ashby,      lambda x: str(x))
    check_list("smartrec",   srcs.get("smartrec_companies", []), fetch_smartrec,
               lambda x: x if isinstance(x, dict) else {"company": str(x)})
    check_list("workday",    srcs.get("workday_tenants", []), fetch_workday,    lambda x: x)

if __name__ == "__main__":
    main()