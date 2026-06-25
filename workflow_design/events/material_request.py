"""
Document event handlers for Material Request.

Why on_update AND on_workflow_action?
──────────────────────────────────────
Frappe fires workflow transitions as saves (doc_status stays 0 for intermediate
states).  on_workflow_action fires for every action button click, giving us the
transition that *just* happened.  on_submit fires only when doc_status reaches 1
(WD Approved).  on_cancel fires when doc_status reaches 2 (WD Rejected via cancel).

We use on_workflow_action as the primary hook because it carries the `action`
argument, letting us route notifications precisely without comparing old vs new
state manually.
"""

import frappe
from frappe import _

from workflow_design.utils.mr_notifications import (
    notify_purchase_manager_pending,
    notify_scm_pending,
    notify_purchase_user_rejected,
    notify_purchase_user_review,
    notify_purchase_manager_review,
    notify_purchase_user_approved,
)


# ---------------------------------------------------------------------------
# Workflow action names (must match workflow_action_master.json exactly)
# ---------------------------------------------------------------------------
ACTION_SUBMIT       = "WD Submit for Approval"
ACTION_RESUBMIT     = "WD Resubmit"
ACTION_APPROVE      = "WD Approve"
ACTION_REJECT       = "WD Reject"
ACTION_REVIEW       = "WD Request Review"

# Workflow state names (must match workflow.json exactly)
STATE_PENDING_PM    = "WD Pending Purchase Manager Approval"
STATE_PENDING_SCM   = "WD Pending Supply Chain Manager Approval"
STATE_REVIEW_PU     = "WD Review by Purchase User"
STATE_REVIEW_PM     = "WD Review by Purchase Manager"
STATE_APPROVED      = "WD Approved"
STATE_REJECTED      = "WD Rejected"


# ---------------------------------------------------------------------------
# Frappe doc event hooks (registered in hooks.py)
# ---------------------------------------------------------------------------

def on_workflow_action(doc, method=None, action=None):
    """
    Primary notification router.

    Frappe passes the action name via the `action` kwarg when
    `on_workflow_action` is defined in doc_events.
    """
    if not action:
        return

    new_state = doc.workflow_state

    # Purchase User submits (initial or resubmit)
    if action in (ACTION_SUBMIT, ACTION_RESUBMIT) and new_state == STATE_PENDING_PM:
        _stamp_pending_since(doc)
        notify_purchase_manager_pending(doc)

    # Purchase Manager approves → goes to SCM
    elif action == ACTION_APPROVE and new_state == STATE_PENDING_SCM:
        _reset_escalation_flags(doc)
        notify_scm_pending(doc)

    # Purchase Manager rejects
    elif action == ACTION_REJECT and new_state == STATE_REJECTED:
        _reset_escalation_flags(doc)
        notify_purchase_user_rejected(doc)

    # Purchase Manager sends back for review
    elif action == ACTION_REVIEW and new_state == STATE_REVIEW_PU:
        _reset_escalation_flags(doc)
        notify_purchase_user_review(doc)

    # Supply Chain Manager approves → fully approved
    elif action == ACTION_APPROVE and new_state == STATE_APPROVED:
        notify_purchase_user_approved(doc)

    # Supply Chain Manager rejects
    elif action == ACTION_REJECT and new_state == STATE_REJECTED:
        notify_purchase_user_rejected(doc)

    # Supply Chain Manager sends back to Purchase Manager for review
    elif action == ACTION_REVIEW and new_state == STATE_REVIEW_PM:
        notify_purchase_manager_review(doc)


def on_submit(doc, method=None):
    """
    Fires when doc_status flips to 1 (WD Approved sets doc_status=1).
    on_workflow_action already handled the email; use this for any
    post-approval side effects (e.g. real-time desk alerts).
    """
    if doc.workflow_state == STATE_APPROVED:
        _desk_alert_owner(
            doc,
            _("Your Material Request {0} has been fully approved.").format(doc.name),
        )


def on_cancel(doc, method=None):
    """Fires when doc_status flips to 2."""
    if doc.workflow_state == STATE_REJECTED:
        _desk_alert_owner(
            doc,
            _("Material Request {0} was rejected.").format(doc.name),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _desk_alert_owner(doc, message: str):
    """Push a real-time desk notification to the document owner."""
    if not doc.owner:
        return
    frappe.publish_realtime(
        event="msgprint",
        message=message,
        user=doc.owner,
    )


def _stamp_pending_since(doc) -> None:
    """
    Record the exact datetime the document entered the pending-PM-approval state.
    Also clear any stale escalation flags from a previous submission cycle.
    Uses db_set so it does not re-fire doc events.
    """
    from frappe.utils import now_datetime  # noqa: PLC0415
    frappe.db.set_value(
        "Material Request",
        doc.name,
        {
            "wd_pending_since": now_datetime(),
            "wd_escalation_sent": 0,
            "wd_escalation_datetime": None,
        },
        update_modified=False,
    )


def _reset_escalation_flags(doc) -> None:
    """
    Clear escalation flags when the document leaves the pending-PM-approval
    state so that a future resubmission starts a clean SLA clock.
    Uses db_set so it does not re-fire doc events.
    """
    frappe.db.set_value(
        "Material Request",
        doc.name,
        {
            "wd_pending_since": None,
            "wd_escalation_sent": 0,
            "wd_escalation_datetime": None,
        },
        update_modified=False,
    )
