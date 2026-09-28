"""run_eval.py - run every company in data/golden.jsonl through JobGuard's prompt.

Usage:  python run_eval.py
Prints expected vs. actual per row, then a summary. One API call per row.
Also saves each run to results/run_<timestamp>.txt (table) and .json (full data),
so results can be reviewed later without copying terminal output.
"""
import datetime
import json
import pathlib

from classify import PROMPT_VERSION, MODEL, vet

DATASET = "data/golden.jsonl"
RESULTS_DIR = pathlib.Path("results")


def main():
    with open(DATASET, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    lines, records = [], []

    def out(text=""):
        print(text)
        lines.append(text)

    out(f"Run {stamp} | prompt {PROMPT_VERSION} | model {MODEL} | {len(rows)} rows")
    out(f"{'ID':<5}{'EXPECTED':<10}{'ACTUAL':<10}{'RESULT':<8}COMPANY")
    out("-" * 70)
    matches, errors = 0, 0
    for r in rows:
        result = {}
        try:
            result = vet(r["company"], r.get("role", ""), r.get("url", ""))
            actual = result["recommendation"]
        except Exception as e:  # keep going if one call fails
            actual, errors = "ERROR", errors + 1
            out(f"   ! {r['id']} failed: {e}")
        ok = actual == r["expected"]
        matches += ok
        out(f"{r['id']:<5}{r['expected']:<10}{actual:<10}{'PASS' if ok else 'MISS':<8}{r['company']}")
        records.append({**r, "actual": actual, "pass": ok, "response": result})

    out("-" * 70)
    out(f"{matches}/{len(rows)} matched ({matches / len(rows):.0%}), {errors} errors")

    RESULTS_DIR.mkdir(exist_ok=True)
    base = RESULTS_DIR / f"run_{stamp}"
    base.with_suffix(".txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    base.with_suffix(".json").write_text(
        json.dumps({"stamp": stamp, "prompt_version": PROMPT_VERSION, "model": MODEL,
                    "matched": matches, "total": len(rows), "errors": errors,
                    "rows": records}, indent=2), encoding="utf-8")
    print(f"\nSaved: {base}.txt and {base}.json")


if __name__ == "__main__":
    main()