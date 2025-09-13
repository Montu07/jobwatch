# main.py (Greenhouse + Lever + Ashby + Workday + SmartRecruiters) — hardened

import os
import yaml
from datetime import datetime
from dotenv import load_dotenv

from db import get_conn, insert_if_new
from utils.filters import match_job

# sources
from sources.greenhouse import fetch_greenhouse
from sources.lever import fetch_lever
from sources.ashby import fetch_ashby
from sources.workday import fetch_workday
from sources.smartrec import fetch_smartrec

# notify
from notify.telegram import send_telegram

TELEGRAM_MAX = 3800  # keep under Telegram's ~4096 limit with a buffer

def load_config():
    cfg_path = os.getenv("CONFIG_PATH") or "config.yml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def source_fetchers(cfg):
    """Yield (source_key, org_label, jobs_list_or_exception)."""
    srcs = (cfg.get("sources") or {})

    # Greenhouse
    for org in (srcs.get("greenhouse_orgs") or []):
        try:
            jobs = fetch_greenhouse(org)
            yield ("greenhouse", org, jobs, None)
        except Exception as e:
            yield ("greenhouse", org, [], e)

    # Lever
    for org in (srcs.get("lever_orgs") or []):
        try:
            jobs = fetch_lever(org)
            yield ("lever", org, jobs, None)
        except Exception as e:
            yield ("lever", org, [], e)

    # Ashby
    for org in (srcs.get("ashby_orgs") or []):
        try:
            jobs = fetch_ashby(org)
            yield ("ashby", org, jobs, None)
        except Exception as e:
            yield ("ashby", org, [], e)

    # SmartRecruiters — accept strings or dicts; always pass dict to fetcher
    for comp in (srcs.get("smartrec_companies") or []):
        label = comp.get("company") if isinstance(comp, dict) else str(comp)
        payload = comp if isinstance(comp, dict) else {"company": label}
        try:
            jobs = fetch_smartrec(payload)
            yield ("smartrecruiters", label, jobs, None)
        except Exception as e:
            yield ("smartrecruiters", label, [], e)

    # Workday — accept dicts only; label nicely
    for tenant in (srcs.get("workday_tenants") or []):
        label = tenant.get("company") or tenant.get("tenant") or tenant.get("host") or "workday"
        try:
            jobs = fetch_workday(tenant)
            yield ("workday", label, jobs, None)
        except Exception as e:
            yield ("workday", label, [], e)

def format_job_line(j):
    loc = j.get("location") or ""
    title = j.get("title") or ""
    company = j.get("company") or ""
    url = j.get("url") or ""
    return f"• {title} @ {company} — {loc}\n  {url}"

def chunk_and_send(bot, chat, header, lines):
    """Send one compact summary; if too long, send in chunks."""
    bot = (bot or "").strip()
    chat = (str(chat) or "").strip()
    if not bot or not chat:
        return

    body = "\n".join(lines)
    msg = f"{header}\n{body}" if lines else header

    if len(msg) <= TELEGRAM_MAX:
        send_telegram(bot, chat, msg)
        return

    # Split into multiple messages respecting limit
    send_telegram(bot, chat, header)
    buf, cur = [], 0
    for line in lines:
        needed = len(line) + (1 if buf else 0)
        if cur + needed > TELEGRAM_MAX:
            send_telegram(bot, chat, "\n".join(buf))
            buf = [line]
            cur = len(line)
        else:
            if buf:
                buf.append(line)
                cur += len(line) + 1
            else:
                buf = [line]
                cur = len(line)
    if buf:
        send_telegram(bot, chat, "\n".join(buf))

def run():
    print("[main] hardened v2 loaded")  # banner so we know this file is running
    load_dotenv()
    cfg = load_config()

    # env first; fallback to config.notify if present
    bot = os.getenv("TELEGRAM_BOT_TOKEN") or (cfg.get("notify", {}) or {}).get("telegram_bot_token")
    chat = os.getenv("TELEGRAM_CHAT_ID") or (cfg.get("notify", {}) or {}).get("telegram_chat_id")

    # if filters are nested under "filters:", use that; else use top-level keys
    filters_cfg = cfg.get("filters") or cfg

    conn = get_conn()
    new_items = []
    fetched_counts = {}
    errors = []

    for src, org, jobs, err in source_fetchers(cfg):
        key = f"{src}:{org}"
        if err:
            print(f"[warn] {key}: {err}")
            errors.append(f"⚠ {key}: {err}")
            fetched_counts[key] = 0
            continue

        # Type safety + debug
        if not isinstance(jobs, list):
            print(f"[warn] {key}: jobs is {type(jobs).__name__}, forcing []")
            jobs = []
        type_set = {type(x).__name__ for x in jobs} if jobs else set()
        print(f"[debug] {key}: fetched {len(jobs)} (types={sorted(type_set)})")

        # Keep only dict items
        before = len(jobs)
        jobs = [j for j in jobs if isinstance(j, dict)]
        if len(jobs) != before:
            print(f"[debug] {key}: kept {len(jobs)} dict items after filtering")

        fetched_counts[key] = len(jobs)

        for j in jobs:
            try:
                if match_job(j, filters_cfg) and insert_if_new(conn, j):
                    new_items.append(j)
            except Exception as e:
                print(f"[warn] filter/insert failed for {key}: {e}")

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    fetched_total = sum(fetched_counts.values())
    header = f"📣 JobWatch @ {ts}\nFetched: {fetched_total} | New matches: {len(new_items)}"

    new_items.sort(key=lambda x: (x.get("title","").lower(), x.get("company","").lower()))

    lines = []
    if fetched_counts:
        lines.append("🗂 Sources:")
        for k, v in sorted(fetched_counts.items()):
            lines.append(f"  - {k}: {v}")
    else:
        lines.append("🗂 Sources: none")

    if new_items:
        lines.append("")
        lines.append(f"🔥 New matching jobs ({min(len(new_items),25)} shown):")
        for j in new_items[:25]:
            lines.append(format_job_line(j))
        if len(new_items) > 25:
            lines.append(f"...and {len(new_items)-25} more.")
    else:
        lines.append("")
        lines.append("✅ No new matching jobs this run.")

    if errors:
        lines.append("")
        lines.append("⚠ Errors:")
        lines.extend(errors)

    print(header)
    for line in lines:
        print(line)

    chunk_and_send(bot, chat, header, lines)


if __name__ == "__main__":
    run()