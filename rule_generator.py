"""
rule_generator.py — the "G" in RAG: turn a written policy into a runnable rule.

WHAT THIS DOES
--------------
Takes a plain-English policy (the text Step 3 retrieved) and asks Claude to
rewrite it as a STRUCTURED, machine-readable rule in JSON. That rule is what the
deterministic engine (Step 5) actually runs against claims.

WHY IT MATTERS (the generative-AI heart of the demo)
----------------------------------------------------
- Converting unstructured written policy into an executable rule is exactly the
  "content management" problem a payment-integrity company like Cotiviti solves.
- We use STRUCTURED OUTPUTS: the API is given a JSON schema and is required to
  answer in that shape, so Claude cannot return a malformed rule.
- Safety by design: the LLM only DRAFTS the rule. It never sees a claim and never
  decides a payment. And we still validate its output ourselves (below) — if the
  rule references an unknown field or operator, we reject it and fall back.
- A SAVED FALLBACK rule exists for every policy, so the live demo keeps working
  even with no internet, no API key, or a refused request.

THE RULE SHAPE (kept deliberately small so Step 5's engine stays tiny)
----------------------------------------------------------------------
    {
      "policy_id": "POL-...",
      "rule_name": "short human name",
      "conditions": [ {"field": ..., "operator": ..., "value": ["..."]}, ... ],
      "verdict": "PAY" | "DENY" | "FLAG",
      "reason": "plain-English explanation, citing the policy"
    }

Meaning: if ALL conditions are true for a claim, the engine returns `verdict`
with `reason`. If any condition is false, the claim PASSES this policy (PAY).
"""

import json
import os

from dotenv import load_dotenv

# Load ANTHROPIC_API_KEY and LLM_MODEL from a local .env file if present.
# (In production you'd use real secret management — see the report.)
load_dotenv()

MODEL = os.environ.get("LLM_MODEL", "claude-opus-4-8")


# ---------------------------------------------------------------------------
# The vocabulary the rule is allowed to use.
# These MUST match the fields on a claim (see data/claims.py) and the operators
# the engine understands (see Step 5). We list them here so we can (a) tell the
# model exactly what it may use, and (b) validate its answer afterwards.
# ---------------------------------------------------------------------------
ALLOWED_FIELDS = [
    "patient_age",        # int
    "cpt_code",           # str
    "diagnosis_codes",    # list[str]
    "modifiers",          # list[str]
    "place_of_service",   # str  ("02" telehealth, "23" ER, ...)
    "units",              # int
    "prior_auth",         # bool
    "days_since_same",    # int or None
]

ALLOWED_OPERATORS = [
    "equals",                  # claim field == value[0]
    "not_equals",              # claim field != value[0]
    "less_than",               # int(claim field) <  int(value[0])
    "greater_than_or_equal",   # int(claim field) >= int(value[0])
    "contains_any",            # claim list shares an item with value
    "not_contains_any",        # claim list shares NOTHING with value
    "is_true",                 # boolean claim field is True   (value ignored)
    "is_false",                # boolean claim field is False  (value ignored)
]

VERDICTS = ["PAY", "DENY", "FLAG"]


# The JSON schema the API enforces on Claude's answer. Because of this, the
# response is guaranteed to be valid JSON in this exact structure.
RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "policy_id": {"type": "string"},
        "rule_name": {"type": "string"},
        "conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": ALLOWED_FIELDS},
                    "operator": {"type": "string", "enum": ALLOWED_OPERATORS},
                    # value is always a list of strings; the engine coerces it
                    # (e.g. "45" -> 45) based on the field. Keeping one uniform
                    # shape makes both the schema and the engine simpler.
                    "value": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["field", "operator", "value"],
                "additionalProperties": False,
            },
        },
        "verdict": {"type": "string", "enum": VERDICTS},
        "reason": {"type": "string"},
    },
    "required": ["policy_id", "rule_name", "conditions", "verdict", "reason"],
    "additionalProperties": False,
}


SYSTEM_PROMPT = f"""\
You convert written healthcare billing policies into structured, machine-readable
rules for a claims-checking engine.

You are given one policy. Produce ONE rule that describes the VIOLATION the policy
guards against, so that when all conditions are true the claim should be denied or
flagged.

Rules you must follow:
- Use ONLY these claim fields: {", ".join(ALLOWED_FIELDS)}.
- Use ONLY these operators: {", ".join(ALLOWED_OPERATORS)}.
- Each condition's "value" is a LIST OF STRINGS (e.g. ["45"], ["95"], ["J00"]).
- All conditions are combined with AND: the verdict applies only when every
  condition is true.
- Choose "verdict" = "DENY" for clear non-coverage / documentation failures, and
  "FLAG" when the claim needs human review rather than an automatic denial.
- Write "reason" in plain English, citing what the policy requires.

Procedure codes you may need:
- 99213 = office/outpatient visit
- 45378 = screening colonoscopy
- G0439 = annual wellness visit
- 70551 = MRI of the brain (advanced imaging)
- 69210 = removal of impacted earwax (can be bilateral)
- 99285 = highest-level emergency department visit
Place of service: "02" = telehealth, "11" = office, "22" = outpatient, "23" = ER.
"""


