import requests, json, datetime
from bs4 import BeautifulSoup
from utils.text import strip_html, stable_id

def fetch_ashby(org: str):
    """
    Scrape Ashby boards like https://jobs.ashbyhq.com/<org>
    Returns a normalized list of job dicts.
    """
    url = f"https://jobs.ashbyhq.com/{org}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script:
        return []

    data = json.loads(script.string)
    postings = data.get("props", {}).get("pageProps", {}).get("jobs", []) or []

    out = []
    for j in postings:
        title = j.get("title", "")
        loc = ", ".join([l.get("name", "") for l in j.get("locations", [])]) or (j.get("location", "") or "")
        job_url = j.get("jobUrl") or j.get("url") or f"https://jobs.ashbyhq.com/{org}/{j.get('slug','')}"
        desc = strip_html(j.get("description", ""))
        updated = j.get("updatedAt") or j.get("createdAt") or datetime.datetime.utcnow().isoformat()
        remote = "remote" in (f"{loc} {desc}".lower())

        out.append({
            "id": stable_id(job_url, title, org),
            "title": title,
            "company": org,
            "location": loc,
            "remote": remote,
            "url": job_url,
            "posted_at": updated,
            "description": desc,
            "source": "ashby",
        })
    return out
