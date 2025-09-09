import re, datetime

US_HINTS = [
    "united states", "usa", "u.s.", "remote - usa", "us remote", "remote (us)", "remote (usa)"
]

def _parse_ts(ts):
    """Parse ISO8601 or epoch(ms/sec) to naive UTC datetime. Return None if unknown."""
    if ts is None:
        return None
    s = str(ts).strip()
    try:
        # Epoch milliseconds or seconds (Lever uses createdAt in ms)
        if s.isdigit():
            i = int(s)
            if i > 1_000_000_000_000:  # ms
                return datetime.datetime.utcfromtimestamp(i / 1000.0)
            elif i > 1_000_000_000:    # sec
                return datetime.datetime.utcfromtimestamp(i)
        # ISO8601 (Greenhouse updated_at)
        s2 = s.replace("Z", "+00:00")
        try:
            dt = datetime.datetime.fromisoformat(s2)
            # make naive UTC for comparison
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return None
    except Exception:
        return None

def is_recent(job, cfg):
    days = int(cfg.get("min_posted_days_ago", 30))
    ts = job.get("posted_at") or job.get("updated_at")
    dt = _parse_ts(ts)
    if not dt:
        # If timestamp unknown, allow it (we can still catch the job)
        return True
    return (datetime.datetime.utcnow() - dt).days <= days

def looks_us(job):
    loc = ((job.get("location") or "") + " " + (job.get("description") or "")).lower()
    if any(h in loc for h in US_HINTS):
        return True
    # Look for common US state abbreviations like ", CA", ", NY", etc.
    return bool(re.search(
        r",\s?(AL|AK|AZ|AR|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV)\b",
        loc, re.I
    ))

def match_job(job, cfg):
    text = f"{job.get('title','')} {job.get('description','')}".lower()

    # Date window (e.g., last 3 days)
    if not is_recent(job, cfg):
        return False

    # US-only
    if not looks_us(job):
        # allow if explicitly listed in locations_any
        loc = (job.get("location") or "").lower()
        if not any(s.lower() in loc or s.lower() in text for s in cfg.get("locations_any", [])):
            return False

    # Exclude titles
    for ex in cfg.get("exclude_if_title", []):
        if ex.lower() in (job.get('title','').lower()):
            return False

    # Must match at least one keyword
    if cfg.get("keywords_any"):
        if not any(k.lower() in text for k in cfg["keywords_any"]):
            return False

    # Require any of the must-haves
    if cfg.get("must_have_any"):
        if not any(m.lower() in text for m in cfg["must_have_any"]):
            return False

    # Optional locations_any gate (kept, but looks_us already narrows to US)
    if cfg.get("locations_any"):
        loc = (job.get("location") or "").lower()
        ok = any(l.lower() in loc or l.lower() in text for l in cfg["locations_any"])
        if not ok and not (job.get("remote") and cfg.get("remote_ok", True)):
            return False

    return True
