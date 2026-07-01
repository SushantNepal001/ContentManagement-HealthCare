"""
vector_store.py — embed the policies and store them in ChromaDB.

WHAT THIS DOES
--------------
Takes the six plain-English policies from data/policies.py, turns each one into
an EMBEDDING (a list of numbers that captures its meaning), and loads those into
a ChromaDB collection we can search by meaning.

WHY IT MATTERS (the RAG "R" — Retrieval)
----------------------------------------
- An embedding is a numeric fingerprint of meaning. Texts that mean similar
  things get similar numbers, even when they share no words. That is what lets a
  messy real-world claim ("video visit, no special code") find the right policy
  ("telehealth requires modifier 95") without keyword matching.
- ChromaDB is the vector database that stores those fingerprints and answers
  "which policies are closest in meaning to this query?" quickly.
- We use ChromaDB's built-in local embedding model (all-MiniLM-L6-v2). It runs on
  this machine, is free, and needs NO API key — so embedding and retrieval work
  offline, and the only place we call an external LLM is Step 4.

DESIGN CHOICE
-------------
build_policy_collection() deletes and rebuilds the collection every time, so the
store is always a clean, exact mirror of data/policies.py. Re-embedding six short
snippets is instant, and a deterministic rebuild means the live demo can never
show stale or half-loaded data.
"""

import chromadb
from chromadb.utils import embedding_functions

from data.policies import POLICIES

# Where ChromaDB keeps its local files. This folder is git-ignored and is fully
# regenerated from code, so it never needs to be committed.
CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "policies"

# The local, no-API-key embedding model. Created once and reused.
_embedding_fn = embedding_functions.DefaultEmbeddingFunction()


def build_policy_collection(verbose=False):
    """Embed every policy and return a fresh ChromaDB collection.

    Deletes any existing collection first so the result is always an exact,
    clean mirror of data/policies.py.
    """
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Start clean: drop the old collection if it exists, then recreate it.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # nothing to delete on the first run

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn,
    )

    # ChromaDB embeds each `document` automatically using the embedding function
    # above. We keep the title in metadata so the UI can show a friendly name.
    collection.add(
        ids=[p["id"] for p in POLICIES],
        documents=[p["text"] for p in POLICIES],
        metadatas=[{"title": p["title"]} for p in POLICIES],
    )

    if verbose:
        print(f"Embedded and stored {collection.count()} policies "
              f"in collection '{COLLECTION_NAME}'.")

    return collection


if __name__ == "__main__":
    # Build the store, then run one plain-English query to PROVE that semantic
    # search works — the query below shares almost no words with the policy text.
    collection = build_policy_collection(verbose=True)

    demo_query = "patient had a video appointment but no special billing code"
    print(f"\nQuery: {demo_query!r}")

    results = collection.query(query_texts=[demo_query], n_results=3)

    print("\nMost semantically similar policies:")
    for rank, (pol_id, doc, dist) in enumerate(
        zip(results["ids"][0], results["documents"][0], results["distances"][0]),
        start=1,
    ):
        title = next(p["title"] for p in POLICIES if p["id"] == pol_id)
        # Lower distance = closer in meaning.
        print(f"  {rank}. [{pol_id}] {title}  (distance={dist:.3f})")
