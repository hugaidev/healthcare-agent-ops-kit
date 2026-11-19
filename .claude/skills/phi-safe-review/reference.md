# Regulatory mapping for review checks

Engineering interpretation, not legal advice. Confirm with your compliance owner.

| Check | Control it supports |
|---|---|
| No PHI in logs or errors | HIPAA Security Rule 45 CFR 164.312(b) audit controls and 164.502(b) minimum necessary; logs are retained and widely readable |
| Opaque references, field-level scoping | Minimum necessary (164.502(b), 164.514(d)) |
| Audit event on every access | 164.312(b); information system activity review 164.308(a)(1)(ii)(D) |
| Hash-chained, append-only audit | Integrity 164.312(c)(1); retain documentation six years (164.316(b)(2)) |
| Role-to-scope policy, fail closed | Access control 164.312(a)(1); workforce access management 164.308(a)(4) |
| Unique actor on every call | Unique user identification 164.312(a)(2)(i); authentication 164.312(d) |
| Encryption at rest and in transit | 164.312(a)(2)(iv), 164.312(e)(1) addressable specifications; treat as required |
| Human review of outbound drafts | Reduces risk of erroneous disclosure and of automated decisions without oversight |
| Substance-use-disorder records | 42 CFR Part 2 applies stricter consent rules; flag any psychiatry/SUD data path for compliance review |
| AI governance | NIST AI RMF (Govern, Map, Measure, Manage) for evals, monitoring and human oversight |
