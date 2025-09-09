# sources/smartrec.py
import requests, datetime, time
from utils.text import strip_html, stable_id

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (JobWatch)"})

API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"

def fetch_smartrec(slug: str, max_pages: int = 10):
    """
    slug: the company's SmartRecruiters slug, e.g. 'celonis'
    We page through the public API and normalize items.
    """
    out = []
    page = 1
    while page <= max_pages:
        url = f"{API.format(slug=slug)}?page={page}"
        r = SESSION.get(url, timeout=30)
        if r.status_code == 404:
            # company slug not found
            break
        r.raise_for_status()
        data = r.json() or {}
        items = data.get("content") or []
        if not items:
            break

        for it in items:
            # fields per API
            title = it.get("name") or ""
            company = it.get("company", {}).get("identifier") or slug
            loc = ", ".join([l.get("city","") for l in it.get("location", {}).get("labels", []) if l.get("city")]) \
                  or (it.get("location", {}).get("city") or "")
            url = it.get("ref", {}).get("jobAdUrl") or it.get("ref", {}).get("jobAd") or ""
            desc = strip_html((it.get("jobAd", {}).get("sections", {}).get("companyDescription", {}).get("text", "")))
            posted = it.get("releasedDate") or it.get("createdOn") or datetime.datetime.utcnow().isoformat()
            remote = "remote" in f"{title} {loc}".lower()

            out.append({
                "id": stable_id(url, title, company),
                "title": title,
                "company": company,
                "location": loc,
                "remote": remote,
                "url": url,
                "posted_at": posted,
                "description": desc,
                "source": "smartrecruiters",
            })
        page += 1
        time.sleep(0.2)
    return out