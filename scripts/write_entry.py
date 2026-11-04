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
    facts = topic.get("facts")
    if not facts or not topic.get("snippet"):
        return "\n".join([
            f"Today's focus: **{topic['title']}** ({topic['category']}).",
            "",
            "No AI-written entry today (the generator was unavailable), so this is a short placeholder.",
            "I will revisit this topic and add notes when I have time.",
        ])
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


DEFAULT_MODELS = "gemini-3.5-flash,gemini-3.1-flash-lite"


def model_chain() -> list[str]:
    """Models to try in order. GEMINI_MODELS (comma list) wins, then the old GEMINI_MODEL."""
    raw = os.environ.get("GEMINI_MODELS", "").strip() or os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODELS
    return [m.strip() for m in raw.split(",") if m.strip()]


def api_keys() -> list[str]:
    """GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3 ... (use keys from different Google projects)."""
    names = ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 6)]
    return [v for v in (os.environ.get(n, "").strip() for n in names) if v]


def gemini_body(topic: dict, api_key: str, model: str) -> str | None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = (
        f"Write a 'Today I learned' developer journal entry about: {topic['title']} "
        f"({topic['category']}). 120-180 words, first person, practical and specific. "
        "Include exactly one tiny fenced code snippet (max 8 lines) with a language tag. "
        "Markdown only. Do NOT include a top-level heading or a title line. "
        f"Useful facts you may build on: {' '.join(topic.get('facts') or [])}"
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
        with urllib.request.urlopen(req, timeout=45) as resp:
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


THOUGHTS_DIR = ROOT / "thoughts"
NOTE_MARK = "<!-- my-note -->"


def thought_path(d: date) -> Path:
    return THOUGHTS_DIR / f"{d.isoformat()}.md"


def save_input_note(d: date) -> None:
    """A note typed into the workflow_dispatch form (e.g. from the GitHub phone app)."""
    note = os.environ.get("JOURNAL_NOTE", "").strip()
    if not note:
        return
    p = thought_path(d)
    p.parent.mkdir(parents=True, exist_ok=True)
    old = p.read_text(encoding="utf-8").rstrip() + "\n\n" if p.exists() else ""
    p.write_text(old + note + "\n", encoding="utf-8", newline="\n")
    print(f"Saved note to {p.relative_to(ROOT).as_posix()}")


def apply_thoughts(path: Path, d: date) -> bool:
    """Append the owner's own note for this date (thoughts/YYYY-MM-DD.md) once."""
    tp = thought_path(d)
    if not tp.exists() or not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    note = tp.read_text(encoding="utf-8").strip()
    if not note or NOTE_MARK in text:
        return False
    path.write_text(text.rstrip() + f"\n\n{NOTE_MARK}\n## My note\n\n{note}\n", encoding="utf-8", newline="\n")
    print("Added owner note to entry.")
    return True


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

    keys = api_keys()
    body, source = None, "offline"
    if keys:
        # Try every model on key 1, then key 2, ... (a failed key or retired model just moves on).
        for ki, key in enumerate(keys, 1):
            for model in model_chain():
                print(f"Trying key #{ki}, model {model} ...")
                body = gemini_body(topic, key, model)
                if body:
                    source = "gemini"
                    break
            if body:
                break
    else:
        print("No GEMINI_API_KEY set; using offline entry.")
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
    save_input_note(d)
    path, n, title, _ = write_entry(cfg, d)
    apply_thoughts(path, d)
    update_readme(d)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"day={n}\n")
            fh.write(f"title={title}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
