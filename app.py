"""
app.py — the Streamlit web app that ties the whole pipeline together.

WHAT THIS DOES (the "Display" step)
-----------------------------------
Gives you one screen that runs all five steps for a chosen claim:
  1. Store    - policies are already embedded in ChromaDB (done at import)
  2. Retrieve - find the policy that best matches the claim   (RAG "R")
  3. Generate - Claude turns that policy into a JSON rule      (RAG "G")
  4. Judge    - the deterministic engine decides PAY/DENY/FLAG (no AI)
  5. Display  - everything you see below

WHY IT MATTERS
--------------
This is the piece a reviewer actually watches. It turns five Python files into a
single, click-only story and shows — with a live badge — whether each rule was
written by Claude just now or served from the saved fallback.

Run it with:   streamlit run app.py
"""

import json

import streamlit as st

from data.claims import CLAIMS
from retrieval import retrieve_for_claim, claim_to_query
from rule_generator import policy_to_rule, FALLBACK_RULES
from engine import judge_claim, evaluate_conditions


# Human-friendly wording for each operator, used in the reasoning trace.
OPERATOR_WORDS = {
    "equals": "must equal",
    "not_equals": "must not equal",
    "less_than": "must be less than",
    "greater_than_or_equal": "must be at least",
    "contains_any": "must include one of",
    "not_contains_any": "must not include",
    "is_true": "must be true",
    "is_false": "must be false",
}


def describe_condition(condition, claim):
    """Turn one condition into a readable line, with the claim's actual value."""
    field = condition["field"]
    op_words = OPERATOR_WORDS.get(condition["operator"], condition["operator"])
    value = condition["value"]
    value_text = "" if not value else " " + ", ".join(f'"{v}"' for v in value)
    return f'`{field}` {op_words}{value_text}  —  claim has: `{claim.get(field)}`'


st.set_page_config(page_title="Policy-to-Rule", page_icon="🏥", layout="wide")


# Cache the generated rule so clicking around doesn't re-call the API every time
# (saves money and keeps the demo snappy). Keyed on the policy + live/offline mode.
@st.cache_data(show_spinner=False)
def get_rule(policy_id, policy_text, use_live):
    if not use_live:
        # Force the saved rule — useful for a guaranteed-deterministic recording.
        return FALLBACK_RULES[policy_id], "fallback"
    return policy_to_rule(policy_text, policy_id)


def verdict_banner(verdict, reason):
    """Show the final decision in a big, colour-coded box."""
    if verdict == "PAY":
        st.success(f"### ✅ {verdict}\n{reason}")
    elif verdict == "DENY":
        st.error(f"### ⛔ {verdict}\n{reason}")
    else:  # FLAG
        st.warning(f"### ⚠️ {verdict}\n{reason}")


# ---------------------------------------------------------------------------
# Sidebar: controls + a short "how it works" for the presenter.
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Controls")
    use_live = st.checkbox(
        "Use live Claude API",
        value=True,
        help="On: Claude writes the rule from the policy text. "
             "Off: use the saved rule (fully offline, deterministic).",
    )
    st.divider()
    st.subheader("How it works")
    st.markdown(
        "1. **Retrieve** – find the policy that best matches the claim "
        "(semantic search over a vector database).\n"
        "2. **Generate** – Claude rewrites that policy as a machine-readable rule.\n"
        "3. **Judge** – plain Python (no AI) applies the rule and decides.\n\n"
        "*AI drafts the rule; deterministic code makes the decision.*"
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🏥 Policy-to-Rule")
st.caption(
    "Turn a written healthcare billing policy into a working rule that judges "
    "insurance claims as PAY / DENY / FLAG — with a plain-English, policy-cited "
    "reason."
)


# ---------------------------------------------------------------------------
# Step 0: pick a claim
# ---------------------------------------------------------------------------
labels = [f"{c['claim_id']} — {c['description']}" for c in CLAIMS]
choice = st.selectbox("Choose a sample claim to check:", labels)
claim = CLAIMS[labels.index(choice)]

# Show the structured claim so the audience sees what's being judged.
with st.expander("See the claim details", expanded=False):
    st.json({k: v for k, v in claim.items() if k != "expected"})


# ---------------------------------------------------------------------------
# Run the pipeline for the chosen claim.
# ---------------------------------------------------------------------------
# Step 2 — Retrieve the best-matching policy (semantic search).
match = retrieve_for_claim(claim)[0]

# Step 3 — Generate (or fetch) the rule for that policy.
with st.spinner("Asking Claude to turn the policy into a rule…"):
    rule, source = get_rule(match["id"], match["text"], use_live)

# Step 4 — Judge the claim with the deterministic engine.
result = judge_claim(rule, claim)


# ---------------------------------------------------------------------------
# Display everything, in pipeline order.
# ---------------------------------------------------------------------------
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("1 · Retrieved policy  ·  RAG “R”")
    st.caption(
        f"Matched by meaning, not keywords "
        f"(distance {match['distance']:.3f} — lower is closer)."
    )
    st.markdown(f"**{match['title']}**  \n`{match['id']}`")
    st.info(match["text"])
    with st.expander("The plain-English query we searched with"):
        st.write(claim_to_query(claim))

with col_right:
    st.subheader("2 · Generated rule  ·  RAG “G”")
    # LIVE vs saved badge — the line you point at on camera.
    if source == "live":
        st.markdown(":green-background[**LIVE** — written by Claude just now]")
    else:
        st.markdown(":gray-background[**SAVED** — using the offline fallback rule]")
    # Make the meaning of the rule's verdict field explicit: it is the penalty
    # applied ONLY IF every condition below is true (i.e. the rule is violated).
    st.caption(
        f"This rule flags a violation. Penalty **if all conditions are met**: "
        f"**{rule['verdict']}**."
    )
    st.json(rule)

st.divider()

# Step 5 — the final verdict.
st.subheader("3 · Verdict  ·  deterministic engine (no AI)")
verdict_banner(result["verdict"], result["reason"])

# The condition-by-condition reasoning lives in a collapsed panel: hidden by
# default to keep the screen clean, one click away to explain on camera.
with st.expander("Show how the engine decided (step by step)"):
    for condition, passed in evaluate_conditions(rule, claim):
        mark = "✅" if passed else "❌"
        st.markdown(f"{mark} {describe_condition(condition, claim)}")
    if result["matched"]:
        st.markdown(
            f"➡️ **All conditions met → the rule is violated → "
            f"{result['verdict']}.**"
        )
    else:
        st.markdown(
            "➡️ **Not all conditions met → the rule is not violated → PAY.**"
        )
