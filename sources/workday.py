# sources/workday.py
import requests, datetime, time
from utils.text import strip_html, stable_id

HEADERS = {
    "User-Agent": "Mozilla/5.0 (JobWatch)",
    "Accept": "application/json, text/plain, /",
    "Content-Type": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

def _host(tenant):
    # host pattern: <tenant>.<subdomain>.myworkdayjobs.com
    return f"{tenant['tenant']}.{tenant['subdomain']}.myworkdayjobs.com"

def _api_url(tenant):
    # API pattern: https://<tenant>.<subdomain>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs
    return f"https://{_host(tenant)}/wday/cxs/{tenant['tenant']}/{tenant['site']}/jobs"

def _public_root_url(tenant):
    # Public root used for cookie priming and referer
    return f"https://{_host(tenant)}/en-US/{tenant['tenant']}"

def _job_url(tenant, external_path):
    return f"{_public_root_url(tenant)}/job/{external_path}"

def _prime_session(tenant, session):
    # Hit the public site first to receive cookies Workday expects
    root = _public_root_url(tenant)
    session.headers.update(HEADERS | {
        "Origin": f"https://{_host(tenant)}",
        "Referer": root,
    })
    # try a couple of likely paths to set cookies
    for path in ("", "/jobs", "/careers", "/search"):
        try:
            r = session.get(root + path, timeout=20)
            # Some tenants respond non-200 on odd paths; that's fine as long as cookies set
        except Exception:
            pass

def _fetch_page(tenant, offset=0, limit=50, session=None):
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)
    body = {"limit": limit, "offset": offset, "appliedFacets": {}, "searchText": ""}
    r = session.post(_api_url(tenant), json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_workday(tenant):
    """
    tenant dict example:
      { "subdomain": "wd1", "tenant": "databricks", "site": "External", "company": "Databricks" }
      { "subdomain": "wd5", "tenant": "nvidia",     "site": "NVIDIAExternalCareerSite", "company": "NVIDIA" }
    """
    out = []
    offset, limit = 0, 50
    session = requests.Session()
    _prime_session(tenant, session)  # set cookies + Origin/Referer/User-Agent

    tries = 0
    while True:
        tries += 1
        try:
            data = _fetch_page(tenant, offset=offset, limit=limit, session=session)
        except requests.HTTPError as e:
            # Handle 406/403 by re-priming once and retrying
            if e.response is not None and e.response.status_code in (403, 406) and tries <= 2:
                time.sleep(1.0)
                _prime_session(tenant, session)
                data = _fetch_page(tenant, offset=offset, limit=limit, session=session)
            else:
                raise
        except Exception:
            # brief backoff and one retry for network hiccups
            if tries <= 2:
                time.sleep(1.0)
                continue
            raise

        jobs = data.get("jobPostings", []) or data.get("items", [])
        if not jobs:
            break

        company = tenant.get("company") or tenant["tenant"]
        for j in jobs:
            title = j.get("title") or j.get("titleLocalized") or ""
            loc = ", ".join([l.get("formattedName","") for l in j.get("locations", [])]) \
                  or (j.get("locationsText","") or "")
            external_path = j.get("externalPath","")
            job_url = _job_url(tenant, external_path) if external_path else _public_root_url(tenant)
            desc = strip_html(j.get("bulletFields","")) if isinstance(j.get("bulletFields",""), str) else ""
            updated = j.get("postedOn") or j.get("startDate") or j.get("timeUpdated") \
                      or datetime.datetime.utcnow().isoformat()
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
        time.sleep(0.4)  # polite rate limit
    return out