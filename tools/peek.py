#!/usr/bin/env python3
# tools/peek.py
"""
Quick sampler for any source.

Examples (PowerShell):
  python tools/peek.py greenhouse databricks -n 5
  python tools/peek.py smartrec accenture -n 5

Workday (two options):
  # JSON string (PowerShell needs escaped quotes):
  python tools/peek.py workday '{\"subdomain\":\"wd103\",\"host\":\"accenture\",\"path\":\"AccentureCareers\",\"company\":\"Accenture\"}' -n 5

  # OR a JSON file:
  python tools/peek.py workday .\tools\examples\accenture.json -n 5
"""

import sys, json, pathlib, argparse

# Make repo root importable
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sources.greenhouse import fetch_greenhouse
from sources.lever import fetch_lever
from sources.ashby import fetch_ashby
from sources.smartrec import fetch_smartrec
from sources.workday import fetch_workday


def pr(s=""):
    print(s, flush=True)


def show(j, idx):
    title = (j.get("title") or "").strip()
    company = (j.get("company") or "").strip()
    loc = (j.get("location") or "").strip()
    url = (j.get("url") or "").strip()
    pr(f"{idx:>2}. {title} @ {company} — {loc}")
    pr(f"    {url}")


def parse_workday_arg(arg: str) -> dict:
    p = pathlib.Path(arg)
    if p.suffix.lower() == ".json" and p.exists():
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    # Otherwise assume JSON string
    return json.loads(arg)


def main(argv):
    parser = argparse.ArgumentParser(description="Peek jobs from a source")
    parser.add_argument("source", choices=["greenhouse", "lever", "ashby", "smartrec", "workday"])
    parser.add_argument("org_or_json", help="Org/slug for all but workday; JSON string or .json file for workday")
    parser.add_argument("-n", "--limit", type=int, default=5, help="How many to show (default 5)")
    args = parser.parse_args(argv)

    pr(f"[peek] source={args.source} arg={args.org_or_json} limit={args.limit}")

    try:
        if args.source == "greenhouse":
            jobs = fetch_greenhouse(args.org_or_json)

        elif args.source == "lever":
            jobs = fetch_lever(args.org_or_json)

        elif args.source == "ashby":
            jobs = fetch_ashby(args.org_or_json)

        elif args.source == "smartrec":
            # Accept either {"company": "<slug>"} or just "<slug>"
            comp = args.org_or_json.strip()
            payload = {"company": comp} if not comp.startswith("{") else json.loads(comp)
            jobs = fetch_smartrec(payload)

        elif args.source == "workday":
            conf = parse_workday_arg(args.org_or_json)
            if not isinstance(conf, dict):
                raise ValueError("Workday argument must resolve to a JSON object")
            jobs = fetch_workday(conf)

        else:
            pr("Unknown source.")
            return

    except Exception as e:
        pr(f"[error] fetch failed: {e}")
        return

    if not isinstance(jobs, list):
        pr(f"[warn] fetch returned {type(jobs)._name_}, expected list — nothing to show.")
        return

    pr(f"[peek] fetched {len(jobs)} item(s)")
    for i, j in enumerate(jobs[: args.limit], 1):
        if not isinstance(j, dict):
            pr(f"{i:>2}. [skip non-dict item: {type(j)._name_}]")
            continue
        show(j, i)


if __name__ == "__main__":
    main(sys.argv[1:])