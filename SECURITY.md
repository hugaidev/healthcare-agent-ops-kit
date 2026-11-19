# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's
[private vulnerability reporting](../../security/advisories/new) on this repository, with steps
to reproduce and the affected version. Expect an acknowledgement within 3 business days.

## Data handling

This repository contains **synthetic data only**. If you find something that looks like real
PHI or a real credential, report it privately right away so it can be removed from history.

## Scope

In scope: the code in `src/`, the hooks and configuration in `.claude/`, the CI workflows and
the Terraform example. Out of scope: findings that require already having the ability to edit
the audit file together with its external anchor, or that depend on running the synthetic payer
as if it were production.

## Supported versions

Only the latest release on `main` receives fixes.
