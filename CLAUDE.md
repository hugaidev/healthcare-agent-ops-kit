# Project instructions

Reference kit for PHI-safe agent tooling in regulated healthcare operations. All data in this
repo is synthetic. Treat every change as if it will run against real PHI.

## Commands

```bash
uv sync --extra llm          # install
uv run pytest                # tests + coverage gate (85%)
uv run ruff check . && uv run ruff format --check .
uv run mypy                  # strict
uv run opskit-evals          # eval suite; must exit 0 (thresholds in evals/thresholds.json)
uv run opskit-review scan src infra   # compliance rules; same gate as CI
```

## Non-negotiable rules (PHI and audit)

1. **No PHI in code, logs, errors, comments, commit messages or fixtures.** Use opaque refs
   (`pt_demo000001`, `clm_abc123456`). Realistic-looking identifiers are only allowed in
   `tests/` and `evals/data/` (a hook enforces this).
2. **Never log request payloads or model output.** Log `trace_id`, tool name, status and error
   *type*. Never `print()` in `src/opskit/mcp_server/`: stdout is the MCP protocol channel.
3. **Every tool goes through `BenefitsService._execute`**: authorization, rate limit, validation,
   audit. A new tool that skips it is a bug (rule AUD001).
4. **Fail closed.** No identity, unknown role, audit write failure or ambiguous payer data means
   deny or escalate with `requires_human_review=true`. Never guess a coverage or auth answer.
5. **Validation errors report field names and types only.** Never echo the rejected value.
6. **Least privilege.** New capabilities get a new `Scope`; map it to the narrowest role.
7. **Drafts are never sent.** Anything outbound to a payer or patient needs a human approval step.
8. **Secrets come from the environment or a secrets manager.** Never commit them.

## Workflow

- Spec first for any new workflow or tool: use the `workflow-spec` skill. Include data
  classification, failure modes, human-in-the-loop points and the eval plan.
- Every behavior change ships with eval cases (`write-evals` skill). Safety-critical cases must
  keep `unsafe_action_rate` at 0.
- Run the `phi-safe-review` skill (or the `phi-reviewer` subagent) before opening a PR.
- Infrastructure is Terraform only, reviewed by CI. Never run `terraform apply` locally.
- Small PRs, conventional commits, no `--no-verify`.

## Code conventions

- Python 3.12, Pydantic v2 models with `extra="forbid"`, strict mypy, ruff clean.
- Pure functions for decisions (see `payer_sim.evaluate_prior_auth`); side effects at the edges.
- Suppressing a review rule requires a written reason:
  `# phi-review: ignore[RULE] why this is safe`.
