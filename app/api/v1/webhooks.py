"""GitHub webhook handlers for workflow job events."""

import hashlib
import hmac
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.github.client import GitHubClient
from app.models import Runner
from app.services.label_policy_service import LabelPolicyService, LabelPolicyViolation

logger = structlog.get_logger()

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify GitHub webhook signature.

    Args:
        payload: Raw request body
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret

    Returns:
        True if signature is valid
    """
    if not secret:
        # No secret configured - skip verification (not recommended for production)
        return True

    if not signature:
        return False

    # GitHub sends signature as "sha256=<hex>"
    if not signature.startswith("sha256="):
        return False

    expected_signature = signature[7:]  # Remove "sha256=" prefix
    computed_signature = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


async def validate_runner_labels(
    runner_name: str,
    runner_id: int,
    db: Session,
    settings: Settings,
) -> tuple[Optional[Runner], Optional[LabelPolicyViolation]]:
    """
    Validate a runner's labels against policy.

    Args:
        runner_name: Name of the runner
        runner_id: GitHub runner ID
        db: Database session
        settings: Application settings

    Returns:
        Tuple of (runner, violation) - runner is None if not found in DB,
        violation is None if labels are valid
    """
    # Look up runner in our database
    runner = db.query(Runner).filter(Runner.runner_name == runner_name).first()

    if not runner:
        logger.warning(
            "webhook_runner_not_found",
            runner_name=runner_name,
            github_runner_id=runner_id,
        )
        return None, None

    # Fetch actual labels from GitHub
    github_client = GitHubClient(settings)
    github_runner = await github_client.get_runner_by_id(runner_id)

    if not github_runner:
        logger.warning(
            "webhook_github_runner_not_found",
            runner_name=runner_name,
            github_runner_id=runner_id,
        )
        return runner, None

    # Validate labels against policy
    label_policy_service = LabelPolicyService(db)
    try:
        label_policy_service.validate_labels(
            runner.provisioned_by, github_runner.labels
        )
        return runner, None
    except LabelPolicyViolation as e:
        return runner, e


@router.post("/github")
async def handle_github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
):
    """
    Handle GitHub webhook events.

    Currently handles:
    - workflow_job: Validates runner labels when jobs start

    **Authentication:** Webhook signature verification (if secret configured)
    """
    # Read raw body for signature verification
    body = await request.body()

    # Verify signature
    if not verify_webhook_signature(
        body, x_hub_signature_256 or "", settings.github_webhook_secret
    ):
        logger.warning(
            "webhook_signature_invalid",
            delivery_id=x_github_delivery,
            event=x_github_event,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    logger.info(
        "webhook_received",
        event=x_github_event,
        delivery_id=x_github_delivery,
        action=payload.get("action"),
    )

    # Handle workflow_job events
    if x_github_event == "workflow_job":
        return await handle_workflow_job(payload, db, settings)

    # Acknowledge other events
    return {"status": "ignored", "event": x_github_event}


async def handle_workflow_job(
    payload: dict,
    db: Session,
    settings: Settings,
) -> dict:
    """
    Handle workflow_job webhook event.

    On 'in_progress' action:
    - Look up runner by name
    - Fetch runner's actual labels from GitHub
    - Validate against user's label policy
    - If violation: log security event and optionally cancel workflow

    Args:
        payload: Webhook payload
        db: Database session
        settings: Application settings

    Returns:
        Response dict with status
    """
    action = payload.get("action")
    workflow_job = payload.get("workflow_job", {})
    repository = payload.get("repository", {})

    # Only process in_progress events (when job actually starts)
    if action != "in_progress":
        return {"status": "ignored", "reason": f"action={action}"}

    runner_name = workflow_job.get("runner_name")
    runner_id = workflow_job.get("runner_id")
    run_id = workflow_job.get("run_id")
    repo_name = repository.get("name")
    repo_full_name = repository.get("full_name")

    if not runner_name or not runner_id:
        logger.debug(
            "webhook_missing_runner_info",
            runner_name=runner_name,
            runner_id=runner_id,
        )
        return {"status": "ignored", "reason": "missing runner info"}

    logger.info(
        "workflow_job_in_progress",
        runner_name=runner_name,
        runner_id=runner_id,
        run_id=run_id,
        repo=repo_full_name,
    )

    # Validate runner labels
    runner, violation = await validate_runner_labels(
        runner_name, runner_id, db, settings
    )

    if not runner:
        return {"status": "ignored", "reason": "runner not managed by this service"}

    if not violation:
        return {"status": "ok", "labels_valid": True}

    # Label policy violation detected
    logger.error(
        "webhook_label_policy_violation",
        runner_name=runner_name,
        runner_id=runner_id,
        run_id=run_id,
        repo=repo_full_name,
        provisioned_by=runner.provisioned_by,
        invalid_labels=list(violation.invalid_labels),
    )

    # Log security event
    label_policy_service = LabelPolicyService(db)
    action_taken = None

    # Determine enforcement action
    if settings.label_policy_enforcement == "enforce":
        # Cancel the workflow run
        github_client = GitHubClient(settings)
        try:
            cancelled = await github_client.cancel_workflow_run(repo_name, run_id)
            if cancelled:
                action_taken = "workflow_cancelled"
                logger.info(
                    "workflow_cancelled_for_policy_violation",
                    run_id=run_id,
                    repo=repo_full_name,
                )
            else:
                action_taken = "workflow_cancel_failed"
                logger.warning(
                    "workflow_cancel_failed",
                    run_id=run_id,
                    repo=repo_full_name,
                )
        except Exception as e:
            action_taken = f"workflow_cancel_error: {str(e)}"
            logger.error(
                "workflow_cancel_error",
                run_id=run_id,
                repo=repo_full_name,
                error=str(e),
            )
    else:
        action_taken = "audit_only"

    # Log security event
    label_policy_service.log_security_event(
        event_type="label_policy_violation_workflow",
        severity="high",
        user_identity=runner.provisioned_by,
        runner_id=str(runner.id),
        runner_name=runner_name,
        github_runner_id=runner_id,
        violation_data={
            "invalid_labels": list(violation.invalid_labels),
            "message": str(violation),
            "run_id": run_id,
            "repository": repo_full_name,
            "workflow_job_id": workflow_job.get("id"),
            "enforcement_mode": settings.label_policy_enforcement,
        },
        action_taken=action_taken,
    )

    return {
        "status": "violation_detected",
        "enforcement_mode": settings.label_policy_enforcement,
        "action_taken": action_taken,
    }
