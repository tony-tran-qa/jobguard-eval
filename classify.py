"""JobGuard eval harness - wrapper around JobGuard's company-vetting prompt.

Prompt text mirrors vetCompanyWithAI() in my-jobguard/src/App.jsx exactly.
If you change the prompt in App.jsx, change it here too.
"""
import json
import re

import anthropic

MODEL = "claude-haiku-4-5-20251001"   # same model as App.jsx
MAX_TOKENS = 900                      # same as App.jsx

client = anthropic.Anthropic()        # reads ANTHROPIC_API_KEY from the environment

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
    return json.loads(match.group(0))


if __name__ == "__main__":
    # Smoke test: python classify.py
    result = vet("Anthropic", "SDET", "https://anthropic.com")
    print(result["riskLevel"], result["recommendation"], "-", result["verdict"])