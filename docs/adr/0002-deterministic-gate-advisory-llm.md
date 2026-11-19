# ADR 0002: Deterministic rules gate merges; the LLM review is advisory

Status: accepted

## Context

Code review for a regulated codebase needs checks that are reproducible, explainable to an
auditor, and independent of any vendor. LLM review is good at judgment (business-logic risk,
missing tests) but non-deterministic and can be influenced by the content it reads.

## Decision

- The merge gate is `opskit-review scan`: AST rules for Python and block rules for Terraform,
  emitted as SARIF into code scanning. Suppression requires a written reason.
- The LLM pass (`opskit-review llm`) posts a non-blocking PR comment. It receives a diff with
  PHI redacted, a system prompt that marks the diff as untrusted data, and runs only for
  same-repo PRs with the secret configured.
- Claude Code runs the same rules after every edit (PostToolUse hook), so most issues are fixed
  before a PR exists.

## Consequences

- Builds are reproducible and failures are explainable by rule id and control reference.
- Coverage of the rules is limited by what we encode; they complement, not replace, tfsec,
  Checkov, CodeQL and human review (CODEOWNERS covers sensitive paths).
- LLM review cost and latency are bounded (diff size cap, one call per push).
- Source code is shared with the model vendor when enabled; use an enterprise agreement.
