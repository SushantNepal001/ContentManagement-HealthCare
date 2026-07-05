# Policy-to-Rule — Content Management in Health Care

A small proof-of-concept that turns a **written healthcare billing policy** into a
**working rule** that judges sample insurance claims as **PAY / DENY / FLAG**, with
a plain-English, policy-cited reason.

It demonstrates, at a first-principles level, the technologies behind modern
payment-integrity / "content management" products: **embeddings, a vector
database, retrieval, RAG, and generative AI** — with a deliberate safety design.

---

## The idea in one sentence

> Paste (or select) a written policy, let an LLM convert it into a machine-readable
> rule, then let **plain, auditable Python** — not the AI — apply that rule to
> claims and make the actual decision.

**Core design principle:** *AI drafts the rule; deterministic code decides.* This
mirrors safe real-world healthcare practice — you never let a language model make
an unchecked payment call — and it keeps the live demo from ever breaking.

---

## The pipeline

```
          ┌───────────────────────────── written policies (plain English)
          │
   1. STORE         embed the policies into a local ChromaDB vector database
          │
   2. RETRIEVE      a claim is embedded; the nearest policy is returned   ← RAG "R"
          │         (semantic search — matches on meaning, not keywords)
          │
   3. GENERATE      Claude rewrites that policy as a structured JSON rule  ← RAG "G"
          │         (schema-enforced; validated; falls back if unavailable)
          │
   4. JUDGE         plain Python applies the rule to the claim → PAY/DENY/FLAG
          │         (NO AI here — the auditable decision layer)
          │
   5. DISPLAY       a Streamlit UI shows every step and the final verdict
```

---

## Tech stack

| Piece            | Choice                                             |
| ---------------- | -------------------------------------------------- |
| Language         | Python 3.9                                         |
| Vector database  | ChromaDB (local, with a built-in embedding model)  |
| Embeddings       | `all-MiniLM-L6-v2` (runs locally, no API key)      |
| LLM              | Claude via the Anthropic API (model set by env var)|
| UI               | Streamlit                                          |
| Sample data      | self-written policy snippets + test claims         |

The policy snippets and claims are **hand-written**, not real CMS/payer documents
(those are copyrighted, licensed, and too dense for a clean demo). Real sources are
named in the accompanying written report's production recommendation.

---

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Claude API key
cp .env.example .env               # then edit .env and paste your key
```

Your key lives in `.env`, which is git-ignored and never committed. The app still
runs **without** a key — it uses saved fallback rules instead of the live LLM.

---

## Run it

```bash
streamlit run app.py
```

Then open the URL it prints (usually http://localhost:8501). Pick a claim and watch
the pipeline run. The sidebar has a toggle to switch between the **live Claude API**
and the **offline saved rules** (handy for a deterministic demo).

### Run the individual steps (optional)

Each stage also runs on its own (as a module, from the project root), which is
useful for understanding the internals:

```bash
python -m src.data.policies   # list the policy snippets
python -m src.data.claims     # list the sample claims
python -m src.vector_store    # embed policies + a semantic-search sanity check
python -m src.retrieval       # route each claim to its best-matching policy
python -m src.rule_generator  # convert each policy into a rule (LIVE or fallback)
python -m src.engine          # judge every claim end-to-end (scores 8/8, offline)
```

---

## Project structure

```
.
├── app.py                    # DISPLAY: the Streamlit UI (entry point)
├── src/
│   ├── data/
│   │   ├── policies.py       # 6 written policy snippets (the content to manage)
│   │   └── claims.py         # 8 structured test claims
│   ├── vector_store.py       # STORE:    embed policies into ChromaDB
│   ├── retrieval.py          # RETRIEVE: semantic search (RAG "R")
│   ├── rule_generator.py     # GENERATE: policy -> JSON rule via Claude (RAG "G")
│   └── engine.py             # JUDGE:    deterministic PAY/DENY/FLAG (no AI)
├── requirements.txt
└── .env.example              # keyless template for the API key
```

---

## Why it's built this way

- **Generative AI only drafts.** The LLM converts policy text into a rule. It never
  sees a claim and never issues a payment decision.
- **Deterministic code decides.** `engine.py` applies the rule in plain Python that
  a human can read line by line. Same input always gives the same verdict.
- **Guardrails on AI output.** Generated rules are schema-enforced *and* validated
  against an allow-list of fields/operators; anything unexpected is rejected.
- **Graceful degradation.** If the API key is missing, the network fails, or a
  request is refused, the app falls back to a saved rule — the demo never crashes.

---

## Scope

This is intentionally a small, first-principles demonstration: ~6 policies, one
vector search, one LLM call per policy, a handful of claims, and a minimal UI.
Production concerns — fine-tuning, cloud deployment, large corpora, authentication,
managed vector databases, evaluation harnesses — are out of scope for the POC and
are discussed in the written report's recommendation instead.
