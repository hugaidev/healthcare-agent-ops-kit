## What and why

## Checklist

- [ ] No PHI in code, logs, errors, fixtures or this description (synthetic refs only)
- [ ] New or changed behavior has tests and eval cases; unsafe-action rate and PHI leaks remain 0
- [ ] Every new tool goes through the guarded service (authz, rate limit, audit)
- [ ] New capability has a dedicated scope mapped to the narrowest role
- [ ] Failures fail closed; ambiguous cases set `requires_human_review`
- [ ] Docs updated (`docs/`, ADR if a design decision changed)
- [ ] `uv run pytest`, `ruff`, `mypy`, `opskit-evals`, `opskit-review scan` all pass locally
