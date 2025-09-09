import requests, datetime
from utils.text import strip_html, stable_id

def fetch_greenhouse(org: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{org}/jobs?content=true"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    out = []
    for j in data.get("jobs", []):
        desc = strip_html(j.get("content", ""))
        out.append({
            "id": stable_id(j.get("absolute_url",""), j.get("title",""), org),
            "title": j.get("title",""),
            "company": org,
            "location": (j.get("location") or {}).get("name",""),
            "remote": ("remote" in desc.lower() or "work from home" in desc.lower()),
            "url": j.get("absolute_url",""),
            "posted_at": j.get("updated_at") or datetime.datetime.utcnow().isoformat(),
            "description": desc,
            "source": "greenhouse"
        })
    return out
