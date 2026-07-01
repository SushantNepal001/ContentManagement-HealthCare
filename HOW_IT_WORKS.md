# How It Works — a plain-language walkthrough

This is your study guide. It explains the whole project in order, file by file, in
plain English — so you can present it on camera and answer interview questions.

---

## 1. The big picture

**What the app does:** you pick an insurance claim, and the app decides whether it
should be **PAID**, **DENIED**, or **FLAGGED** for review — and tells you *why*, in
plain English, citing the policy it used.

**The clever part:** the rule it uses to judge the claim is not hard-coded. It's
**written by an AI (Claude)**, live, from a plain-English policy document. Then a
separate piece of **plain Python** applies that rule.

**The one big idea to remember:**

> **AI drafts the rule. Deterministic code makes the decision.**

That split is the whole point. In healthcare you can't let an AI make the final
payment call unchecked (it could hallucinate). So the AI only does the "reading and
rewriting" part; a simple, auditable program does the deciding.

---

## 2. The pipeline (five steps)

Everything is one flow with five stages. This is the diagram to memorise:

```
   1. STORE      →  2. RETRIEVE   →  3. GENERATE   →  4. JUDGE      →  5. DISPLAY
   embed the        find the         Claude turns     plain Python     show it all
   policies into    policy that      that policy       applies the      in a web UI
   a vector DB      matches a        into a JSON       rule → verdict
                    claim (RAG "R")  rule (RAG "G")    (NO AI here)
```

- **RAG** = *Retrieval-Augmented Generation*. Steps 2 and 3 are the "R" and the "G".
  We *retrieve* the right policy, then *generate* a rule from it.

---

## 3. File-by-file walkthrough

### `src/data/policies.py` — the content we manage
Six short, plain-English **policy snippets** we wrote ourselves (telehealth needs a
modifier, colonoscopy has a minimum age, etc.). Each has an `id`, a `title`, and the
`text` (the actual written policy). The `text` is what gets embedded and searched.

*Why self-written?* Real CMS/payer manuals are copyrighted, licensed, and too dense
for a clean 5-minute demo. The report names the real sources for production.

### `src/data/claims.py` — the things we judge
Eight **sample claims**. Unlike policies (free text), a claim is a **structured
record** with fields a computer can check: `patient_age`, `cpt_code` (the procedure
code), `modifiers`, `place_of_service`, `units`, `prior_auth`, etc. The `expected`
field is only a note to ourselves — the real verdict is computed live.

### `src/vector_store.py` — STORE (step 1)
Takes each policy's text and turns it into an **embedding** — a list of numbers that
captures its *meaning*. Stores those in **ChromaDB**, a local vector database. Two
texts that mean similar things get similar numbers, even with no shared words.

Key function: `build_policy_collection()` — embeds all six policies and returns a
searchable collection. It rebuilds cleanly every run so the demo can't show stale
data. The embedding model (`all-MiniLM-L6-v2`) runs **locally, with no API key**.

### `src/retrieval.py` — RETRIEVE (step 2, the "R" in RAG)
Given a claim, finds the policy whose meaning is closest.

- `claim_to_query(claim)` — turns a structured claim into a plain-English sentence
  (e.g. *"A claim for a screening colonoscopy for a 39-year-old patient…"*). It uses
  a small **CPT-code → procedure-name** map, because the embedding model understands
  *words*, not billing codes like `45378`.
- `retrieve_policy(query)` / `retrieve_for_claim(claim)` — embeds that sentence and
  asks ChromaDB for the closest policy. Returns it with a **distance** score (lower =
  closer in meaning).

*The lesson worth telling:* feeding raw codes failed; describing them in words fixed
it. That shows you understand *why* semantic search behaves the way it does.

### `src/rule_generator.py` — GENERATE (step 3, the "G" in RAG)
The generative-AI heart of the demo. Sends the retrieved policy's text to **Claude**
and gets back a **structured JSON rule**.

- **Structured outputs:** the API is handed a JSON schema and *must* answer in that
  shape, so Claude can't return a malformed rule.
- **The rule shape:** a list of `conditions` (field / operator / value) that are
  AND-ed together, a `verdict` (PAY/DENY/FLAG) when they all match, and a `reason`.
- **Guardrail (`_is_valid_rule`):** even with schema-enforced JSON, we re-check every
  rule ourselves — reject anything using an unknown field or operator. *We never
  trust AI output blindly for a healthcare decision.*
- **Fallback (`FALLBACK_RULES`):** a saved rule for every policy. If the key is
  missing, the network fails, or the response is refused, we use it — so the demo
  never breaks.
- `policy_to_rule(text, id)` returns `(rule, source)` where `source` is `"live"` or
  `"fallback"` — that's what drives the LIVE badge in the UI.

### `src/engine.py` — JUDGE (step 4, NO AI)
The safety keystone. Pure Python — no model, no network. Takes a rule and a claim
and returns the verdict.

- `_check_condition(condition, claim)` — evaluates one condition (handles the
  fiddly bits: `"45"` → `45`, `None` values, list membership).
