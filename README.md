# JobGuard Eval Harness

An evaluation harness for **JobGuard**, my LLM-powered company-vetting tool. It measures how accurately and consistently JobGuard's prompt classifies companies as APPLY, CAUTION, or AVOID.

---

## What this program does

JobGuard asks an LLM (Claude Haiku 4.5) to judge whether a company is safe to apply to, and it answers **APPLY**, **CAUTION**, or **AVOID**. An LLM's answers can be wrong, and they can change from run to run. This harness **tests JobGuard's prompt the way you'd test any system**:

1. **A labeled test set** (`data/golden.jsonl`): companies where I already know the right answer, including real companies, known scam patterns, and hard cases (real brands on fake domains, small companies the model may not know).
2. **The same prompt and model as the app** (`classify.py`), so results reflect what JobGuard users actually get.
3. **A scored run** (`run_eval.py`): every company goes through the model, and each answer is compared with the expected label.

**What it measures:**
- **Recall**: of the real scams, how many were caught (AVOID). A miss here means a user gets scammed.
- **Precision**: of the AVOID verdicts, how many were actually scams. A miss here means a user skips a real job.
- **False-positive rate**: how often a legitimate company is wrongly flagged as a scam.
- **Stability** (Day 2): whether the same company gets the same verdict across repeated runs. LLM output isn't deterministic, so one passing run doesn't prove much.

**Why it exists:** to show, with numbers, that an AI feature is accurate and consistent before trusting it. This is the core skill of testing non-deterministic AI systems.
---

## Quick start (every time you come back)

Open PowerShell and run:
```powershell
cd C:\TNY\jobguard-eval
. .\start.ps1
python run_eval.py
```
- `. .\start.ps1` activates the virtual environment and asks for your API key (paste it; nothing shows on screen). **Type the dot and the space in front**, or the settings won't stay in the window.
- `python run_eval.py` runs every company in the dataset and prints a PASS/MISS table plus a score.

That's it. Everything below is reference.

---

## How it works

`classify.py` contains an **exact copy** of JobGuard's `vetCompanyWithAI()` prompt (from `C:\Users\tony_\my-jobguard\src\App.jsx`) and calls the Anthropic API directly with the same model (`claude-haiku-4-5-20251001`) and the same `max_tokens` (900).

**The JobGuard app does NOT need to be running.** No VS Code, no Vite dev server, no browser.

> ⚠ **Keep in sync:** if the prompt or model changes in `App.jsx`, update `classify.py` to match. Otherwise the harness tests an old version of the app.
>
> **Current state:** `classify.py` is on prompt **v2**, one rule *ahead* of `App.jsx` (v1), on purpose. It's an experiment being validated by the eval (see Results log). `PROMPT_VERSION` in `classify.py` shows which version is active.

## Files

| File | What it is |
|---|---|
| `start.ps1` | Activates the venv and sets the API key for this window |
| `classify.py` | JobGuard's prompt plus the `vet()` function (one API call) |
| `run_eval.py` | Runs the whole dataset, prints the PASS/MISS table, and saves the run to `results/` |
| `results/` | One `run_<date>_<time>.txt` (the table) and `.json` (full model responses) per run, including prompt version and model |
| `data/golden.jsonl` | The labeled test companies (the ground truth) |
| `requirements.txt` | Python packages to install |
| `.gitignore` | Keeps `.venv`, cache files, and keys out of Git |

## All commands

| Task | Command |
|---|---|
| Get the window ready | `. .\start.ps1` |
| Smoke test (1 call) | `python classify.py` |
| Full run (1 call per row) | `python run_eval.py` |
| Vet one company by hand | `python -c "from classify import vet; print(vet('Shopify', 'QA', 'https://shopify.com'))"` |
| Original one-line full run | `python -c "import json; from classify import vet; [print(r['id'], r['expected'], vet(r['company'], r['role'], r['url'])['recommendation']) for r in map(json.loads, open('data/golden.jsonl', encoding='utf-8'))]"` |
| Check the key is set (safely) | `$env:ANTHROPIC_API_KEY.Substring(0,10) + "..."` |
| Leave the venv | `deactivate` |

