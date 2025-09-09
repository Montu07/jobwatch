import hashlib, re
from html import unescape

def strip_html(s: str) -> str:
    s = unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def stable_id(url: str, title: str, company: str) -> str:
    return hashlib.sha256(f"{url}|{title}|{company}".encode()).hexdigest()[:24]
