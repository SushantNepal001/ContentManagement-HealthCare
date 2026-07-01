"""
retrieval.py — the "R" in RAG, wrapped in one clean function.

WHAT THIS DOES
--------------
Given a plain-English question OR a structured claim, find the policy in the
ChromaDB store whose meaning is closest. This is the single doorway the rest of
the app uses for retrieval — nothing else needs to know ChromaDB exists.

WHY IT MATTERS
--------------
- Step 2 proved semantic search works. Here we package it as a dependable
  function, retrieve_policy(), that returns a simple dict the LLM step and the UI
  can use without touching embeddings or the vector database directly.
- Because retrieval lives behind one function, swapping ChromaDB for a managed
  vector database later (a point made in the written report) would change only
  this file.

TWO WAYS TO ASK
---------------
- retrieve_policy("video visit billed with no special code")  -> free text
- claim_to_query(claim)  turns a structured claim (age, CPT, modifiers, ...) into
  a sentence the embedding model can match against the written policies.
"""

from vector_store import build_policy_collection

# Build (or rebuild) the collection once when this module is imported, and reuse
# it for every retrieval. Rebuilding six short snippets is instant.
_collection = build_policy_collection()


# A real claims system knows what each billing code means. The embedding model
# only understands words, not numbers like "45378", so we give it the clinical
# name of the procedure. That is what makes semantic retrieval land on the right
# policy instead of matching on stray words.
CPT_NAMES = {
    "99213": "an office or outpatient evaluation and management visit",
    "45378": "a screening colonoscopy of the colon",
    "G0439": "an annual wellness visit",
    "70551": "an MRI scan of the brain",
    "69210": "removal of impacted earwax, performed on both ears",
    "99285": "a highest-level emergency department visit",
}


def claim_to_query(claim):
    """Turn a structured claim into a plain-English sentence for retrieval.

    The embedding model compares meaning between texts, so we describe the claim
    in the same natural language the policies are written in — leading with the
    CLINICAL NAME of the procedure and only adding the facts a policy would care
    about (setting, modifiers, units, frequency). We deliberately do NOT append
    boilerplate like "no prior authorization" to every claim, because repeating
    the same phrase everywhere drags unrelated claims toward the prior-auth
    policy.
    """
    procedure = CPT_NAMES.get(claim["cpt_code"], f"procedure code {claim['cpt_code']}")
    parts = [f"A claim for {procedure}"]

    # Place of service, spelled out where it matters to a policy.
    pos_words = {"02": "delivered via telehealth video visit",
                 "23": "in the emergency department"}
    if claim["place_of_service"] in pos_words:
        parts.append(pos_words[claim["place_of_service"]])

    parts.append(f"for a {claim['patient_age']}-year-old patient")

    if claim["modifiers"]:
        parts.append("billed with modifiers " + ", ".join(claim["modifiers"]))
    else:
        parts.append("billed with no modifiers")

    if claim["units"] and claim["units"] != 1:
        parts.append(f"as {claim['units']} units")

    if claim.get("days_since_same") is not None:
        parts.append(
            f"repeated only {claim['days_since_same']} days after the same service"
        )

    return " ".join(parts) + "."


def retrieve_policy(query, k=1):
    """Return the k policies closest in meaning to `query`.

    `query` may be any string (a question, a scenario, or the output of
    claim_to_query). Returns a list of dicts, best match first:

        {"id": ..., "title": ..., "text": ..., "distance": float}

    Lower distance = closer in meaning. With the default k=1 you get a
    single-item list holding the single best policy.
    """
    results = _collection.query(query_texts=[query], n_results=k)

    matches = []
    for pol_id, doc, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        matches.append({
            "id": pol_id,
            "title": meta.get("title", ""),
            "text": doc,
            "distance": dist,
        })
    return matches


def retrieve_for_claim(claim, k=1):
    """Convenience: build a query from a structured claim, then retrieve."""
    return retrieve_policy(claim_to_query(claim), k=k)


if __name__ == "__main__":
    # Demo 1: a free-text question.
    print("=== Free-text query ===")
    q = "do I need prior approval before an MRI of the head?"
    best = retrieve_policy(q)[0]
    print(f"Query: {q!r}")
    print(f"  -> [{best['id']}] {best['title']}  (distance={best['distance']:.3f})\n")

    # Demo 2: every sample claim, routed to its best-matching policy.
    from data.claims import CLAIMS

    print("=== Each sample claim -> best-matching policy ===")
    for c in CLAIMS:
        match = retrieve_for_claim(c)[0]
        print(f"{c['claim_id']}: {c['description']}")
        print(f"    query : {claim_to_query(c)}")
        print(f"    policy: [{match['id']}] {match['title']}  "
              f"(distance={match['distance']:.3f})\n")