Expected smoke-test output: `LOW APPLY - Anthropic is a legitimate...`

## Dataset: `data/golden.jsonl`

One company per line:
```json
{"id": "001", "company": "Anthropic", "role": "SDET", "url": "https://anthropic.com", "expected": "APPLY", "note": "why this label"}
```
- `expected` is the ground truth: **APPLY** or **AVOID** only (CAUTION is too fuzzy to label).
- Includes hard cases: small real companies with no URL, and real brands on fake or lookalike domains.
- To add a row: copy a line, give it the next `id`, and set your own `expected`. Labels are my (QT's) judgment, not the model's.

## First-time setup (new PC, or if .venv gets deleted)

```powershell
cd C:\TNY\jobguard-eval
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If activation fails with "running scripts is disabled," run this once, then retry:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## API key

- Created in the Claude Console: https://platform.claude.com/dashboard → **Get API key → Create key**. It's shown only once.
- `start.ps1` sets it for the current window only. **Never** use `setx`: a permanent key makes Claude Code bill the API instead of your Pro plan.
- Keys expire (mine is set to 30 days). When expired, you get a 401 error. Create a new key.
- Full guide: `C:\TNY\A02_TECH_DOCS\HOWTO-claude-api-keys.html`

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `401 invalid x-api-key` | Placeholder text pasted, or key expired | Run `. .\start.ps1` again with the real key |
| `401` in a new window | Key only lives in the window where it was set | Run `. .\start.ps1` |
| `No module named anthropic` | venv not active | Run `. .\start.ps1` (prompt should show `(.venv)`) |
| Credit or billing error | Console balance is $0 | Console → Settings → Billing, add a small amount |
| Red `NativeCommandError` text after pip or git | Tools write notices to the error stream | Not a real error if the output says it succeeded |
| `LF will be replaced by CRLF` | Git line-ending notice | Harmless; already silenced with `core.autocrlf true` |

## Save your work (Git)

```powershell
git status
git add .
git commit -m "describe what changed"
```
`.gitignore` keeps `.venv` and keys out automatically. Before pushing to GitHub for the first time, run `git branch -M main`.

## Running the JobGuard app itself (separate project)

Only needed if you want to use the app, not for the harness:
```powershell
cd C:\Users\tony_\my-jobguard
npm install      # first time only
npm run dev      # starts the app; open the local URL it prints
```
The app stores its API key and records in the browser, not in this folder.

## Cost

Haiku 4.5 is about $0.0025 per call, so a 20-row run costs about 5 cents. Credits are prepaid in the Claude Console, with auto-reload OFF.

## Results log

### Run 1: Sept 28, 2026 (20 rows, 1 pass, Haiku 4.5)

Raw output:
```
001 APPLY APPLY
002 APPLY APPLY
003 APPLY APPLY
004 APPLY APPLY
005 APPLY APPLY
006 APPLY APPLY
007 APPLY AVOID    <- the only miss
008 APPLY APPLY
009 AVOID AVOID
010 AVOID AVOID
011 AVOID AVOID
012 AVOID AVOID
013 AVOID AVOID
014 AVOID AVOID
015 AVOID AVOID
016 AVOID AVOID
017 AVOID AVOID
018 AVOID AVOID
019 APPLY APPLY
020 AVOID AVOID
```

Score (AVOID = the "scam" class):

| Metric | Result |
|---|---|
| Matched | 19/20 (95%) |
| Recall | 11/11 = 100% (every scam caught) |
| Precision | 11/12 = 92% |
| False-positive rate | 1/9 = 11% |

**Finding:** 007 (Palitronica, a small real Waterloo company, no URL given) was flagged **AVOID**, a false positive. This is the costlier error for a vetting tool, because it tells users to skip a real employer. 008 (Intellijoint, also small with no URL) passed, so "small company" alone doesn't explain it.

**Caveats:** one run of 20 rows. The model is non-deterministic, so this needs repeat runs before drawing conclusions.

**Next:** inspect 007's `redFlags` and `confidenceNote`, rerun it several times for stability, and test it with its real URL to see whether a domain fixes the false positive.

### Run 1 follow-up: 007 repeated 3 times (Sept 28, 2026)

`AVOID, AVOID, AVOID`: a **consistent** failure, not random.

**Root cause** (from 007's full JSON output): the model has no internet access, but its red flags claimed searches it never ran ("returns no legitimate business results," "no verifiable LinkedIn company page"). It treated "I don't know this company" as evidence of fraud, and escalated low confidence to "immediate rejection," which the prompt never asked for. A known LLM failure mode: hallucinated verification.

**Change: prompt v2** (`PROMPT_VERSION = "v2"` in `classify.py`). Added a rule: the model has no web access and must never claim it searched; not recognizing a company is not evidence of fraud; unknown companies with no concrete scam signals get CAUTION ("unverified"); AVOID requires concrete red flags in the name, role, or URL.

> v2 exists only in the harness for now. Port it to `App.jsx` only after the eval shows it fixes 007 without breaking the scam rows.

### Run 2: prompt v2, two full passes (Sept 28, 2026)

Pass criteria: 007 no longer AVOID, and all 11 AVOID rows still caught (recall stays 100%).

007 alone, 3 repeats: `CAUTION, CAUTION, CAUTION` (v1 was `AVOID` 3/3). **False positive fixed.**

| Row | Run 2a (not saved, pasted) | Run 2b (`results/run_20260928_141322`) |
|---|---|---|
| 007 Palitronica (expected APPLY) | CAUTION | CAUTION |
| 009 QuickHire Solutions (expected AVOID) | **CAUTION (miss)** | AVOID |
| 011 Apex Digital Payments (expected AVOID) | **CAUTION (miss)** | **CAUTION (miss)** |
| All other rows | pass | pass |
| Matched | 17/20 | 18/20 |

Score, v1 vs. v2 (AVOID = the "scam" class):

| Metric | v1 (Run 1) | v2 (Run 2a) | v2 (Run 2b) |
|---|---|---|---|
| Recall | 11/11 = 100% | 9/11 = 82% | 10/11 = 91% |
| Precision | 11/12 = 92% | 9/9 = 100% | 10/10 = 100% |
| False-positive rate | 1/9 = 11% | 0/9 = 0% | 0/9 = 0% |

**Findings:**
- **v2 fixed the false positive but over-corrected:** recall dropped. A trade-off, not a free win.
- **011 is a consistent miss (2/2).** The model's own red flags *name* the scam ("role title commonly used in work-from-home scams involving money handling"), yet it chose CAUTION. It recognizes the pattern; v2's decision rule biases it toward CAUTION.
- **009 is unstable:** CAUTION in one run, AVOID in the next. A borderline case where non-determinism decides the verdict, which is exactly what Day 2's repeat-run stability metric is for.
- 007's v2 red flags are softer, but still hint at checks it can't do ("not recognized in public databases"). Worth tightening.

**Next: prompt v3.** Keep the "unknown is not a scam" rule, but define known scam **role patterns** as concrete red flags that require AVOID (money/payment handling, package reshipping, vague data entry, mystery shopper, crypto trading assistant, government impersonation). Then rerun 3 times to measure stability.
**How to read `run_eval.py` output:** each row shows `ID  EXPECTED  ACTUAL  RESULT  COMPANY`. PASS means the model matched my label; MISS means investigate that row. The last line is the overall score.
## Roadmap

- **Day 1:** wrapper, smoke test, golden dataset, first full pass
- **Day 2:** pytest suite with precision, recall, and false-positive rate (AVOID = positive class); run each company 5 times to measure verdict stability
- **Day 3:** GitHub Actions CI gate (fails if recall or stability drops); per-run token cost logging