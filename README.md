# Daily Dev Journal

A short "Today I learned" note every day, written by a GitHub Actions workflow, on full-stack,
AI/LLM/RAG, FastAPI, React, Android, Git, system design, security and automation topics.

Each entry is 120-180 words with a small code snippet. If a `GEMINI_API_KEY` secret is set, Gemini
writes the entry. If the key is missing or the call fails for any reason, the script builds an
offline entry from the facts in `topics.json`, so the workflow does not fail.

## Latest entries

<!-- JOURNAL:START -->
**Current streak:** 0 day(s) · **Total entries:** 0

_No entries yet. The first one lands after the workflow runs._
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
