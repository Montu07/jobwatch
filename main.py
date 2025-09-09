# main.py (your style + Ashby/Workday added)

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

# notify
from notify.telegram import send_telegram

TELEGRAM_MAX = 3800  # keep under Telegram's ~4096 message limit with some buffer


def load_config():
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def source_fetchers(cfg):
    """Yield (source_key, org_label, jobs_list_or_exception)."""

    # Greenhouse
    for org in (cfg.get("sources", {}) or {}).get("greenhouse_orgs", []) or []:
        try:
            jobs = fetch_greenhouse(org)
            yield ("greenhouse", org, jobs, None)
        except Exception as e:
            yield ("greenhouse", org, [], e)

    # Lever
    for org in (cfg.get("sources", {}) or {}).get("lever_orgs", []) or []:
        try:
            jobs = fetch_lever(org)
            yield ("lever", org, jobs, None)
        except Exception as e:
            yield ("lever", org, [], e)

    # Ashby
    for org in (cfg.get("sources", {}) or {}).get("ashby_orgs", []) or []:
        try:
            jobs = fetch_ashby(org)
            yield ("ashby", org, jobs, None)
        except Exception as e:
            yield ("ashby", org, [], e)

    # Workday
    for tenant in (cfg.get("sources", {}) or {}).get("workday_tenants", []) or []:
        try:
            jobs = fetch_workday(tenant)
            label = tenant.get("company") or tenant.get("tenant") or "workday"
            yield ("workday", label, jobs, None)
        except Exception as e:
            label = tenant.get("company") or tenant.get("tenant") or "workday"
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
    load_dotenv()
    cfg = load_config()

    # env first; if you prefer config.notify, you can add fallback from cfg
    bot = os.getenv("TELEGRAM_BOT_TOKEN") or (cfg.get("notify", {}) or {}).get("telegram_bot_token")
    chat = os.getenv("TELEGRAM_CHAT_ID") or (cfg.get("notify", {}) or {}).get("telegram_chat_id")

    # if filters are nested under "filters:", use that; else use top-level keys
    filters_cfg = cfg.get("filters") or cfg

    conn = get_conn()
    new_items = []
    fetched_counts = {}   # e.g., {"greenhouse:duolingo": 74}
    errors = []

    # Fetch, filter, insert
    for src, org, jobs, err in source_fetchers(cfg):
        key = f"{src}:{org}"
        if err:
            print(f"[warn] {key}: {err}")
            errors.append(f"⚠️ {key}: {err}")
            fetched_counts[key] = 0
            continue

        print(f"[debug] {key}: fetched {len(jobs)}")
        fetched_counts[key] = len(jobs)

        for j in jobs:
            try:
                if match_job(j, filters_cfg) and insert_if_new(conn, j):
                    new_items.append(j)
            except Exception as e:
                # never let one bad post break the run
                print(f"[warn] filter/insert failed for {key}: {e}")

    # --- Build summary & send heartbeat / results ---
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    fetched_total = sum(fetched_counts.values())
    header = f"📣 JobWatch @ {ts}\nFetched: {fetched_total} | New matches: {len(new_items)}"

    # Sort new items for readability (title then company)
    new_items.sort(key=lambda x: (x.get("title","").lower(), x.get("company","").lower()))

    lines = []

    # Per-source counts
    if fetched_counts:
        lines.append("🗂️ Sources:")
        for k, v in sorted(fetched_counts.items()):
            lines.append(f"  - {k}: {v}")
    else:
        lines.append("🗂️ Sources: none")

    # New jobs list (trim to 25 to keep message short)
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

    # Errors, if any
    if errors:
        lines.append("")
        lines.append("⚠️ Errors:")
        lines.extend(errors)

    # Console print (helps during dev)
    print(header)
    for line in lines:
        print(line)

    # Telegram (single compact summary; chunk if needed)
    chunk_and_send(bot, chat, header, lines)


if __name__ == "__main__":
    run()
