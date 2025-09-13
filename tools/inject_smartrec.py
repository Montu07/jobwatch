# tools/inject_smartrec.py
import pathlib, yaml, re

CLEAN = pathlib.Path("tools/companies_clean.txt")
CFG   = pathlib.Path("config.generated.yml")  # change to your target config if needed

# 1) read, normalize, and de-duplicate company slugs
def to_slug(s: str) -> str:
    s = s.strip()
    s = s.replace("&", "and")
    s = re.sub(r"[^a-zA-Z0-9\- ]+", "", s)
    s = s.replace(" ", "")
    return s.lower()

names = []
if CLEAN.exists():
    for line in CLEAN.read_text(encoding="utf-8").splitlines():
        if not line.strip(): 
            continue
        slug = to_slug(line)
        if slug and slug not in names:
            names.append(slug)
else:
    raise SystemExit(f"Missing {CLEAN}")

# 2) load config (or start fresh)
cfg = {}
if CFG.exists():
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}

cfg.setdefault("sources", {})
cfg["sources"]["smartrec_companies"] = names

# 3) write back
CFG.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")

print(f"Injected {len(names)} smartrecruiters companies into {CFG}")