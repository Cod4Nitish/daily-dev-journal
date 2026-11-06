# Daily Dev Journal

A short "Today I learned" note every day, written by a GitHub Actions workflow, on full-stack,
AI/LLM/RAG, FastAPI, React, Android, Git, system design, security and automation topics.

Each entry is 120-180 words with a small code snippet. If a `GEMINI_API_KEY` secret is set, Gemini
writes the entry. If the key is missing or the call fails for any reason, the script builds an
offline entry from the facts in `topics.json`, so the workflow does not fail.

## Latest entries

<!-- JOURNAL:START -->
**Current streak:** 4 day(s) · **Total entries:** 4

| Day | Date | Topic |
|---:|---|---|
| 3 | 2026-11-06 | [Pydantic v2 validators](journal/2026/11/2026-11-06.md) |
| 2 | 2026-11-05 | [FastAPI background tasks](journal/2026/11/2026-11-05.md) |
| 1 | 2026-11-04 | [FastAPI dependency injection](journal/2026/11/2026-11-04.md) |
| 1 | 2026-11-03 | [FastAPI dependency injection](journal/2026/11/2026-11-03.md) |
<!-- JOURNAL:END -->

## How it works

- `.github/workflows/daily-journal.yml` runs every day at 03:30 UTC (09:00 IST), and you can also
  start it by hand from the Actions tab (`workflow_dispatch`).
- `scripts/write_entry.py` (Python standard library only) works out the day number from
  `start_date` in `topics.json`, picks the next topic in the rotation, and writes
  `journal/YYYY/MM/YYYY-MM-DD.md`. Then it rebuilds the block above with the streak and the
  7 latest entries.
- Running it twice on the same day changes nothing, because an existing entry for today is
  never rewritten. If nothing changed, the workflow skips the commit.
- Commits are authored as `Nitish Singh <theeditornitish@gmail.com>`.

## Setup

1. Create a **public** GitHub repo (not a fork) and push this folder to it. `setup.ps1` does this
   with `gh`: `./setup.ps1 -RepoName daily-dev-journal`.
2. Add the secret: **Settings → Secrets and variables → Actions → New repository secret**, with
   the name `GEMINI_API_KEY`. This step is optional, since the offline fallback works without it.
   To use a different model, add a repository *variable* (not a secret) named `GEMINI_MODEL`.
3. Make sure Actions is enabled: **Settings → Actions → General → Allow all actions**. Also
   check that **Workflow permissions** permits read and write, or that the workflow's own
   `permissions: contents: write` is not overridden by an org policy.
4. Run it once: **Actions → Daily dev journal → Run workflow**.

Local run: `python scripts/write_entry.py`. You can set `JOURNAL_DATE=YYYY-MM-DD` to test a
specific date.

## Notes

- **Contribution graph:** commits count only if `theeditornitish@gmail.com` is a **verified** email on
  your GitHub account, the commits are on the default branch (`main`), and the repo is **not a
  fork**. A private repo's commits count only if you turn on "private contributions" in your
  profile settings.
- **Keepalive:** GitHub disables scheduled workflows in public repos after 60 days with no repo
  activity. The daily commits count as activity, so the schedule keeps itself alive. If it does
  get disabled (for example after a long run of failures), re-enable it from the Actions tab.
- **Honesty:** the entries are short, real notes, and the README says plainly that they are
  automated. Read them, edit them, and add your own. The streak means the most when you
  actually learn the thing.

## Year plan, your own notes, and fallbacks

- `topics.json` holds a 365-day plan (rich topics first, then one planned topic per day). The day number comes from `start_date`.
- **Your own thoughts:** add `thoughts/YYYY-MM-DD.md` any time (you can pre-write 30 or 60 days). It is appended to that day's entry under "My note". Or start the workflow by hand and type a note in the `note` box (works from the GitHub phone app).
- **Model fallback:** `GEMINI_MODELS` (repo variable, comma list) is tried in order; default `gemini-3.5-flash,gemini-3.1-flash-lite`. Extra keys `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3` (secrets, ideally from different Google projects) are tried when a key fails. If everything fails the entry is a short offline placeholder, so the day is never skipped.
- Secrets live only in GitHub Actions secrets, never in files.
