# ADR 0001: Tools accept opaque references, never identities

Status: accepted

## Context

Agents and the models behind them are an untrusted-ish boundary: their inputs and outputs are
logged, traced, cached and sometimes sent to third parties. HIPAA minimum necessary
(45 CFR 164.502(b)) says each actor should see only the PHI it needs. Benefits and prior-auth
decisions need *which* patient and plan, not who the person is.

## Decision

Tool parameters are opaque references (`pt_*`, `clm_*`) validated by strict patterns.
Resolution to real identities happens behind the service boundary in an access-controlled,
audited vault (a synthetic table in this repo). Models reject unknown fields. Validation errors
name fields and types, never values. Free text is optional, length-limited and redacted.

## Consequences

- A prompt, trace or log cannot contain what was never provided: PHI exposure shrinks from
  "everywhere the agent runs" to "the vault and the payer adapter".
- Debuggability relies on `trace_id` and references rather than names; support tooling for
  humans resolves references through the vault with its own authorization.
- Free-text fields remain a residual channel; they are redacted and covered by adversarial evals.
- Slightly more plumbing: callers must obtain references from an upstream system.
