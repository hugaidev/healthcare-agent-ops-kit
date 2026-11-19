---
name: temporal-workflow-scaffold
description: Scaffold a durable Temporal workflow with PHI-safe payloads, idempotent activities, retries and a human-approval signal. Use when a process spans minutes to days, waits on payers or people, or must survive restarts, such as prior authorization follow-up or claim resubmission.
---

# Temporal workflow scaffold

Use Temporal when the process is long-running, waits on external parties, or must be exactly
resumable. Keep short request/response tools as plain service calls.

## Design rules

1. **No PHI in workflow history, search attributes, memo or task-queue names.** Pass opaque refs
   (`pt_*`, `clm_*`). Resolve identities inside activities, behind the service boundary.
2. **Encrypt payloads** with a custom `PayloadCodec` (KMS-backed) so history is unreadable at
   rest even to Temporal operators.
3. **Workflows are deterministic.** All I/O, time, randomness and model calls live in activities.
4. **Activities are idempotent.** Derive an idempotency key from `(workflow_id, step)`; payers
   and clearinghouses may see retries.
5. **Retry only transient errors.** Set `non_retryable_error_types` for validation and
   authorization failures; bound attempts and total time.
6. **Human approval is a signal with a timeout.** Never auto-send outbound payer/patient content;
   on timeout, escalate rather than proceed.
7. **Audit every state transition** through the same audit log as the tools.
8. **Kill switch** behind a feature flag checked in an activity (not in workflow code).

## Skeleton

See `reference.md` for the full template (workflow, activities, worker, test with the
time-skipping environment).

## Checklist before merging

- [ ] Workflow ID is derived from a business key, so duplicates are rejected, not doubled.
- [ ] Replay test passes against a recorded history.
- [ ] Payload codec enabled in worker and client.
- [ ] Alert on stuck workflows (age over SLA) and on approval-timeout rate.
- [ ] Eval cases cover the escalation branches.
