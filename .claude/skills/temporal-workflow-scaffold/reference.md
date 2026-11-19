# Template: prior-authorization follow-up workflow

Scaffold only. `temporalio` is not a dependency of this repo; add it in the service that owns
the workflow (`uv add temporalio`).

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy


@dataclass(frozen=True)
class PaRequest:
    patient_ref: str  # opaque, never a name or member ID
    payer_id: str
    cpt_code: str
    units: int


@activity.defn
async def submit_prior_auth(req: PaRequest, idempotency_key: str) -> str:
    """Calls the payer adapter. Returns an opaque case reference."""
    ...


@activity.defn
async def check_prior_auth_status(case_ref: str) -> str:
    """Returns 'approved' | 'denied' | 'pending'."""
    ...


@activity.defn
async def notify_reviewer(case_ref: str, reason: str) -> None:
    """Creates a task for a human; payload contains refs only."""
    ...


@workflow.defn
class PriorAuthFollowUp:
    def __init__(self) -> None:
        self._approved_by_human: bool | None = None

    @workflow.signal
    def human_decision(self, approved: bool) -> None:
        self._approved_by_human = approved

    @workflow.run
    async def run(self, req: PaRequest) -> str:
        retry = RetryPolicy(
            maximum_attempts=5,
            backoff_coefficient=2.0,
            non_retryable_error_types=["ValidationError", "AuthorizationError"],
        )
        key = f"{workflow.info().workflow_id}:submit"
        case_ref = await workflow.execute_activity(
            submit_prior_auth,
            args=[req, key],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )
        for _ in range(14):  # poll for up to ~14 days
            status = await workflow.execute_activity(
                check_prior_auth_status,
                case_ref,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry,
            )
            if status in {"approved", "denied"}:
                break
            await workflow.sleep(timedelta(days=1))
        else:
            status = "pending"

        if status != "approved":
            await workflow.execute_activity(
                notify_reviewer,
                args=[case_ref, f"status={status}"],
                start_to_close_timeout=timedelta(seconds=30),
            )
            try:
                await workflow.wait_condition(
                    lambda: self._approved_by_human is not None, timeout=timedelta(days=2)
                )
            except TimeoutError:
                return "escalated_timeout"  # never auto-proceed
            return "approved_by_human" if self._approved_by_human else "closed_by_human"
        return "approved"
```

## Test

Use `WorkflowEnvironment.start_time_skipping()` so day-long sleeps run instantly, and assert
that no activity payload contains anything but `pt_*`/`clm_*` references.

## Worker and client

Create the client with `data_converter=dataclasses.replace(default(), payload_codec=KmsCodec())`
and give the worker the same converter. Run workers in private subnets with a task role limited
to the activities they execute.
