"""
claims.py — sample insurance claims for the demo to judge.

WHAT THIS IS
------------
A handful of made-up claims. Unlike the policies (which are free text), a claim
is a STRUCTURED record with fields a computer can check: age, procedure code,
modifiers, and so on. In Step 5 a plain-Python engine reads the rule the LLM
generated and checks it against exactly these fields — no AI in the final call.

WHY THESE PARTICULAR CLAIMS
---------------------------
They are hand-picked so the demo shows all three outcomes — PAY, DENY, and
FLAG — and so each one lines up with one of the six policies. The `expected`
field is only a note for us (what a correct engine *should* say); the real
verdict is computed live, never read from here.

FIELD DICTIONARY
----------------
- claim_id        : identifier shown in the UI
- description     : one-line plain-English summary for the demo
- patient_age     : integer age in years
- cpt_code        : the billed procedure code (CPT/HCPCS)
- diagnosis_codes : list of ICD-10 diagnosis codes (may be empty)
- modifiers       : list of billing modifiers on the line (e.g. "95", "50")
- place_of_service: 2-digit POS code ("02" = telehealth, "11" = office,
                    "23" = emergency room)
- units           : how many units of the procedure were billed
- prior_auth      : True/False — is an approved prior authorization on file?
- days_since_same : days since the same service was last billed for this
                    patient (None if it has never been billed before)
- expected        : NOTE-TO-SELF only — the outcome we designed this claim to hit
"""

CLAIMS = [
    {
        "claim_id": "CLM-001",
        "description": "Telehealth visit billed WITH modifier 95",
        "patient_age": 52,
        "cpt_code": "99213",
        "diagnosis_codes": ["E11.9"],   # type 2 diabetes follow-up
        "modifiers": ["95"],
        "place_of_service": "02",
        "units": 1,
        "prior_auth": False,
        "days_since_same": None,
        "expected": "PAY",   # telehealth done correctly
    },
    {
        "claim_id": "CLM-002",
        "description": "Telehealth visit billed WITHOUT modifier 95",
        "patient_age": 47,
        "cpt_code": "99213",
        "diagnosis_codes": ["I10"],     # hypertension follow-up
        "modifiers": [],
        "place_of_service": "02",
        "units": 1,
        "prior_auth": False,
        "days_since_same": None,
        "expected": "DENY",  # missing the required telehealth modifier
    },
    {
        "claim_id": "CLM-003",
        "description": "Screening colonoscopy for a 39-year-old, average risk",
        "patient_age": 39,
        "cpt_code": "45378",
        "diagnosis_codes": ["Z12.11"],  # screening for colon cancer, no high-risk dx
        "modifiers": [],
        "place_of_service": "22",
        "units": 1,
        "prior_auth": False,
        "days_since_same": None,
        "expected": "DENY",  # below the age-45 preventive threshold
    },
    {
        "claim_id": "CLM-004",
        "description": "Screening colonoscopy for a 58-year-old, average risk",
        "patient_age": 58,
        "cpt_code": "45378",
        "diagnosis_codes": ["Z12.11"],
        "modifiers": [],
        "place_of_service": "22",
        "units": 1,
        "prior_auth": False,
        "days_since_same": None,
        "expected": "PAY",   # meets the age threshold
    },
    {
        "claim_id": "CLM-005",
        "description": "Second annual wellness visit only 90 days after the last one",
        "patient_age": 66,
        "cpt_code": "G0439",
        "diagnosis_codes": ["Z00.00"],
        "modifiers": [],
        "place_of_service": "11",
        "units": 1,
        "prior_auth": False,
        "days_since_same": 90,          # inside the 365-day window
        "expected": "DENY",  # exceeds the once-per-12-months limit
    },
    {
        "claim_id": "CLM-006",
        "description": "Brain MRI billed without prior authorization",
        "patient_age": 44,
        "cpt_code": "70551",
        "diagnosis_codes": ["R51.9"],   # headache
        "modifiers": [],
        "place_of_service": "22",
        "units": 1,
        "prior_auth": False,
        "days_since_same": None,
        "expected": "FLAG",  # advanced imaging with no prior auth -> review
    },
    {
        "claim_id": "CLM-007",
        "description": "Bilateral procedure billed as 2 units WITHOUT modifier 50",
        "patient_age": 61,
        "cpt_code": "69210",            # cerumen removal, done both ears
        "diagnosis_codes": ["H61.23"],
        "modifiers": [],
        "place_of_service": "11",
        "units": 2,
        "prior_auth": False,
        "days_since_same": None,
        "expected": "FLAG",  # two units, no bilateral modifier -> review
    },
    {
        "claim_id": "CLM-008",
        "description": "Highest-level ER visit billed for a minor complaint",
        "patient_age": 30,
        "cpt_code": "99285",
        "diagnosis_codes": ["J00"],     # common cold
        "modifiers": [],
        "place_of_service": "23",
        "units": 1,
        "prior_auth": False,
        "days_since_same": None,
        "expected": "FLAG",  # top-level ER code + trivial dx -> medical-necessity review
    },
]


if __name__ == "__main__":
    # Run `python data/claims.py` to eyeball the sample claims.
    print(f"{len(CLAIMS)} sample claims loaded:\n")
    for c in CLAIMS:
        print(f"  [{c['claim_id']}] ({c['expected']:>4}) {c['description']}")
