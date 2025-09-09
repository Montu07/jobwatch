import os
import yaml
from datetime import datetime
from dotenv import load_dotenv

from db import get_conn, insert_if_new
from utils.filters import match_job
from sources.greenhouse import fetch_greenhouse
from sources.lever import fetch_lever
from notify.telegram import send_telegram


TELEGRAM_MAX = 3800  # keep under Telegram's ~4096 message limit with some buffer


def load_config():
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def source_fetchers(cfg):
    """Yield (source_key, org, jobs_list_or_exception)."""
    # Greenhouse
    for org in cfg.get("sources", {}).get("greenhouse_orgs", []):
        try:
            jobs = fetch_greenhouse(org)
            yield ("greenhouse", org, jobs, None)
        except Exception as e:
            yield ("greenhouse", org, [], e)

    # Lever
    for org in cfg.get("sources", {}).get("lever_orgs", []):
        try:
            jobs = fetch_lever(org)
            yield ("lever", org, jobs, None)
        except Exception as e:
            yield ("lever", org, [], e)


def format_job_line(j):
    loc = j.get("location") or ""
    title = j.get("title") or ""
    company = j.get("company") or ""
    url = j.get("url") or ""
    return f"• {title} @ {company} — {loc}\n  {url}"


def chunk_and_send(bot, chat, header, lines):
    """Send one compact summary; if too long, send in chunks."""
    if not bot or not chat:
        return

    body = "\n".join(lines)
    msg = f"{header}\n{body}" if lines else header

    if len(msg) <= TELEGRAM_MAX:
        send_telegram(bot, chat, msg)
        return

    # Split into multiple messages respecting limit
    send_telegram(bot, chat, header)
    buf = []
    cur = 0
    for line in lines:
        if cur + len(line) + 1 > TELEGRAM_MAX:
            send_telegram(bot, chat, "\n".join(buf))
            buf = [line]
            cur = len(line) + 1
        else:
            buf.append(line)
            cur += len(line) + 1
    if buf:
        send_telegram(bot, chat, "\n".join(buf))


def run():
    load_dotenv()
    cfg = load_config()

    bot = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")

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
            if match_job(j, cfg) and insert_if_new(conn, j):
                new_items.append(j)

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
