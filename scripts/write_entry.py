#!/usr/bin/env python3
"""Write today's dev-journal entry and refresh the README index.

Stdlib only. Uses Gemini when GEMINI_API_KEY is set; otherwise (or on any
failure) falls back to an offline entry built from topics.json, so the
scheduled workflow never fails because of the LLM.

Env vars:
  GEMINI_API_KEY  optional; enables LLM-written entries (never logged)
  GEMINI_MODEL    optional; default "gemini-2.5-flash"
  START_DATE      optional; overrides topics.json "start_date" (YYYY-MM-DD)
  JOURNAL_DATE    optional; force the entry date (YYYY-MM-DD), for testing
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOPICS_FILE = ROOT / "topics.json"
JOURNAL_DIR = ROOT / "journal"
README = ROOT / "README.md"
START_MARK = "<!-- JOURNAL:START -->"
END_MARK = "<!-- JOURNAL:END -->"
IST = timezone(timedelta(hours=5, minutes=30))
HEADER_RE = re.compile(r"^# Day (\d+) · (\d{4}-\d{2}-\d{2}) · (.+)$")


def today() -> date:
    forced = os.environ.get("JOURNAL_DATE", "").strip()
    if forced:
        return date.fromisoformat(forced)
    return datetime.now(IST).date()


def load_config() -> dict:
    return json.loads(TOPICS_FILE.read_text(encoding="utf-8"))


def day_number(cfg: dict, d: date) -> int:
    start = os.environ.get("START_DATE", "").strip() or cfg.get("start_date") or d.isoformat()
    return max(1, (d - date.fromisoformat(start)).days + 1)


def offline_body(topic: dict) -> str:
    facts = topic["facts"]
    lines = [
        f"Today I revisited **{topic['title']}** ({topic['category']}).",
        "",
        *[f"- {fact}" for fact in facts],
        "",
        f"```{topic['lang']}",
        topic["snippet"],
        "```",
        "",
        f"Takeaway: {facts[0]}",
    ]
    return "\n".join(lines)


def gemini_body(topic: dict, api_key: str) -> str | None:
    model = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = (
        f"Write a 'Today I learned' developer journal entry about: {topic['title']} "
        f"({topic['category']}). 120-180 words, first person, practical and specific. "
        "Include exactly one tiny fenced code snippet (max 8 lines) with a language tag. "
        "Markdown only. Do NOT include a top-level heading or a title line. "
        f"Useful facts you may build on: {' '.join(topic['facts'])}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
    }).encode("utf-8")
    # Key goes in a header, not the query string, so it can't leak via URLs in error text.
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except urllib.error.HTTPError as exc:
        print(f"Gemini HTTP {exc.code}; using offline entry.")
        return None
    except Exception as exc:  # network, JSON, missing fields, timeouts
        print(f"Gemini failed ({type(exc).__name__}); using offline entry.")
        return None
    # Drop any heading the model added anyway, and sanity-check length.
    text = "\n".join(l for l in text.splitlines() if not l.startswith("# ")).strip()
    if len(text.split()) < 60:
        print("Gemini reply too short; using offline entry.")
        return None
    return text


def entry_path(d: date) -> Path:
    return JOURNAL_DIR / f"{d:%Y}" / f"{d:%m}" / f"{d.isoformat()}.md"


def write_entry(cfg: dict, d: date) -> tuple[Path, int, str, bool]:
    n = day_number(cfg, d)
    topics = cfg["topics"]
    topic = topics[(n - 1) % len(topics)]
    path = entry_path(d)
    if path.exists():
        m = HEADER_RE.match(path.read_text(encoding="utf-8").splitlines()[0])
        title = m.group(3) if m else topic["title"]
        print(f"Entry already exists for {d}: {path.relative_to(ROOT).as_posix()} (no change)")
        return path, n, title, False

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    body, source = None, "offline"
    if key:
        body = gemini_body(topic, key)
        if body:
            source = "gemini"
    else:
        print("GEMINI_API_KEY not set; using offline entry.")
    if not body:
        body = offline_body(topic)

    content = (
        f"# Day {n} · {d.isoformat()} · {topic['title']}\n\n"
        f"_Category: {topic['category']} · Source: {source}_\n\n"
        f"{body}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Wrote {path.relative_to(ROOT).as_posix()} (Day {n}, {topic['title']}, {source})")
    return path, n, topic["title"], True


def collect_entries() -> list[tuple[int, date, str, Path]]:
    entries = []
    for p in JOURNAL_DIR.glob("*/*/*.md"):
        first = p.read_text(encoding="utf-8").splitlines()[:1]
        m = HEADER_RE.match(first[0]) if first else None
        if m:
            entries.append((int(m.group(1)), date.fromisoformat(m.group(2)), m.group(3), p))
    entries.sort(key=lambda e: e[1], reverse=True)
    return entries


def current_streak(entries, d: date) -> int:
    dates = {e[1] for e in entries}
    # Count back from today (or yesterday, if today's entry isn't written yet).
    cur = d if d in dates else d - timedelta(days=1)
    streak = 0
    while cur in dates:
        streak += 1
        cur -= timedelta(days=1)
    return streak


def update_readme(d: date) -> bool:
    entries = collect_entries()
    lines = [
        START_MARK,
        f"**Current streak:** {current_streak(entries, d)} day(s) · **Total entries:** {len(entries)}",
        "",
    ]
    if entries:
        lines.append("| Day | Date | Topic |")
        lines.append("|---:|---|---|")
        for n, ed, title, p in entries[:7]:
            rel = p.relative_to(ROOT).as_posix()
            lines.append(f"| {n} | {ed.isoformat()} | [{title}]({rel}) |")
    else:
        lines.append("_No entries yet. The first one lands after the workflow runs._")
    lines.append(END_MARK)
    block = "\n".join(lines)

    text = README.read_text(encoding="utf-8")
    if START_MARK not in text or END_MARK not in text:
        text = text.rstrip() + "\n\n## Latest entries\n\n" + START_MARK + "\n" + END_MARK + "\n"
    pattern = re.compile(re.escape(START_MARK) + r".*?" + re.escape(END_MARK), re.S)
    new = pattern.sub(lambda _: block, text, count=1)
    if new != text:
        README.write_text(new, encoding="utf-8", newline="\n")
        print("README updated.")
        return True
    print("README unchanged.")
    return False


def main() -> int:
    cfg = load_config()
    d = today()
    _, n, title, _ = write_entry(cfg, d)
    update_readme(d)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"day={n}\n")
            fh.write(f"title={title}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
