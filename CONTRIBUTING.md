# Contributing

1. Read [CLAUDE.md](CLAUDE.md): the non-negotiable rules apply to humans and agents alike.
2. For a new tool or workflow, write a short spec first (`workflow-spec` skill) and add eval
   cases before the implementation (`write-evals` skill).
3. Use only synthetic data. Realistic-looking identifiers are allowed in `tests/` and
   `evals/data/` only.
4. Before opening a PR:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv run opskit-evals
uv run opskit-review scan src infra
```

5. Conventional commit messages, small PRs, fill in the PR template. Never use `--no-verify`.
6. Suppressing a review rule needs a written reason in the comment; reviewers will check it.
