# tools/companies_parse.py
import re, pathlib

raw = pathlib.Path("tools/companies_raw.txt").read_text(encoding="utf-8", errors="ignore")

# split and trim non-empty lines
lines = [l.strip() for l in raw.splitlines() if l.strip()]

SKIP_FULL = {
    "Employer Name\tH1B LCA Filings Count",
    "Employer Name H1B LCA Filings Count",
}
SKIP_PREFIX = ("Employer Name", "H1B", "Filings", "Count", "[", "]")

CONSULT_KEYS = [
    "consult", "staff", "solutions", "services", "llc", "inc.", "corp", "corporation",
    "technologies", "technology", "tech", "systems", " it", "it ", "dba ", "group",
    "llp", "ltd", "partners", "associates"
]

names = []
for l in lines:
    if l in SKIP_FULL:
        continue
    # drop trailing counts like "...   210"
    l = re.sub(r"\s+\d+\s*$", "", l)
    # strip leading bullets/prefix punctuation
    l = re.sub(r"^\W+", "", l)
    # collapse spaces
    l = re.sub(r"\s+", " ", l).strip()
    if any(l.startswith(p) for p in SKIP_PREFIX):
        continue
    if not l or len(l) < 2:
        continue
    if len(l.split()) > 12:  # very long lines are likely not names
        continue
    names.append(l)

# de-dupe, preserving order
seen, clean = set(), []
for n in names:
    key = n.lower()
    if key not in seen:
        seen.add(key)
        clean.append(n)

product_like, consultancy_like = [], []
for n in clean:
    lo = n.lower()
    # strong product/company hints
    if any(k in lo for k in [
        "google","meta","amazon","microsoft","tesla","ibm","apple","expedia",
        "ford","netflix","tiktok","toyota","cisco","paypal","stripe","uber",
        "airbnb","pinterest","reddit","robinhood","cloudflare","palantir",
        "databricks","datadog","brex","gusto","lyft","plaid","figma",
        "snowflake","nvidia","qualtrics","workday","servicenow","salesforce",
        "bytedance","optum","mastercard","barclays","dropbox","nike","amgen",
    ]):
        product_like.append(n)
    elif sum(k in lo for k in CONSULT_KEYS) >= 2:
        consultancy_like.append(n)
    else:
        product_like.append(n)

pathlib.Path("tools/companies_clean.txt").write_text("\n".join(product_like), encoding="utf-8")
pathlib.Path("tools/companies_consultancies.txt").write_text("\n".join(consultancy_like), encoding="utf-8")

print(f"Saved {len(product_like)} product-like -> tools/companies_clean.txt")
print(f"Saved {len(consultancy_like)} likely consultancies -> tools/companies_consultancies.txt")