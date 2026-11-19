# Evals

Evals are the release gate for any model-facing or decision-making behavior. This repo ships a
deterministic suite for the tool layer and a pattern for extending it to model-in-the-loop
behavior.

## What is measured

| Metric | Definition | Gate |
|---|---|---|
| Accuracy | Passing cases / all cases, also reported per category | `min_accuracy` 1.0 for deterministic logic |
| **Unsafe-action rate** | Failures among cases tagged `safety_critical` (system guessed, leaked, or acted without authorization) | must be 0 |
| **PHI leaks** | Forbidden strings that appear anywhere in a tool result | must be 0 |
| Latency p50 / p95 | Wall time per call | p95 under 1000 ms (includes an fsync per audited call) |

Why separate "unsafe" from "wrong": a wrong prior-auth answer on a routine case is a defect; a
confident answer where the correct behavior was to escalate is a safety event. They are tracked,
alerted and prioritized differently.

## Running

```bash
uv run opskit-evals                      # writes evals/reports/latest.{json,md}
uv run opskit-evals --cases my.jsonl     # custom suite
```

CI runs the suite on every PR and uploads the report as an artifact.

## Case design

See the `write-evals` skill for the schema. The shipped suite has 28 cases across eligibility,
prior authorization, appeals and security. It covers threshold boundaries (40 vs 41 units),
upstream timeouts and every decision branch. The 13 safety-critical cases are the ones where
the correct behavior is to refuse or escalate: unknown codes, payer mismatch, missing members,
raw identifiers where a reference is required, extra fields, wrong roles, and PHI or injection
strings in free text.

## Extending to model-in-the-loop behavior

For features where a model reads or writes free text (clinical documentation summaries, intake
extraction, appeal letters):

1. **Keep the deterministic suite as the safety floor.** It validates the controls around the
   model regardless of model output.
2. **Add a graded set** with human-labeled expected outputs. Grade with exact match where
   possible (extracted fields), rubric-based LLM grading where not, and calibrate the grader
   against a human-labeled sample.
3. **Track regressions per model and prompt version.** Pin the model ID in the eval run and
   record it in the report.
4. **Run offline in CI on synthetic data; sample production traffic for online monitoring**
   (with PHI redaction at the source) and feed disagreements back into the suite.
5. **Add adversarial cases for every free-text field**: injection, identifiers, very long input.

## Production metrics to pair with evals

Escalation rate (too low means overconfidence, too high means no value), human override rate,
time to resolution, denial rate by rule version, audit verification failures, rate-limit hits
per actor.
