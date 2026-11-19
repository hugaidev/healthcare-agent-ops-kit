# Regulatory framework and control mapping

> Engineering interpretation for design discussions. Not legal advice and not a certification.
> Confirm scope, applicability and interpretation with your privacy officer and counsel.

## Regulatory landscape for healthcare operations agents

| Framework | Why it matters here |
|---|---|
| **HIPAA Privacy Rule** (45 CFR Part 164 Subpart E) | Uses and disclosures of PHI; **minimum necessary** (164.502(b), 164.514(d)); business associate contracts (164.502(e), 164.504(e)) |
| **HIPAA Security Rule** (Subpart C) | Administrative, physical and technical safeguards for ePHI: access control 164.312(a), audit controls 164.312(b), integrity 164.312(c), authentication 164.312(d), transmission security 164.312(e); risk analysis 164.308(a)(1)(ii)(A); documentation retention 164.316(b)(2) |
| **Breach Notification Rule** (Subpart D) | Incident response, notification obligations, and why a PHI leak in a log is a reportable-event candidate |
| **HITECH Act** | Business associates are directly liable; breach notification and enforcement |
| **42 CFR Part 2** | Stricter consent rules for substance use disorder records; relevant when expanding into psychiatry and behavioral health |
| **HIPAA standard transactions** (X12 5010: 270/271 eligibility, 278 prior authorization, 837/835 claims) | The interface shape of benefits, auth and claim workflows |
| **CMS Interoperability and Prior Authorization final rule (CMS-0057-F)** | Impacted payers must meet prior authorization decision timeframes (72 hours expedited, 7 calendar days standard) from 2026 and expose prior-authorization APIs from 2027; shapes what operations tooling can automate and measure |
| **State law** | Mental health, minors, ABA coverage mandates and consumer health data statutes can be stricter than HIPAA |
| **NIST AI RMF** (Govern, Map, Measure, Manage) | Framework for evals, monitoring, human oversight and accountability of AI features |
| **SOC 2 / HITRUST** | Customer and payer assurance; common contractual requirement |

Vendors: every party that creates, receives, maintains or transmits PHI on your behalf
(model providers, cloud, observability, ticketing) needs a **business associate agreement**
and an approved configuration (for model APIs: zero or minimal data retention, no training on
inputs). This kit sends no PHI to any model by design; the optional LLM review runs on redacted
code diffs only.

## Control mapping

| Requirement | Implementation | Verified by |
|---|---|---|
| Minimum necessary (164.502(b)) | Tools accept opaque references only; extra fields rejected (`extra="forbid"`) | `models.py`, eval `sec-001`, `sec-002`, `sec-005` |
| Access control, unique user ID (164.312(a)(1), (a)(2)(i)) | Mandatory `OPS_ACTOR` + `OPS_ROLE`; role-to-scope map; fail closed | `policy.py`, tests, eval `sec-003`, `sec-004` |
| Audit controls (164.312(b)) | Every call, including denials, writes an audit event before data is returned; audit failure returns no data | `service.py`, `test_audit_failure_fails_closed` |
| Integrity (164.312(c)(1)) | Hash-chained events; tamper and deletion detected; verification CLI and tool | `audit.py`, `test_audit.py` |
| No PHI in logs | Scrubbing log filter; payloads never logged; errors expose type only; rule PHI001 | `phi.py`, review rule, hook |
| Authentication, transmission security (164.312(d), (e)) | Production identity from IdP/mTLS; TLS everywhere; DB and bucket encryption in Terraform example | `infra/examples/main.tf` |
| Encryption at rest | KMS-backed RDS and S3, rotation on | rules TF003, TF002 |
| Retention (164.316(b)(2)) | Object Lock, 6-year compliance mode on the audit bucket | `infra/examples/main.tf` |
| Least privilege for engineers and agents | Claude Code permissions deny secrets, force-push, `terraform apply`, network fetches; hooks block PHI writes | `.claude/settings.json`, `.claude/hooks` |
| Change management and auditability | PR template, CODEOWNERS on sensitive paths, SARIF into code scanning, suppressions require a reason | `.github/`, rule SUP001 |
| Human oversight of AI output | `requires_human_review` on every ambiguous result; appeals are never sent | `service.py`, evals `app-*` |
| AI measurement (NIST AI RMF Measure) | Unsafe-action rate and PHI-leak count are release gates | `evals/thresholds.json` |
| Supply chain | `pip-audit`, gitleaks, Dependabot, pinned lockfile | `.github/workflows/ci.yml` |

## Production readiness checklist

- [ ] Documented, current **risk analysis** (164.308(a)(1)(ii)(A)) covering this system
- [ ] **BAAs** signed with every vendor touching PHI; model API retention configured accordingly
- [ ] Identity from your IdP (OIDC/mTLS) instead of environment variables; short-lived credentials
- [ ] Audit events shipped to an append-only store, six-year retention, chain head anchored externally, alerting on verification failure
- [ ] Real payer adapter with timeouts, retries with backoff, circuit breaker, and idempotency keys
- [ ] Reference-to-identity vault with its own access policy and audit
- [ ] Break-glass and incident response runbook; breach assessment procedure (Subpart D)
- [ ] Production observability without PHI (Datadog or equivalent with redaction at the source)
- [ ] Feature flags and a kill switch per workflow; shadow mode before enforcement
- [ ] Workforce training and access reviews; offboarding removes agent and human credentials
- [ ] Data classification for 42 CFR Part 2 and state-specific categories before expanding specialties
- [ ] Penetration test and review of prompt-injection paths for every free-text field
