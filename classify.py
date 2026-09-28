"""JobGuard eval harness - wrapper around JobGuard's company-vetting prompt.

Prompt text mirrors vetCompanyWithAI() in my-jobguard/src/App.jsx exactly.
If you change the prompt in App.jsx, change it here too.
"""
import json
import pathlib
import re

import anthropic

MODEL = "claude-haiku-4-5-20251001"   # same model as App.jsx
MAX_TOKENS = 900                      # same as App.jsx
PROMPT_VERSION = "v3"                 # v1 = App.jsx copy; v2 = unknown-is-not-scam; v3 = + scam-role patterns force AVOID

def _load_dotenv(path=".env"):
    """Load KEY=VALUE lines from a local .env file (git-ignored) into os.environ,
    without overriding a key that is already set in the environment."""
    import os
    f = pathlib.Path(__file__).with_name(path)
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_dotenv()
client = anthropic.Anthropic()        # reads ANTHROPIC_API_KEY from the environment (or .env)

JSON_SPEC = """Reply with ONLY raw JSON (no markdown fences, no extra text):
{
  "riskLevel": "LOW" | "MEDIUM" | "HIGH",
  "recommendation": "APPLY" | "CAUTION" | "AVOID",
  "verdict": "one concise sentence summarizing legitimacy",
  "redFlags": ["up to 3 specific red flags"],
  "greenFlags": ["up to 3 specific green flags"],
  "verificationSteps": ["step1", "step2", "step3"],
  "companyType": "e.g. Software / SaaS, Staffing Agency, Financial Services, Healthcare, Retail, Manufacturing, Consulting, etc.",
  "ownership": "Public" | "Private" | "Non-Profit" | "Government" | "Unknown",
  "headcount": "e.g. 1-10, 11-50, 51-200, 201-500, 501-1000, 1001-5000, 5001-10000, 10000+, or Unknown",
  "annualRevenue": "e.g. <$1M, $1M-$10M, $10M-$50M, $50M-$200M, $200M-$1B, $1B-$10B, $10B+, or Unknown",
  "founded": "year founded or Unknown",
  "headquarters": "City, Country or Unknown",
  "confidenceNote": "brief note on data confidence, e.g. Well-known public company \u2014 data reliable or Limited public info \u2014 estimates only"
}"""


# v2 rule: added after Run 1 false positive (Palitronica flagged AVOID 3/3 because the
# model treated "I don't know this company" as evidence of fraud and claimed searches it never ran).
# v3: v2 over-corrected (recall 82-91%): the model named money-handling scam patterns as red flags
# yet still chose CAUTION. v3 makes recognized scam patterns decisive, and bans database/search claims.
UNKNOWN_RULE = (
    "\nYou have no internet access and cannot search. Never claim you searched, looked anything up, "
    "or that a company is missing from any database, registry, directory, or search result."
    "\nNot recognizing a company is NOT evidence of fraud. If you do not recognize the company and the "
    "role and URL show no concrete scam signals, use riskLevel MEDIUM and recommendation CAUTION, and say "
    "it is unverified."
    "\nThese are concrete scam signals, and any ONE of them requires riskLevel HIGH and recommendation AVOID, "
    "even if the company is unknown: (1) a role that involves receiving, holding, transferring, or processing "
    "money, payments, or checks for the employer; (2) receiving and reshipping packages; (3) vague remote "
    "data-entry or clerical work offered by a generic, unidentifiable company; (4) mystery shopping; "
    "(5) trading or managing cryptocurrency on someone's behalf; (6) impersonating a government agency or a "
    "well-known brand, including a lookalike, typosquatted, cheap-TLD, or free-hosting domain."
    "\nIf you list a red flag that matches one of these signals, your recommendation must be AVOID, not CAUTION."
)

def build_prompt(company: str, role: str = "", url: str = "") -> str:
    url_context = f'\nHomepage URL: "{url}"' if url else ""
    role_line = f'\nRole: "{role}"' if role else ""
    and_role = " and role" if role else ""
    url_rule = ("\nIf a Homepage URL is provided, use the domain to help identify and verify the company. "
                "A mismatched or suspicious domain (e.g. typosquatting, free hosting) should be flagged as a red flag."
                if url else "")
    return (
        f"You are a company intelligence and job scam detection expert. Analyze this company{and_role} thoroughly.\n\n"
        f'Company: "{company}"{role_line}{url_context}\n\n'
        f"{JSON_SPEC}\n\n"
        "For well-known companies (Google, Microsoft, Anthropic, etc.) use accurate known data.\n"
        "For obscure or likely fake companies, use Unknown for financial fields and note low confidence.\n"
        f"headcount and annualRevenue should be ranges, not exact figures.{url_rule}"
        f"{UNKNOWN_RULE}"
    )


def vet(company: str, role: str = "", url: str = "") -> dict:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": build_prompt(company, role, url)}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError(f"No JSON in response: {raw[:200]}")
    result = json.loads(match.group(0))
    result["_usage"] = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    return result


if __name__ == "__main__":
    # Smoke test: python classify.py
    result = vet("Anthropic", "SDET", "https://anthropic.com")
    print(result["riskLevel"], result["recommendation"], "-", result["verdict"])