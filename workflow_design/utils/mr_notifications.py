"""
Material Request workflow notification dispatcher.

Each public function maps to one workflow transition event and delegates
to the shared email_utils.send_workflow_email() helper.

State → notification mapping
─────────────────────────────────────────────────────────────────────────────
New state                                   │ Recipient role
─────────────────────────────────────────────────────────────────────────────
WD Pending Purchase Manager Approval        │ WD Purchase Manager
WD Pending Supply Chain Manager Approval    │ WD Supply Chain Manager
WD Review by Purchase User                  │ WD Purchase User
WD Review by Purchase Manager               │ WD Purchase Manager
WD Approved                                 │ WD Purchase User  (doc owner)
WD Rejected                                 │ WD Purchase User  (doc owner)
─────────────────────────────────────────────────────────────────────────────
"""

import frappe
from frappe import _

from workflow_design.utils.email_utils import send_workflow_email, get_role_emails


# Role constants — single source of truth
ROLE_PURCHASE_USER = "WD Purchase User"
ROLE_PURCHASE_MANAGER = "WD Purchase Manager"
ROLE_SUPPLY_CHAIN_MANAGER = "WD Supply Chain Manager"


# ---------------------------------------------------------------------------
# One function per notification event (called from events/material_request.py)
# ---------------------------------------------------------------------------

def notify_purchase_manager_pending(doc):
    """Purchase User submitted → email Purchase Manager."""
    send_workflow_email(
        doc=doc,
        recipient_role=ROLE_PURCHASE_MANAGER,
        template_name="mr_submitted",
        subject=_("[Action Required] Material Request {0} awaits your approval").format(doc.name),
    )


def notify_scm_pending(doc):
    """Purchase Manager approved → email Supply Chain Manager."""
    send_workflow_email(
        doc=doc,
        recipient_role=ROLE_SUPPLY_CHAIN_MANAGER,
        template_name="mr_pm_approved",
        subject=_("[Action Required] Material Request {0} awaits final approval").format(doc.name),
    )


def notify_purchase_user_rejected(doc):
    """Purchase Manager or Supply Chain Manager rejected → email Purchase User (owner)."""
    _notify_owner(
        doc=doc,
        template_name="mr_rejected",
        subject=_("[Material Request] {0} has been rejected").format(doc.name),
        extra_context={"rejection_reason": _get_rejection_reason(doc)},
    )


def notify_purchase_user_review(doc):
    """Purchase Manager sent back for review → email Purchase User."""
    _notify_owner(
        doc=doc,
        template_name="mr_review_requested",
        subject=_("[Review Required] Material Request {0} needs your attention").format(doc.name),
        extra_context={"recipient_role_label": "Purchase User"},
    )


def notify_purchase_manager_review(doc):
    """Supply Chain Manager sent back for review → email Purchase Manager."""
    send_workflow_email(
        doc=doc,
        recipient_role=ROLE_PURCHASE_MANAGER,
        template_name="mr_review_requested",
        subject=_("[Review Required] Material Request {0} needs your attention").format(doc.name),
        extra_context={"recipient_role_label": "Purchase Manager"},
    )


def notify_purchase_user_approved(doc):
    """Supply Chain Manager fully approved → email Purchase User (owner)."""
    _notify_owner(
        doc=doc,
        template_name="mr_approved",
        subject=_("[Approved] Material Request {0} has been fully approved").format(doc.name),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _notify_owner(doc, template_name: str, subject: str, extra_context: dict | None = None):
    """
    Send an email directly to the document owner rather than everyone in a role.
    Falls back to role-based lookup when the owner has no email.
    """
    owner_email = frappe.db.get_value("User", doc.owner, "email") if doc.owner else None

    if owner_email:
        from workflow_design.utils.email_utils import _build_context, _render_template  # noqa: PLC0415
        context = _build_context(doc, extra_context)
        message = _render_template(template_name, context)
        frappe.sendmail(
            recipients=[owner_email],
            subject=subject,
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
            delayed=False,
        )
    else:
        # owner has no email — fall back to all Purchase Users
        send_workflow_email(
            doc=doc,
            recipient_role=ROLE_PURCHASE_USER,
            template_name=template_name,
            subject=subject,
            extra_context=extra_context,
        )


def _get_rejection_reason(doc) -> str:
    """
    Pull a rejection reason from a custom field if it exists,
    otherwise return an empty string gracefully.
    """
    return getattr(doc, "wd_rejection_reason", "") or ""
