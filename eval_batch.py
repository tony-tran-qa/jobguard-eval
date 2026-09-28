"""eval_batch.py - run a dataset N times (concurrently), score each repeat, measure stability and cost.

Usage:
    python eval_batch.py                              # golden set, 3 repeats
    python eval_batch.py --dataset data/holdout.jsonl --repeats 3
Scoring (fixed before tuning): AVOID is the positive ("scam") class.
    Scam row + CAUTION/APPLY = miss (false negative). Legit row + AVOID = false positive.
    Legit row + CAUTION is not a false positive, but is counted and reported.
Pass criteria: recall 100% and FPR 0% on EVERY repeat, stability >= 95% of rows.
Saves results/batch_<stamp>_<prompt>_<dataset>.txt and .json
"""
import argparse, collections, concurrent.futures as cf, datetime, json, pathlib, time

from classify import MODEL, PROMPT_VERSION, vet

import re
LOOKUP_CLAIM = re.compile(r"search(ed)? results|no (legitimate )?results|returns no|database|registr|directory|no verifiable linkedin|glassdoor|crunchbase|whois", re.I)


def lookup_claims(res):
    """Count phrases implying the model looked something up (it has no internet access)."""
    text = " ".join([str(res.get("verdict", ""))] + [str(x) for x in res.get("redFlags", [])] + [str(res.get("confidenceNote", ""))])
    return len(LOOKUP_CLAIM.findall(text))


PRICE_IN, PRICE_OUT = 1.0, 5.0   # USD per million tokens, Haiku 4.5 (third-party trackers; not confirmed on Anthropic's page)


def call(row, rep):
    for attempt in range(3):
        try:
            res = vet(row["company"], row.get("role", ""), row.get("url", ""))
            return row["id"], rep, res
        except Exception as e:
            err = e
            time.sleep(2 * (attempt + 1))
    return row["id"], rep, {"recommendation": "ERROR", "error": str(err)}


def score(rows, verdicts):
    tp = fn = fp = tn = legit_caution = 0
    for r in rows:
        v = verdicts[r["id"]]
        if r["expected"] == "AVOID":
            tp += v == "AVOID"; fn += v != "AVOID"
        else:
            fp += v == "AVOID"; tn += v != "AVOID"; legit_caution += v == "CAUTION"
    recall = tp / (tp + fn) if tp + fn else 1.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    prec = tp / (tp + fp) if tp + fp else 1.0
    return dict(tp=tp, fn=fn, fp=fp, tn=tn, recall=recall, fpr=fpr, precision=prec, legit_caution=legit_caution)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/golden.jsonl")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.dataset, encoding="utf-8") if l.strip()]
    jobs = [(r, k) for k in range(a.repeats) for r in rows]
    out = collections.defaultdict(dict)
    usage_in = usage_out = 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for rid, rep, res in ex.map(lambda j: call(*j), jobs):
            out[rep][rid] = res
            u = res.get("_usage", {}); usage_in += u.get("input_tokens", 0); usage_out += u.get("output_tokens", 0)

    per_rep = [score(rows, {rid: out[k][rid].get("recommendation") for rid in out[k]}) for k in range(a.repeats)]
    stable = [r for r in rows if len({out[k][r["id"]].get("recommendation") for k in range(a.repeats)}) == 1]
    stability = len(stable) / len(rows)
    cost = usage_in / 1e6 * PRICE_IN + usage_out / 1e6 * PRICE_OUT
    passed = all(s["recall"] == 1.0 and s["fpr"] == 0.0 for s in per_rep) and stability >= 0.95

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = pathlib.Path(a.dataset).stem
    L = [f"Batch {stamp} | prompt {PROMPT_VERSION} | {MODEL} | {name} | {len(rows)} rows x {a.repeats} repeats",
         f"{'ID':<5}{'EXPECTED':<9}" + "".join(f"R{k+1:<9}" for k in range(a.repeats)) + "STABLE  COMPANY"]
    for r in rows:
        vs = [out[k][r["id"]].get("recommendation") for k in range(a.repeats)]
        flag = "yes" if r in stable else "NO"
        miss = any((r["expected"] == "AVOID") != (v == "AVOID") for v in vs)
        L.append(f"{r['id']:<5}{r['expected']:<9}" + "".join(f"{v:<10}" for v in vs) + f"{flag:<8}{r['company']}" + ("   <-- MISS" if miss else ""))
    L.append("-" * 78)
    for k, s in enumerate(per_rep):
        L.append(f"R{k+1}: recall {s['tp']}/{s['tp']+s['fn']} = {s['recall']:.0%} | FPR {s['fp']}/{s['fp']+s['tn']} = {s['fpr']:.0%} | "
                 f"precision {s['precision']:.0%} | legit CAUTION {s['legit_caution']}")
    L.append(f"Stability: {len(stable)}/{len(rows)} rows identical across repeats = {stability:.0%}")
    lc = sum(1 for k in range(a.repeats) for r in rows if lookup_claims(out[k][r["id"]]))
    L.append(f"Hallucinated-lookup claims: {lc}/{len(jobs)} responses (quality check, not a pass criterion)")
    L.append(f"Tokens: {usage_in} in / {usage_out} out | est. cost ${cost:.3f} ({len(jobs)} calls)")
    L.append(f"PASS CRITERIA MET: {'YES' if passed else 'NO'}  (recall 100% + FPR 0% every repeat, stability >= 95%)")
    print("\n".join(L))

    pathlib.Path("results").mkdir(exist_ok=True)
    base = pathlib.Path("results") / f"batch_{stamp}_{PROMPT_VERSION}_{name}"
    base.with_suffix(".txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    base.with_suffix(".json").write_text(json.dumps({"stamp": stamp, "prompt_version": PROMPT_VERSION, "model": MODEL,
        "dataset": a.dataset, "repeats": a.repeats, "per_repeat": per_rep, "stability": stability, "passed": passed,
        "tokens_in": usage_in, "tokens_out": usage_out, "est_cost_usd": cost,
        "responses": {str(k): out[k] for k in range(a.repeats)}}, indent=2), encoding="utf-8")
    print(f"Saved: {base}.txt/.json")


if __name__ == "__main__":
    main()