# ---------------------------------------------------------------------------
# SAVED FALLBACK RULES — one per policy.
# Used whenever the live API call can't be made or its answer fails validation,
# so the demo always has a working rule. These are hand-written to match the
# policies in data/policies.py exactly.
# ---------------------------------------------------------------------------
FALLBACK_RULES = {
    "POL-TELEHEALTH-95": {
        "policy_id": "POL-TELEHEALTH-95",
        "rule_name": "Telehealth requires modifier 95",
        "conditions": [
            {"field": "place_of_service", "operator": "equals", "value": ["02"]},
            {"field": "modifiers", "operator": "not_contains_any", "value": ["95"]},
        ],
        "verdict": "DENY",
        "reason": ("Telehealth visit (place of service 02) billed without modifier "
                   "95, which the policy requires for synchronous telehealth."),
    },
    "POL-COLONOSCOPY-AGE": {
        "policy_id": "POL-COLONOSCOPY-AGE",
        "rule_name": "Screening colonoscopy minimum age 45",
        "conditions": [
            {"field": "cpt_code", "operator": "equals", "value": ["45378"]},
            {"field": "patient_age", "operator": "less_than", "value": ["45"]},
        ],
        "verdict": "DENY",
        "reason": ("Screening colonoscopy for a patient under 45 is not covered as "
                   "a preventive service under this policy."),
    },
    "POL-AWV-FREQUENCY": {
        "policy_id": "POL-AWV-FREQUENCY",
        "rule_name": "Annual wellness visit once per 12 months",
        "conditions": [
            {"field": "cpt_code", "operator": "equals", "value": ["G0439"]},
            {"field": "days_since_same", "operator": "less_than", "value": ["365"]},
        ],
        "verdict": "DENY",
        "reason": ("A second annual wellness visit billed fewer than 365 days after "
                   "the previous one exceeds the policy's frequency limit."),
    },
    "POL-MRI-PRIORAUTH": {
        "policy_id": "POL-MRI-PRIORAUTH",
        "rule_name": "Advanced imaging needs prior authorization",
        "conditions": [
            {"field": "cpt_code", "operator": "equals", "value": ["70551"]},
            {"field": "prior_auth", "operator": "is_false", "value": []},
        ],
        "verdict": "FLAG",
        "reason": ("Brain MRI (advanced imaging) submitted without an approved prior "
                   "authorization; policy says to review before paying."),
    },
    "POL-BILATERAL-50": {
        "policy_id": "POL-BILATERAL-50",
        "rule_name": "Bilateral procedure needs modifier 50",
        "conditions": [
            {"field": "units", "operator": "greater_than_or_equal", "value": ["2"]},
            {"field": "modifiers", "operator": "not_contains_any", "value": ["50"]},
        ],
        "verdict": "FLAG",
        "reason": ("Two units of the same procedure billed without modifier 50; the "
                   "policy asks to review this as a possible billing error."),
    },
    "POL-ER-HIGHLEVEL": {
        "policy_id": "POL-ER-HIGHLEVEL",
        "rule_name": "High-level ER visit needs a serious diagnosis",
        "conditions": [
            {"field": "cpt_code", "operator": "equals", "value": ["99285"]},
            {"field": "diagnosis_codes", "operator": "contains_any",
             "value": ["J00", "J06.9", "J20.9", "R05"]},
        ],
        "verdict": "FLAG",
        "reason": ("Highest-level emergency visit billed with only a minor, "
                   "self-limiting diagnosis; policy asks for medical-necessity "
                   "review."),
    },
}


def _is_valid_rule(rule):
    """Deterministic guard rail: reject anything that isn't a well-formed rule.

    Even though structured outputs make malformed JSON unlikely, we never trust
    AI output blindly for a healthcare decision — we check it ourselves.
    """
    try:
        if rule["verdict"] not in VERDICTS:
            return False
        for cond in rule["conditions"]:
            if cond["field"] not in ALLOWED_FIELDS:
                return False
            if cond["operator"] not in ALLOWED_OPERATORS:
                return False
            if not isinstance(cond["value"], list):
                return False
        return bool(rule["conditions"])  # a rule with no conditions is useless
    except (KeyError, TypeError):
        return False


def policy_to_rule(policy_text, policy_id):
    """Convert one policy into a structured rule.

    Tries the live Claude API first. If the key is missing, the call fails, the
    response is refused, or the returned rule fails our validator, we fall back
    to the saved rule for this policy so the demo never breaks.

    Returns (rule_dict, source) where source is "live" or "fallback".
    """
    try:
        import anthropic

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the env

        user_prompt = (
            f'Policy id: {policy_id}\n'
            f'Policy text:\n"""{policy_text}"""\n\n'
            f'Return the rule for this policy.'
        )

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema", "schema": RULE_SCHEMA}},
        )

        # A safety refusal (or any non-normal stop) -> use the fallback.
        if response.stop_reason == "refusal":
            return FALLBACK_RULES[policy_id], "fallback"

        text = next(b.text for b in response.content if b.type == "text")
        rule = json.loads(text)

        # Make sure the policy id is the one we asked about, then validate.
        rule["policy_id"] = policy_id
        if _is_valid_rule(rule):
            return rule, "live"
        return FALLBACK_RULES[policy_id], "fallback"

    except Exception:
        # Missing key, network error, unknown policy id, etc. — degrade safely.
        if policy_id in FALLBACK_RULES:
            return FALLBACK_RULES[policy_id], "fallback"
        raise


if __name__ == "__main__":
    # Convert every policy and show the resulting rule + where it came from.
    from data.policies import POLICIES

    for p in POLICIES:
        rule, source = policy_to_rule(p["text"], p["id"])
        print(f"[{source.upper():>8}] {rule['rule_name']}  ->  {rule['verdict']}")
        for c in rule["conditions"]:
            print(f"           if {c['field']} {c['operator']} {c['value']}")
        print()
