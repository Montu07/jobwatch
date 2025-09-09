import requests, datetime
from utils.text import strip_html, stable_id

def fetch_lever(org: str):
    url = f"https://api.lever.co/v0/postings/{org}?mode=json"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    out = []
    for j in r.json():
        desc = strip_html(j.get("description",""))
        title = j.get("text","")
        hosted = j.get("hostedUrl","")
        categories = j.get("categories") or {}
        location = ", ".join([v for v in categories.values() if isinstance(v, str)])
        remote = ("remote" in (categories.get("commitment","") or "").lower()) or ("remote" in desc.lower())
        out.append({
            "id": stable_id(hosted, title, org),
            "title": title,
            "company": org,
            "location": location,
            "remote": remote,
            "url": hosted,
            "posted_at": j.get("createdAt") or datetime.datetime.utcnow().isoformat(),
            "description": desc,
            "source": "lever"
        })
    return out
