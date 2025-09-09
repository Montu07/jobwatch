import requests, datetime, time
from utils.text import strip_html, stable_id

# Example tenant dict for config.yml:
# { subdomain: "wd1", tenant: "databricks", site: "External", company: "Databricks" }

def _fetch_page(tenant, offset=0, limit=50):
    url = f"https://{tenant['subdomain']}.myworkdayjobs.com/wday/cxs/{tenant['tenant']}/{tenant['site']}/jobs"
    body = {"limit": limit, "offset": offset, "appliedFacets": {}, "searchText": ""}
    r = requests.post(url, json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_workday(tenant):
    """
    Fetch Workday jobs for a given tenant descriptor.
    """
    out = []
    offset, limit = 0, 50
    while True:
        data = _fetch_page(tenant, offset=offset, limit=limit)
        jobs = data.get("jobPostings", []) or data.get("items", [])
        if not jobs:
            break

        for j in jobs:
            title = j.get("title") or j.get("titleLocalized") or ""
            loc = ", ".join([l.get("formattedName", "") for l in j.get("locations", [])]) \
                  or (j.get("locationsText", "") or "")
            job_url = f"https://{tenant['subdomain']}.myworkdayjobs.com/en-US/{tenant['tenant']}/job/{j.get('externalPath','')}"
            desc = strip_html(j.get("bulletFields", "")) if isinstance(j.get("bulletFields", ""), str) else ""
            updated = j.get("postedOn") or j.get("startDate") or j.get("timeUpdated") \
                      or datetime.datetime.utcnow().isoformat()
            company = tenant.get("company") or tenant["tenant"]
            remote = "remote" in (f"{title} {desc} {loc}".lower())

            out.append({
                "id": stable_id(job_url, title, company),
                "title": title,
                "company": company,
                "location": loc,
                "remote": remote,
                "url": job_url,
                "posted_at": updated,
                "description": desc,
                "source": "workday",
            })

        offset += limit
        time.sleep(0.5)  # polite rate-limit
    return out
