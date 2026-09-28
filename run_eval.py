"""run_eval.py - run every company in data/golden.jsonl through JobGuard's prompt.

Usage:  python run_eval.py
Prints expected vs. actual per row, then a summary. One API call per row.
"""
import json

from classify import vet

DATASET = "data/golden.jsonl"


def main():
    with open(DATASET, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    print(f"{'ID':<5}{'EXPECTED':<10}{'ACTUAL':<10}{'RESULT':<8}COMPANY")
    print("-" * 70)
    matches, errors = 0, 0
    for r in rows:
        try:
            actual = vet(r["company"], r.get("role", ""), r.get("url", ""))["recommendation"]
        except Exception as e:  # keep going if one call fails
            actual, errors = "ERROR", errors + 1
            print(f"   ! {r['id']} failed: {e}")
        ok = actual == r["expected"]
        matches += ok
        print(f"{r['id']:<5}{r['expected']:<10}{actual:<10}{'PASS' if ok else 'MISS':<8}{r['company']}")

    print("-" * 70)
    print(f"{matches}/{len(rows)} matched ({matches / len(rows):.0%}), {errors} errors")


if __name__ == "__main__":
    main()