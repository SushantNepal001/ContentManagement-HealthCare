"""
engine.py — the deterministic claim engine ("code decides"). NO AI in this file.

WHAT THIS DOES
--------------
Takes ONE rule (the JSON produced in Step 4) and ONE claim (Step 1) and returns a
verdict: PAY, DENY, or FLAG, plus a plain-English reason.

WHY IT MATTERS (the safety keystone of the whole design)
--------------------------------------------------------
- The LLM only DRAFTS rules. This module makes the actual decision, in plain
  Python a human can read line by line. That mirrors safe healthcare practice:
  never let an AI make an unchecked payment decision.
- Because there is no model and no network here, it cannot hallucinate and cannot
  crash from an API failure. Same input always gives the same verdict — which is
  exactly what keeps the live demo from breaking.

HOW A RULE IS EVALUATED
-----------------------
A rule has a list of conditions (field / operator / value). We check each one
against the claim, AND them together, and:
  - if EVERY condition is true  -> return the rule's verdict + reason (a violation)
  - if ANY condition is false   -> return PAY ("no violation of this policy")

The operators and fields match exactly what Step 4 is allowed to emit
(see rule_generator.ALLOWED_FIELDS / ALLOWED_OPERATORS).
"""


def _to_int(value):
    """Best-effort convert a value to int; return None if it can't be done.

    Rules carry values as strings (e.g. "45"), and some claim fields can be None
    (e.g. days_since_same for a first-time service). Returning None lets numeric
    comparisons safely fail instead of raising.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_list(value):
    """Treat a claim field as a list for membership checks.

    Some fields are already lists (modifiers, diagnosis_codes); others are single
    values. Normalising to a list lets 'contains_any' work uniformly.
    """
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _check_condition(condition, claim):
    """Return True if a single condition holds for this claim.

    `condition` looks like {"field": ..., "operator": ..., "value": [...]}.
    `claim` is a dict from data/claims.py.
    """
    field = condition["field"]
    operator = condition["operator"]
    value = condition["value"]            # always a list of strings (see Step 4)
    claim_value = claim.get(field)

    if operator == "equals":
        return str(claim_value) == value[0]

    if operator == "not_equals":
        return str(claim_value) != value[0]

    if operator == "less_than":
        left, right = _to_int(claim_value), _to_int(value[0])
        # If either side isn't a number (e.g. days_since_same is None), the
        # condition simply does not hold.
        return left is not None and right is not None and left < right

    if operator == "greater_than_or_equal":
        left, right = _to_int(claim_value), _to_int(value[0])
        return left is not None and right is not None and left >= right

    if operator == "contains_any":
        claim_items = set(_as_list(claim_value))
        return len(claim_items.intersection(value)) > 0

    if operator == "not_contains_any":
        claim_items = set(_as_list(claim_value))
        return len(claim_items.intersection(value)) == 0

    if operator == "is_true":
        return claim_value is True

    if operator == "is_false":
        return claim_value is False

    # Unknown operator -> treat as not satisfied (defensive; Step 4 validates
    # operators, so this should never happen).
    return False


def judge_claim(rule, claim):
    """Apply one rule to one claim and return the verdict.

    Returns a dict:
        {
          "verdict": "PAY" | "DENY" | "FLAG",
          "reason": "plain-English explanation",
          "policy_id": "POL-...",
          "matched": bool,        # did the rule's violation conditions all hold?
        }
    """
    all_conditions_true = all(
        _check_condition(cond, claim) for cond in rule["conditions"]
    )

    if all_conditions_true:
        # The policy's violation applies -> use the rule's verdict + reason.
        return {
            "verdict": rule["verdict"],
            "reason": rule["reason"],
            "policy_id": rule.get("policy_id", ""),
            "matched": True,
        }

    # No violation of this policy -> the claim passes.
    return {
        "verdict": "PAY",
        "reason": "No violation of this policy was detected, so the claim is payable.",
        "policy_id": rule.get("policy_id", ""),
        "matched": False,
    }


if __name__ == "__main__":
    # End-to-end check with NO live API: use the saved fallback rules so this
    # runs offline, route each claim to its policy, and judge it.
    from data.claims import CLAIMS
    from rule_generator import FALLBACK_RULES
    from retrieval import retrieve_for_claim

    print("Judging every sample claim (using saved rules, offline):\n")
    correct = 0
    for claim in CLAIMS:
        # Step 3: find the best-matching policy for this claim.
        policy_id = retrieve_for_claim(claim)[0]["id"]
        # Step 4 (saved-rule version): the rule for that policy.
        rule = FALLBACK_RULES[policy_id]
        # Step 5: judge.
        result = judge_claim(rule, claim)

        got = result["verdict"]
        expected = claim["expected"]
        ok = "OK " if got == expected else "XX "
        correct += (got == expected)

        print(f"{ok}{claim['claim_id']}: got {got:<4} (expected {expected:<4}) "
              f"- {claim['description']}")

    print(f"\n{correct}/{len(CLAIMS)} claims matched their expected verdict.")
