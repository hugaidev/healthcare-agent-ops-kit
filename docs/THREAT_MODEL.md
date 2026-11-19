# Threat model

Scope: the MCP server, its service layer, audit log, and the Claude Code engineering workflow.

## Assets

PHI (never held by the tools themselves, reachable through the reference vault in production),
audit integrity, credentials, the payer connection, and the integrity of deployed code.

## Threats and mitigations

| # | Threat | Vector | Mitigation | Residual risk |
|---|---|---|---|---|
| T1 | PHI reaches the model or its logs | Agent passes names or IDs; free text contains identifiers | Opaque-reference schema, `extra=forbid`, redaction of free text, log scrubbing filter, error messages without values | Regex redaction is heuristic; novel formats can slip through. Treat free text as the main residual channel and keep it short and optional |
| T2 | Prompt injection through free text | `clinical_rationale` or payer remarks contain instructions | Tools are deterministic and take no model-derived instructions; free text is redacted and quoted as unverified; drafts are never sent | A human reading a draft could be misled; reviewers are trained to treat quoted text as data |
| T3 | Unauthorized access or privilege escalation | Calling a tool outside the role | Role-to-scope map, deny by default, denial is audited | In stdio mode, identity comes from launch environment. In production use a gateway that derives identity from the IdP |
| T4 | Bulk enumeration of members | Agent loop or compromised session | Per-actor sliding-window rate limit; every call audited | Limits are per process; use a shared limiter and anomaly alerts in production |
| T5 | Audit tampering | Edit or delete log lines | Hash chain, sequence numbers, verification tool, external anchoring recommended | Attacker with write access can truncate the tail; anchor the head and ship to object-locked storage |
| T6 | Silent audit loss | Disk full, permission error | Audit write failure returns an error with no data | Availability traded for integrity by design |
| T7 | Wrong answer from ambiguity | Unknown CPT, payer mismatch, missing rule | Explicit `needs_human_review`; safety-critical eval cases fail the build if the system guesses | Rules in the payer table must be kept current; version recorded in each answer |
| T8 | Secrets committed or exfiltrated | Pasted into code, read from `.env` | Hook blocks credential patterns, permissions deny reading `.env`, gitleaks in CI, SEC001 rule | Secrets in places the patterns do not cover |
| T9 | Destructive or unreviewed infra change | Agent runs `terraform apply` | Permissions deny it, hook blocks it, infra changes only through reviewed CI | Humans with cloud credentials remain a trust boundary |
| T10 | Weak infrastructure defaults | Public bucket, wildcard IAM, unencrypted DB | Rules TF001 to TF005 in CI as SARIF; CODEOWNERS on `infra/` | Rules are intentionally simple; use tfsec or Checkov as well |
| T11 | Vulnerable or malicious dependency | Supply chain | `pip-audit`, lockfile, Dependabot, minimal dependency set | Zero-day windows |
| T12 | The review tool leaks code | LLM review sends diffs to a vendor | Advisory only, redacts PHI first, opt-in via secret, skipped for forks | Source code itself is shared with the vendor; use a BAA/enterprise agreement |

## Out of scope for this reference

Network design, key management beyond the Terraform example, endpoint security of developer
machines, and the reference-to-identity vault implementation.
