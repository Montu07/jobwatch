# sources/workday.py
import re, json, time, datetime
import requests
from bs4 import BeautifulSoup
from utils.text import strip_html, stable_id

UA = {"User-Agent": "Mozilla/5.0 (JobWatch)"}

def _host(t):
    # allow separate host vs path tenant.
    # fallback: if 'host' not provided, use 'tenant' (old behavior)
    host_name = t.get("host") or t["tenant"]
    return f"{host_name}.{t['subdomain']}.myworkdayjobs.com"

def _path_tenant(t):
    # path segment after /en-US/, can differ (e.g., Careers, NVIDIAExternalCareerSite)
    return t.get("path") or t["tenant"]

def _public_root(t):
    # most tenants work with this English locale root
    return f"https://{_host(t)}/en-US/{_path_tenant(t)}"

def _search_urls(t):
    """
    Return a list of likely search/landing URLs to try in order.
    Different tenants use different landing paths.
    """
    root = _public_root(t)
    return [
        root + "/search",
        root + "/careers",
        root + "/jobs",
        root,  # landing itself
    ]

def _extract_jobs_from_html(html):
    """
    Workday embeds JSON in one or more <script> tags.
    We look for a JSON block that contains job listings.
    """
    soup = BeautifulSoup(html, "lxml")

    # Strategy 1: big JSON object with 'jobPostings'
    for s in soup.find_all("script"):
        txt = (s.string or s.text or "").strip()
        if not txt or "jobPostings" not in txt and '"jobPostings"' not in txt:
            continue
        start, end = txt.find("{"), txt.rfind("}")
        if start != -1 and end != -1 and end > start:
            blob = txt[start:end+1]
            try:
                data = json.loads(blob)
                postings = []
                def walk(x):
                    nonlocal postings
                    if isinstance(x, dict):
                        for k in ("jobPostings", "items", "results"):
                            v = x.get(k)
                            if isinstance(v, list) and v:
                                postings.extend(v)
                        for v in x.values():
                            walk(v)
                    elif isinstance(x, list):
                        for v in x:
                            walk(v)
                walk(data)
                if postings:
                    return postings
            except Exception:
                pass

    # Strategy 2: fallback heuristic search for objects w/ externalPath
    m_all = re.findall(r'\{[^<>]+?"externalPath"[^<>]+?\}', html)
    postings = []
    for mm in m_all:
        try:
            postings.append(json.loads(mm))
        except Exception:
            continue
    return postings

def fetch_workday(tenant):
    """
    tenant example (new flexible form):
      { "subdomain": "wd3", "host": "lseg", "path": "Careers", "company": "LSEG" }
      { "subdomain": "wd3", "host": "relx", "path": "relx", "company": "RELX" }
      { "subdomain": "wd5", "host": "nvidia", "path": "NVIDIAExternalCareerSite", "company": "NVIDIA" }

    Backward compatible with:
      { "subdomain": "wd5", "tenant": "nvidia", "company": "NVIDIA" }
    """
    sess = requests.Session()
    sess.headers.update(UA)

    html = None
    for url in _search_urls(tenant):
        try:
            r = sess.get(url, timeout=25)
            if r.status_code in (200, 204) and r.text:
                html = r.text
                break
        except Exception:
            pass
        time.sleep(0.2)

    if not html:
        # last attempt: plain root
        try:
            r = sess.get(_public_root(tenant), timeout=25)
            if r.status_code in (200, 204) and r.text:
                html = r.text
        except Exception:
            pass

    if not html:
        return []

    raw_posts = _extract_jobs_from_html(html)
    out = []
    company = tenant.get("company") or (tenant.get("host") or tenant.get("tenant"))

    for j in raw_posts:
        title = (j.get("title") or j.get("titleLocalized") or j.get("displayJobTitle") or "").strip()

        # location
        loc = ""
        if isinstance(j.get("locations"), list):
            loc = ", ".join([x.get("formattedName","") or x.get("name","") for x in j["locations"]])
        loc = loc or j.get("locationsText","") or j.get("location","") or ""

        # url
        ext = j.get("externalPath") or j.get("externalPathKey") or j.get("canonicalPositionUrl") or ""
        if ext.startswith("/"):
            ext = ext[1:]
        job_url = f"{_public_root(tenant)}/job/{ext}" if ext else _public_root(tenant)

        # description (often short in embedded JSON)
        desc = j.get("externalPostingDescription") or j.get("jobPostingInfo",{}).get("jobDescription","") or ""
        desc = strip_html(desc)

        posted = j.get("postedOn") or j.get("startDate") or j.get("timeUpdated") or j.get("updatedAt") \
                 or datetime.datetime.utcnow().isoformat()
        remote = "remote" in f"{title} {loc} {desc}".lower()

        if title and job_url:
            out.append({
                "id": stable_id(job_url, title, company),
                "title": title,
                "company": company,
                "location": loc,
                "remote": remote,
                "url": job_url,
                "posted_at": posted,
                "description": desc,
                "source": "workday",
            })
    return out