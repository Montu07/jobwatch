#!/usr/bin/env python3
# tools/workday_from_urls.py
import re, sys

print("[init] tools/workday_from_urls.py loaded", flush=True)

PAT = re.compile(
    r"https?://(?P<prehost>[^/]+)\.myworkdayjobs\.com/(?P<locale>[^/]+)/(?P<path>[^/?#]+)",
    re.IGNORECASE,
)

def parse_url(u: str):
    u = (u or "").strip()
    m = PAT.search(u)
    if not m:
        return {}
    pre = m.group("prehost")           # e.g. "accenture.wd103"
    parts = pre.split(".")
    if len(parts) < 2:
        return {}
    host = ".".join(parts[:-1])        # "accenture"
    subdomain = parts[-1]              # "wd103"
    path = m.group("path")             # "AccentureCareers"
    label = host.replace("-", " ").replace("_", " ").title()
    return {"subdomain": subdomain, "host": host, "path": path, "company": label}

def main(argv):
    print(f"[debug] __name__={__name__!r}", flush=True)
    print(f"[debug] argv={argv!r}", flush=True)

    urls = [a for a in argv if a.strip()]
    print(f"[debug] received {len(urls)} URL(s)", flush=True)
    for u in urls:
        print(f"  > {u}", flush=True)

    tenants = []
    for u in urls:
        d = parse_url(u)
        if d:
            tenants.append(d)
            print(f"[ok] parsed -> {d}", flush=True)
        else:
            print(f"[skip] not a Workday URL -> {u}", flush=True)

    if not tenants:
        print("[warn] no tenants parsed; nothing to print.", flush=True)
        return

    print("\n# ---- Suggested config.yml snippet ----", flush=True)
    print("sources:", flush=True)
    print("  workday_tenants:", flush=True)
    for t in tenants:
        print(
            f'    - {{ subdomain: "{t["subdomain"]}", host: "{t["host"]}", path: "{t["path"]}", company: "{t["company"]}" }}',
            flush=True,
        )

# Call main() unconditionally so it runs even if the _main_ guard gets mangled
main(sys.argv[1:])