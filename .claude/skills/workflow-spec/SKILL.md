---
name: workflow-spec
description: Write a spec for a new agent, automated workflow or tool before building it. Use when scoping an ambiguous operational problem such as benefits verification, prior authorization, intake, claims or clinical documentation, or when asked to design, spec or plan a new workflow.
---

# Workflow spec

Write `docs/specs/<kebab-name>.md`. Interview the requester first if any section would be a
guess; ambiguity is cheaper to resolve in a conversation than in production.

## Template

```markdown
# <Workflow name>

Status: draft | Owner: <name> | Date: <YYYY-MM-DD>

## Problem
Who does this today, how long it takes, what it costs, how often it goes wrong. One paragraph
plus the baseline numbers we will measure against.

## Users and actors
Humans (roles), systems (payers, clearinghouses, EHR), and the agent. Who approves what.

## Scope
In scope / explicitly out of scope for v1.

## Data classification
Every field in and out: PHI / non-PHI, source, retention, who may see it. State where opaque
references replace identities. Flag any 42 CFR Part 2 (substance use) data.

## Flow
Numbered steps. Mark each: deterministic code, model call, or human decision.

## Human-in-the-loop
Which outcomes always escalate (low confidence, no matching rule, money moves, anything sent
externally). SLA for human response. What the agent does while waiting.

## Failure modes
Table: failure, detection, behavior (fail closed), recovery. Include upstream timeout,
duplicate request, partial completion, wrong-payer, prompt injection in free text.

## Controls
AuthZ scopes and roles, audit events, rate limits, retention, kill switch (feature flag).

## Evals and metrics
Case categories, safety-critical cases, thresholds (accuracy, unsafe-action rate = 0,
PHI leaks = 0, latency). Production metrics and alert thresholds.

## Rollout
Feature flag, shadow mode first, cohort ramp, rollback trigger, who is on call.

## Open questions
```

## Rules

- Quantify the problem before proposing the solution.
- Every model call needs a stated reason a deterministic rule would not do.
- No spec ships without an eval plan and a defined human-escalation path.
- After approval, create the eval cases (skill `write-evals`) before the implementation.
