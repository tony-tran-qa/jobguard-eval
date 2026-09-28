"""Unit tests for the harness plumbing. No API calls: the Anthropic client is mocked.

Run:  pytest            (unit tests only, free)
      pytest -m live    (live eval against the real API, costs ~$0.05)
"""
import json
import os
import types

import pytest

import classify
import eval_batch


# ---------- fake Anthropic client ----------
class FakeMessages:
    def __init__(self, text):
        self.text, self.calls = text, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = types.SimpleNamespace(type="text", text=self.text)
        usage = types.SimpleNamespace(input_tokens=100, output_tokens=50)
        return types.SimpleNamespace(content=[block], usage=usage)


@pytest.fixture
def fake_client(monkeypatch):
    def install(text):
        fm = FakeMessages(text)
        monkeypatch.setattr(classify, "client", types.SimpleNamespace(messages=fm))
        return fm
    return install


# ---------- build_prompt ----------
def test_prompt_contains_company_role_and_url():
    p = classify.build_prompt("Acme", "QA", "https://acme.com")
    assert 'Company: "Acme"' in p and 'Role: "QA"' in p and 'Homepage URL: "https://acme.com"' in p
    assert "Analyze this company and role" in p


def test_prompt_omits_role_and_url_lines_when_empty():
    p = classify.build_prompt("Acme")
    assert "Role:" not in p and "Homepage URL:" not in p
    assert "Analyze this company thoroughly" in p


def test_prompt_includes_current_rules():
    p = classify.build_prompt("Acme")
    assert "no internet access" in p
    assert "Not recognizing a company is NOT evidence of fraud" in p
    assert "must be AVOID, not CAUTION" in p


# ---------- vet(): parsing ----------
def test_vet_parses_json_wrapped_in_extra_text(fake_client):
    fm = fake_client('Sure! {"riskLevel": "LOW", "recommendation": "APPLY", "verdict": "ok"} Hope that helps.')
    r = classify.vet("Acme", "QA", "")
    assert r["recommendation"] == "APPLY"
    assert r["_usage"] == {"input_tokens": 100, "output_tokens": 50}
    assert fm.calls[0]["model"] == classify.MODEL and fm.calls[0]["max_tokens"] == classify.MAX_TOKENS


def test_vet_raises_when_no_json(fake_client):
    fake_client("I cannot help with that.")
    with pytest.raises(ValueError):
        classify.vet("Acme")


def test_vet_raises_on_malformed_json(fake_client):
    fake_client('{"recommendation": "APPLY",}')
    with pytest.raises(json.JSONDecodeError):
        classify.vet("Acme")


# ---------- .env loader ----------
def test_dotenv_does_not_override_existing_key(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "already-set")
    classify._load_dotenv()
    assert os.environ["ANTHROPIC_API_KEY"] == "already-set"


# ---------- scoring (AVOID = positive class) ----------
ROWS = [{"id": "1", "expected": "AVOID"}, {"id": "2", "expected": "AVOID"},
        {"id": "3", "expected": "APPLY"}, {"id": "4", "expected": "APPLY"}]


def test_score_perfect():
    s = eval_batch.score(ROWS, {"1": "AVOID", "2": "AVOID", "3": "APPLY", "4": "APPLY"})
    assert s["recall"] == 1.0 and s["fpr"] == 0.0 and s["precision"] == 1.0


def test_score_caution_on_scam_is_a_miss():
    s = eval_batch.score(ROWS, {"1": "AVOID", "2": "CAUTION", "3": "APPLY", "4": "APPLY"})
    assert s["recall"] == 0.5 and s["fn"] == 1


def test_score_caution_on_legit_is_not_a_false_positive():
    s = eval_batch.score(ROWS, {"1": "AVOID", "2": "AVOID", "3": "CAUTION", "4": "APPLY"})
    assert s["fpr"] == 0.0 and s["legit_caution"] == 1


def test_score_avoid_on_legit_is_a_false_positive():
    s = eval_batch.score(ROWS, {"1": "AVOID", "2": "AVOID", "3": "AVOID", "4": "APPLY"})
    assert s["fpr"] == 0.5 and s["precision"] == pytest.approx(2 / 3)


def test_score_error_counts_as_miss_on_scam():
    s = eval_batch.score(ROWS, {"1": "ERROR", "2": "AVOID", "3": "APPLY", "4": "APPLY"})
    assert s["fn"] == 1


# ---------- hallucinated-lookup detector ----------
@pytest.mark.parametrize("text,expected", [
    ("Company returns no legitimate business results", 1),
    ("not found in any database", 1),
    ("Uses a lookalike domain typical of brand impersonation", 0),
])
def test_lookup_claim_detector(text, expected):
    assert (eval_batch.lookup_claims({"redFlags": [text]}) > 0) == bool(expected)


# ---------- dataset integrity ----------
@pytest.mark.parametrize("path", ["data/golden.jsonl", "data/holdout.jsonl"])
def test_dataset_rows_are_valid(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for r in rows:
        assert r["expected"] in {"APPLY", "AVOID"}, r["id"]
        assert r["company"].strip(), r["id"]


# ---------- live eval (real API, opt-in) ----------
@pytest.mark.live
def test_live_golden_meets_pass_criteria():
    rows = [json.loads(l) for l in open("data/golden.jsonl", encoding="utf-8") if l.strip()]
    verdicts = {r["id"]: classify.vet(r["company"], r["role"], r["url"])["recommendation"] for r in rows}
    s = eval_batch.score(rows, verdicts)
    assert s["recall"] == 1.0, f"missed scams: {s}"
    assert s["fpr"] == 0.0, f"legit companies flagged AVOID: {s}"