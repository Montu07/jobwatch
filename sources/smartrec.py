# sources/smartrec.py
import time
import requests
from utils.text import strip_html

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (JobWatch)",
    "Accept": "application/json, text/plain, /",
})

API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"

def _norm_slug(item):
    """Accept either a plain string or a dict like {'company': 'slug'}."""
    if isinstance(item, str):
        return item.strip().lower()
    if isinstance(item, dict):
        # prefer explicit keys; otherwise fall back to first truthy value
        for k in ("company", "slug", "name"):
            v = item.get(k)
            if v:
                return str(v).strip().lower()
        for v in item.values():
            if v:
                return str(v).strip().lower()
    return ""

def fetch_smartrec(slug_or_dict, max_pages: int = 5, sleep: float = 0.5):
    """
    Returns a list of normalized job dicts from SmartRecruiters.
    Safely handles odd API items (e.g., stray strings) by skipping them.
    """
    slug = _norm_slug(slug_or_dict)
    if not slug:
        return []

    out = []
    page = 1
    while page <= max_pages:
        url = API.format(slug=slug)
        try:
            r = SESSION.get(url, params={"page": page}, timeout=30)
        except Exception:
            # transient network error: stop early for this run
            break

        if r.status_code == 404:
            # company not found on SR
            break
        if r.status_code in (401, 403):
            # board exists but hidden; treat as empty
            break

        try:
            data = r.json() or {}
        except Exception:
            # bad JSON -> stop
            break

        items = data.get("content") or []
        if not isinstance(items, list) or not items:
            break

        for j in items:
            # *** HARDENING: only process dict items ***
            if not isinstance(j, dict):
                # skip weird entries like plain strings
                continue
            try:
                title = j.get("name", "") or ""
                url2 = (j.get("ref") or {}).get("jobAd", "") or ""
                comp = ((j.get("company") or {}) or {}).get("name") or slug.capitalize()

                # location
                loc = (j.get("location") or {}) or {}
                loc_parts = []
                for k in ("city", "region", "country"):
                    v = loc.get(k)
                    if v:
                        loc_parts.append(str(v))
                loc_str = ", ".join(loc_parts)

                created = j.get("releasedDate") or j.get("createdOn") or ""

                # description (HTML -> text)
                desc_html = (((j.get("jobAd") or {}).get("sections") or {})
                             .get("jobDescription") or {}).get("text", "") or ""
                desc = strip_html(desc_html)

                out.append({
                    "id": f"sr:{j.get('id','')}",
                    "title": title,
                    "company": comp,
                    "location": loc_str,
                    "remote": "remote" in f"{title} {desc}".lower(),
                    "url": url2 or f"https://jobs.smartrecruiters.com/{slug}/{j.get('id','')}",
                    "posted_at": created,
                    "description": desc,
                    "source": "smartrecruiters",
                })
            except Exception:
                # never let one bad post break the batch
                continue

        page += 1
        time.sleep(sleep)

    return out