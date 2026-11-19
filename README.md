# Healthcare Agent Ops Kit

> **A reference based on real work.** The patterns here (opaque references, guarded tool
> execution, tamper-evident audit, fail-closed escalation, safety-gated evals, PHI-aware
> engineering workflow) come from systems I built and put into production in regulated
> environments. This repository is the generalized, open version: it uses a synthetic payer and
> no real data, and it is a control skeleton, not a deployed product. 

A reference implementation of how to build **AI agents and AI-assisted engineering workflows
for regulated healthcare operations**: an MCP server with enterprise controls, Claude Code
configuration that enforces PHI rules, reusable skills, a compliance review bot, and an eval
harness that gates releases on safety metrics.

The example domain is outpatient therapy practice operations (ABA, speech, occupational and
physical therapy, behavioral health): benefits verification, prior authorization and claim
appeals. Everything runs offline against a **synthetic payer**; no real data is involved.

> Engineering reference, not legal advice or a compliance certification. Map it to your own
> risk analysis, BAAs and counsel. See [docs/COMPLIANCE.md](docs/COMPLIANCE.md).

## What is in the box

| Piece | Where | What it shows |
|---|---|---|
| **MCP server** | `src/opskit/mcp_server`, `src/opskit/service.py` | Tools an agent can call, wrapped in one guarded path: authorization, rate limit, validation, hash-chained audit, safe errors |
| **PHI controls** | `src/opskit/phi.py`, `models.py` | Opaque references instead of identities, redaction, log scrubbing, strict schemas |
| **Audit trail** | `src/opskit/audit.py` | Tamper-evident log with HMAC'd arguments; verifiable from CLI and as a tool |
| **Claude Code config** | `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks` | Project rules, least-privilege permissions, hooks that block PHI/secrets before they are written and feed review findings back to the model |
| **Skills** | `.claude/skills` | `phi-safe-review`, `workflow-spec`, `write-evals`, `temporal-workflow-scaffold` |
| **Subagents** | `.claude/agents` | Read-only `phi-reviewer`, `eval-analyst` |
| **Review bot** | `src/opskit/review`, `.github/workflows` | Deterministic rules for Python and Terraform (SARIF into code scanning) plus an optional advisory LLM pass |
| **Evals** | `src/opskit/evals`, `evals/` | 28 cases, per-category accuracy, unsafe-action rate and PHI-leak count as release gates |
| **Infra example** | `infra/examples` | Terraform for an encrypted, private database and an object-locked audit bucket |

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync --extra llm
uv run pytest                     # 61 tests, coverage gate 85%
uv run opskit-evals               # eval suite with thresholds
uv run opskit-review scan src infra
```

### Use the MCP server from Claude Code

`.mcp.json` registers it for this repo. Identity is mandatory (fail closed):

```bash
OPS_ACTOR=jane OPS_ROLE=billing_specialist uv run opskit-mcp
```

Then ask Claude Code: *"Does `pt_demo000001` on `acme_health` need prior auth for 97153,
10 units?"* Try the failure paths too: an unknown CPT code, a payer mismatch, a raw SSN passed
as a reference, or `OPS_ROLE=compliance_auditor` calling an eligibility tool.

### Verify the audit trail

```bash
uv run opskit-audit-verify .audit/audit.jsonl
```

## Design principles

1. **The model never needs PHI.** Tools take opaque references; identity resolution happens
   behind the service boundary (minimum necessary). See [ADR 0001](docs/adr/0001-opaque-references.md).
2. **Controls live in one place.** Every tool goes through `BenefitsService._execute`, and a
   review rule fails the build if a tool bypasses it.
3. **Fail closed, escalate ambiguity.** Unknown rule, payer mismatch, missing record, audit
   failure: deny or set `requires_human_review`. The system never guesses.
4. **Deterministic gates, advisory AI.** Hard controls are code and tests. The LLM review is
   advisory and runs on redacted diffs. See [ADR 0002](docs/adr/0002-deterministic-gate-advisory-llm.md).
5. **Measure safety, not only accuracy.** Unsafe-action rate and PHI leaks must be 0 to ship.
6. **Humans approve anything outbound.** Appeals are drafts, never sent.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Regulatory framework and control mapping](docs/COMPLIANCE.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Evals](docs/EVALS.md)
- [Security policy](SECURITY.md) and [contributing](CONTRIBUTING.md)

## Taking this to production

This repo is the control skeleton, not a deployable product. Before real PHI: replace the
synthetic payer with a clearinghouse adapter, resolve identity from your IdP (OIDC/mTLS) instead
of environment variables, ship audit events to an append-only store with six-year retention,
put a signed BAA with every model and infrastructure vendor, and run a documented risk analysis.
The full list is in [docs/COMPLIANCE.md](docs/COMPLIANCE.md#production-readiness-checklist).

## License

MIT, see [LICENSE](LICENSE).