- `judge_claim(rule, claim)` — checks **all** conditions:
  - if **every** condition is true → the rule is **violated** → return its verdict.
  - if **any** condition is false → **PAY** (no violation of this policy).
- `evaluate_conditions(rule, claim)` — returns each condition + whether it held, so
  the UI can show the reasoning step by step.

Because it's deterministic, the same claim always gets the same verdict. Running
`python -m src.engine` judges all eight sample claims and scores **8/8**.

### `app.py` — DISPLAY (step 5)
The **Streamlit** web app that runs the whole pipeline for a chosen claim and shows,
in order: the retrieved policy → the generated rule (with the **LIVE/SAVED badge**) →
the final PAY/DENY/FLAG verdict. A sidebar toggle switches between the live API and
the offline saved rules. A collapsible panel shows the engine's step-by-step check.

### Supporting files
- `.env` — holds your `ANTHROPIC_API_KEY` (git-ignored, never committed).
- `.env.example` — a keyless template so others know what to set.
- `requirements.txt` — the four top-level dependencies, pinned.
- `.gitignore` — keeps secrets, the venv, and the ChromaDB folder out of git.

---

## 4. Follow one claim all the way through

Take **CLM-002** — *a telehealth visit billed WITHOUT modifier 95*. Expected: DENY.

1. **Retrieve.** `claim_to_query` builds *"A claim for an office visit delivered via
   telehealth video visit for a 47-year-old patient billed with no modifiers."*
   ChromaDB returns the closest policy: **POL-TELEHEALTH-95**.
2. **Generate.** Claude reads that policy and writes the rule:
   *"IF place_of_service = 02 AND modifiers does not include 95 → DENY."*
3. **Judge.** The engine checks the claim:
   - `place_of_service equals "02"` → the claim's POS is `"02"` → ✅ true
   - `modifiers not_contains_any "95"` → the claim's modifiers are `[]` → ✅ true
   - Both true → the rule is **violated** → **DENY**.
4. **Display.** The UI shows a red **DENY** box with the reason: *"Telehealth visit
   (place of service 02) billed without modifier 95, which the policy requires."*

Now compare **CLM-001** — same thing but *with* modifier 95. The second condition
(`modifiers not_contains_any "95"`) is **false** (the claim *does* have 95), so not
all conditions hold → the rule is **not** violated → **PAY**. That's why a rule whose
`verdict` says "DENY" can still produce a PAY: the verdict is the penalty *if the
rule is broken*, and this claim didn't break it.

---

## 5. Key concepts, explained simply

- **Embedding** — a numeric fingerprint of a piece of text's *meaning*. Similar
  meanings → similar numbers. This is what lets us match a messy claim to the right
  policy without keyword matching.
- **Vector database (ChromaDB)** — stores those fingerprints and answers "which
  stored items are closest in meaning to this one?" quickly.
- **RAG (Retrieval-Augmented Generation)** — instead of asking the LLM to answer from
  memory, we first *retrieve* the relevant document (the policy) and hand it to the
  LLM to work from. More accurate, and grounded in real source text.
- **Structured outputs** — forcing the LLM's answer to match a fixed JSON schema, so
  it's always valid and machine-usable.
- **Deterministic engine** — plain code that always gives the same output for the
  same input. The opposite of an LLM, which can vary. That predictability is what
  makes it safe to trust with the actual decision.
- **Fallback / graceful degradation** — a saved backup so a failed API call quietly
  uses a known-good rule instead of crashing.

---

## 6. Likely interview / on-camera questions (and answers)

**"Where is the AI, exactly?"** — Only in step 3 (`src/rule_generator.py`), where Claude
turns policy text into a rule. It never sees a claim and never makes a payment
decision.

**"How do you stop the AI from making a wrong payment?"** — Two ways. First, it only
drafts rules; the deterministic engine (`src/engine.py`) makes the decision. Second, we
validate every generated rule against an allow-list of fields and operators and
reject anything unexpected.

**"What happens if the API is down during the demo?"** — Nothing visible. Each policy
has a saved fallback rule; a failed or refused call quietly uses it, so the app keeps
working offline.

**"Why did feeding the CPT code fail at first?"** — Embeddings understand words, not
numbers. `45378` means nothing to the model; *"a screening colonoscopy"* does. Adding
a code-to-name map fixed the retrieval — a real system needs that concept layer.

**"How would this look in production?"** — Real policy corpora, a managed vector
database, a human-in-the-loop review queue for FLAGGED claims, evaluation harnesses,
and cloud deployment. Those are named in the written report; the POC deliberately
stays minimal.

**"Why is a rule's verdict 'DENY' but the claim got 'PAY'?"** — The verdict is the
penalty *if the rule is violated*. If the claim satisfies the policy (not all
violation conditions are true), it passes → PAY.

---

## 7. How to run it

```bash
source .venv/bin/activate      # activate the environment
streamlit run app.py           # launch the web app
```

To see the internals in the terminal:

```bash
python -m src.retrieval            # semantic search matching claims to policies
python -m src.engine               # judge all claims end-to-end (8/8, offline)
```
