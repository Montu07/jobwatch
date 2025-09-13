# utils/filters.py
import re
from datetime import datetime, timezone
from typing import Dict, Any, Iterable, Optional

from utils.text import strip_html


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _match_any(text: str, terms: Iterable[str]) -> bool:
    """
    True if ANY term matches the text.
    Term supports plain substring or regex when written as /pattern/.
    """
    t = _norm(text)
    for raw in terms or []:
        term = (raw or "").strip()
        if not term:
            continue
        if len(term) >= 2 and term.startswith("/") and term.endswith("/"):
            # regex
            try:
                if re.search(term[1:-1], t, flags=re.IGNORECASE):
                    return True
            except re.error:
                # fallback to substring if regex is invalid
                if term[1:-1].lower() in t:
                    return True
        else:
            if term.lower() in t:
                return True
    return False


def _all_match(text: str, terms: Iterable[str]) -> bool:
    t = _norm(text)
    for raw in terms or []:
        term = (raw or "").strip()
        if not term:
            continue
        if len(term) >= 2 and term.startswith("/") and term.endswith("/"):
            try:
                if not re.search(term[1:-1], t, flags=re.IGNORECASE):
                    return False
            except re.error:
                if term[1:-1].lower() not in t:
                    return False
        else:
            if term.lower() not in t:
                return False
    return True


def _days_since_iso(iso_str: Optional[str]) -> Optional[int]:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - dt).total_seconds() // 86400)
    except Exception:
        return None


def match_job(job: Dict[str, Any], cfg: Dict[str, Any]) -> bool:
    """
    Decide whether a normalized job dict should be notified.
    Expected fields (best-effort): title, company, location, description, posted_at, remote.
    """
    # --- Hard guard: ignore malformed items (e.g., SmartRecruiters edge cases) ---
    if not isinstance(job, dict):
        return False

    title = _norm(job.get("title"))
    loc = _norm(job.get("location"))
    desc_raw = job.get("description") or ""
    desc = _norm(strip_html(desc_raw))
    hay = f"{title}\n{desc}"

    include_titles = cfg.get("include_titles") or []
    exclude_titles = cfg.get("exclude_titles") or []
    include_locations = cfg.get("include_locations") or []
    exclude_locations = cfg.get("exclude_locations") or []
    keywords_any = cfg.get("keywords_any") or []
    must_have_any = cfg.get("must_have_any") or []  # legacy compat
    ignore_words = cfg.get("ignore_words") or []    # legacy compat

    # Posted window: only alert if posted/updated within the last N days
    max_age_days = cfg.get("min_posted_days_ago")
    if max_age_days is not None:
        days = _days_since_iso(job.get("posted_at"))
        # If date is parseable and older than threshold -> skip
        if days is not None and days > int(max_age_days):
            return False

    # Title include/exclude
    if include_titles and not _match_any(title, include_titles):
        return False
    if exclude_titles and _match_any(title, exclude_titles):
        return False

    # Extra include keywords (title + description)
    if keywords_any and not _match_any(hay, keywords_any):
        return False
    if must_have_any and not _match_any(hay, must_have_any):
        return False
    if ignore_words and _match_any(hay, ignore_words):
        return False

    # Location include/exclude (respect explicit remote flag too)
    remote_ok = bool(cfg.get("remote_ok"))
    job_is_remote = bool(job.get("remote")) or ("remote" in (title + " " + loc))
    if include_locations and not _match_any(loc, include_locations):
        if not (remote_ok and job_is_remote):
            return False
    if exclude_locations and _match_any(loc, exclude_locations):
        if not (remote_ok and job_is_remote):
            return False

    return True