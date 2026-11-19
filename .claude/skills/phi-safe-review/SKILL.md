---
name: phi-safe-review
description: Review a change for PHI exposure, audit-trail gaps, authorization and infrastructure risk before a PR. Use when code touches logging, errors, tools, data access, prompts, test fixtures or Terraform, or when asked to check a change for HIPAA or compliance issues.
---

# PHI-safe review

## 1. Run the deterministic gate

```bash
uv run opskit-review scan <changed files or dirs> --fail-on high
```

Fix every finding or justify it with a written suppression
(`# phi-review: ignore[RULE] reason`). A suppression with no reason is itself a finding.

## 2. Walk the checklist (rules cannot see these)

| Area | Question |
|---|---|
| Data flow | Where can identifiers enter, and where do they leave (logs, errors, metrics, prompts, files)? |
| Minimum necessary | Does the caller (or the model) receive only the fields it needs? Opaque refs instead of identities? |
| Audit | Does every read or write of patient data create an audit event with actor, role, tool, outcome? |
| AuthZ | New capability means new `Scope`; is it mapped to the narrowest role? Any default-allow? |
| Failure | Does a timeout, missing record or ambiguous input fail closed with `requires_human_review`? |
| Validation | Do errors report field names and types only, never the rejected value? |
| Model output | Is any model/LLM output executed, sent outward, or trusted without a human step? Is injection text inert? |
| Secrets | Anything credential-like in code, config, fixtures or CI? |
| Infra | Encryption at rest and in transit, no public exposure, no wildcard IAM, retention set? |
| Tests | Is there a test (and an eval case if behavior changed) for the unhappy path? |

## 3. Report

Use a table: severity, `path:line`, issue, fix. Finish with `APPROVE`, `APPROVE WITH CHANGES`
or `BLOCK`. For a large change, delegate to the `phi-reviewer` subagent so the review runs in
isolated context.

See `reference.md` for the regulatory mapping behind each check.
