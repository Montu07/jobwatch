# tools/discover_ats.py
import sys, re, json, time
import requests
from bs4 import BeautifulSoup

# -------- HTTP session ----------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (JobWatch)"})
TIMEOUT = 20

# -------- Slug variants ----------
PUNCT = r"[^\w\s-]"

def words(name: str):
    clean = re.sub(PUNCT, " ", name, flags=re.I).strip()
    return [w for w in re.split(r"\s+", clean) if w]

def variants(name: str):
    ws = words(name)
    if not ws:
        return []
    base = "".join(ws).lower()
    hyph = "-".join(ws).lower()
    low = [base, hyph, ws[0].lower()] + [w.lower() for w in ws]
    title = "".join(w.capitalize() for w in ws)
    caps = [title, "".join(ws), "".join(w.capitalize() for w in ws)]
    # add common endings/removals
    extras = []
    endings = ["inc", "inc.", "corp", "labs", "ai", "technologies", "systems"]
    # remove endings
    if ws[-1].lower() in endings:
        ws2 = ws[:-1]
        if ws2:
            extras += ["".join(ws2).lower(), "-".join(ws2).lower(), "".join(w.capitalize() for w in ws2)]
    # add endings
    for e in ["ai", "labs"]:
        extras += [base+e, hyph+"-"+e, "".join(w.capitalize() for w in ws)+e.capitalize()]
    # de-dupe preserving order
    seen = set()
    out = []
    for s in low + caps + extras:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out[:40]

# -------- ATS checkers ----------
def check_greenhouse(slug: str):
    # Greenhouse boards API (public)
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs") or []
            return True, len(jobs), f"https://boards.greenhouse.io/{slug}"
        if r.status_code in (401, 403):
            # board exists but restricted -> treat as match with 0
            return True, 0, f"https://boards.greenhouse.io/{slug}"
    except Exception:
        pass
    return False, 0, ""

def check_lever(slug: str):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return True, len(data), f"https://jobs.lever.co/{slug}"
        if r.status_code in (401, 403):
            return True, 0, f"https://jobs.lever.co/{slug}"
    except Exception:
        pass
    return False, 0, ""

def check_ashby(slug: str):
    url = f"https://jobs.ashbyhq.com/{slug}"
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code != 200 or not r.text:
            return False, 0, ""
        soup = BeautifulSoup(r.text, "lxml")
        script = soup.find("script", id="_NEXT_DATA_", type="application/json")
        if not script or not script.string:
            return False, 0, ""
        data = json.loads(script.string)
        jobs = data.get("props", {}).get("pageProps", {}).get("jobs", []) or []
        return (True, len(jobs), url) if jobs or data else (False, 0, "")
    except Exception:
        pass
    return False, 0, ""

def check_smartrec(slug: str):
    # Try page=1 first (preferred)
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?page=1"
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            items = data.get("content") or []
            return True, len(items), f"https://careers.smartrecruiters.com/{slug}"
        if r.status_code in (401, 403):
            return True, 0, f"https://careers.smartrecruiters.com/{slug}"
    except Exception:
        pass
    return False, 0, ""

ATS_CHECKS = [
    ("greenhouse", check_greenhouse),
    ("lever", check_lever),
    ("ashby", check_ashby),
    ("smartrecruiters", check_smartrec),
    # Workday: tenant discovery is manual; we’ll plug those in when you paste a working URL
]

def find_ats_for_company(name: str):
    tried = []
    for cand in variants(name):
        for label, fn in ATS_CHECKS:
            ok, count, home = fn(cand)
            tried.append((label, cand, ok, count))
            if ok:
                return label, cand, count, home, tried
    return None, None, 0, "", tried

def main(args):
    if not args:
        print("Usage: python tools/discover_ats.py <Company Name 1> <Company Name 2> ...")
        return
    results = {"greenhouse": [], "lever": [], "ashby": [], "smartrecruiters": []}
    for name in args:
        label, slug, count, home, tried = find_ats_for_company(name)
        if label:
            print(f"[FOUND] {name} -> {label}:{slug} (jobs={count}) {home}")
            results[label].append(slug)
        else:
            print(f"[MISS ] {name} -> not found on GH/Lever/Ashby/SR (tried {len(tried)} candidates)")
        time.sleep(0.2)

    # Print config.yml snippet
    print("\n# ---- Suggested config.yml snippet ----")
    print("sources:")
    if results["greenhouse"]:
        print("  greenhouse_orgs:")
        for s in sorted(set(results["greenhouse"])):
            print(f"    - \"{s}\"")
    if results["lever"]:
        print("  lever_orgs:")
        for s in sorted(set(results["lever"])):
            print(f"    - \"{s}\"")
    if results["ashby"]:
        print("  ashby_orgs:")
        for s in sorted(set(results["ashby"])):
            print(f"    - \"{s}\"")
    if results["smartrecruiters"]:
        print("  smartrec_companies:")
        for s in sorted(set(results["smartrecruiters"])):
            print(f"    - \"{s}\"")
    print("# (Add workday_tenants manually when you have real tenant URLs.)")


if __name__ == "__main__":
    main(sys.argv[1:])