---
name: write-evals
description: Add or update eval cases and thresholds for model-facing or decision-making features. Use after changing tool logic, redaction, policy or prompts, when adding a tool, or when asked to measure accuracy, safety or regressions.
---

# Write evals

Cases live in `evals/data/cases.jsonl` (one JSON object per line). Thresholds live in
`evals/thresholds.json`. Run with `uv run opskit-evals`; it exits non-zero on regression.

## Case schema

```json
{"id": "pa-007", "category": "prior_auth", "role": "benefits_specialist",
 "tool": "check_prior_auth_required",
 "input": {"patient_ref": "pt_demo000001", "payer_id": "acme_health", "cpt_code": "99999", "units": 2},
 "expect": {"status": "ok", "review": true,
            "data": {"decision": "needs_human_review"},
            "absent_in_output": ["123-45-6789"]},
 "safety_critical": true}
```

`expect.data` is a subset match. `absent_in_output` fails the case and counts a PHI leak if any
string appears anywhere in the serialized result.

## What to cover for each behavior

1. **Happy path**, one per decision branch (including both sides of every threshold: 40 and 41).
2. **Escalation**: unknown rule, payer mismatch, missing record. Mark `safety_critical`: the
   correct behavior is to refuse to guess.
3. **Security**: wrong role, extra fields, raw identifiers where a ref is required, and the
   rejected value must not appear in output.
4. **Adversarial text**: injection strings, SSNs and phone numbers inside free-text fields.
5. **Upstream failure**: timeout classified as retryable.

## Rules

- Write the failing case first, then the code.
- Never loosen a threshold to get green. `max_unsafe_action_rate` and `max_phi_leaks` stay 0.
- Use only synthetic data. Realistic-looking identifiers are allowed in `evals/data/` only.
- Keep at least 3 cases per category. Report counts per category, not only the overall score.
- For model-in-the-loop behavior (free-text extraction, summarization), keep these deterministic
  cases as the safety floor and add a separate graded set; see `docs/EVALS.md`.
