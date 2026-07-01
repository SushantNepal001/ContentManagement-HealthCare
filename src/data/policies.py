"""
policies.py — our small library of written healthcare billing policies.

WHAT THIS IS
------------
Six short, self-written "policy snippets." Each one is a plain-English rule of
the kind a payer or a payment-integrity company (like Cotiviti) has to manage.

WHY THEY LOOK LIKE THIS
-----------------------
- The `text` field is natural language on purpose. In Step 2 we embed that text
  into a vector database, and in Step 3 we retrieve it by *meaning*, not keywords.
  So it has to read like real policy, not like a list of codes.
- We wrote these ourselves instead of copying real CMS/payer manuals, which are
  copyrighted, licensed, and far too dense for a clean 5-minute demo. The written
  report names the real-world sources as the "production" data recommendation.
- Each policy is intentionally a SIMPLE, checkable condition (an age threshold, a
  required modifier, a frequency limit, a prior-auth requirement...). That keeps
  the deterministic engine in Step 5 easy to read and impossible to break on camera.

FIELDS
------
- id     : short stable identifier (used by the vector store and for citations)
- title  : human-friendly name shown in the UI
- text   : the actual written policy — THIS is what gets embedded and retrieved
"""

POLICIES = [
    {
        "id": "POL-TELEHEALTH-95",
        "title": "Telehealth visits require modifier 95",
        "text": (
            "Telehealth services delivered via real-time audio and video must be "
            "billed with modifier 95 to indicate a synchronous telehealth encounter. "
            "Claims for telehealth visits (place of service 02) submitted without "
            "modifier 95 do not meet documentation requirements and should be denied."
        ),
    },
    {
        "id": "POL-COLONOSCOPY-AGE",
        "title": "Screening colonoscopy minimum age",
        "text": (
            "A routine screening colonoscopy is a covered preventive service for "
            "average-risk patients beginning at age 45. Screening colonoscopy claims "
            "for patients younger than 45 are not covered as preventive care and "
            "should be denied unless a high-risk diagnosis is documented."
        ),
    },
    {
        "id": "POL-AWV-FREQUENCY",
        "title": "Annual wellness visit frequency limit",
        "text": (
            "The annual wellness visit is limited to once every 12 months per "
            "patient. A second annual wellness visit billed fewer than 365 days "
            "after a previous annual wellness visit exceeds the frequency limit "
            "and should be denied as a duplicate preventive service."
        ),
    },
    {
        "id": "POL-MRI-PRIORAUTH",
        "title": "Advanced imaging requires prior authorization",
        "text": (
            "Advanced diagnostic imaging such as MRI of the brain requires prior "
            "authorization before the service is rendered. Claims for advanced "
            "imaging submitted without an approved prior authorization on file "
            "should be flagged for clinical review rather than paid automatically."
        ),
    },
    {
        "id": "POL-BILATERAL-50",
        "title": "Bilateral procedures require modifier 50",
        "text": (
            "A procedure performed on both sides of the body during the same "
            "session must be reported as a single line with modifier 50 to indicate "
            "a bilateral procedure. A claim that bills two units of the same "
            "procedure without modifier 50 should be flagged for review as a "
            "possible unbundling or duplicate billing error."
        ),
    },
    {
        "id": "POL-ER-HIGHLEVEL",
        "title": "High-level emergency visit needs severity",
        "text": (
            "The highest-level emergency department visit represents care for "
            "conditions posing an immediate significant threat to life or function. "
            "When the highest-level emergency visit is billed with only a minor, "
            "self-limiting diagnosis, the level of service is not supported and the "
            "claim should be flagged for medical-necessity review."
        ),
    },
]


# A tiny convenience so other files can look a policy up by its id.
POLICIES_BY_ID = {p["id"]: p for p in POLICIES}


if __name__ == "__main__":
    # Run `python data/policies.py` to eyeball the library.
    print(f"{len(POLICIES)} policies loaded:\n")
    for p in POLICIES:
        print(f"  [{p['id']}] {p['title']}")
