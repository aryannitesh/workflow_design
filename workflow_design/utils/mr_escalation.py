"""
Escalation logic for Material Request — Purchase Manager SLA breach.

Responsibilities
────────────────
1. Query all Material Requests stuck in "WD Pending Purchase Manager Approval"
   for longer than SLA_HOURS without an escalation already sent.
2. Send an escalation email to every Supply Chain Manager.
3. Stamp wd_escalation_sent=1 and wd_escalation_datetime on the document so
   the scheduler never sends a duplicate.

Called by:  workflow_design.tasks.hourly.escalate_overdue_material_requests
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, time_diff_in_hours, format_datetime

from workflow_design.utils.email_utils import (
    send_workflow_email,
    get_role_emails,
    _build_context,
    _render_template,
)

# ── Configuration ────────────────────────────────────────────────────────────

SLA_HOURS: int = 24          # breach threshold
PENDING_STATE: str = "WD Pending Purchase Manager Approval"
ROLE_SCM: str = "WD Supply Chain Manager"


# ── Public entry point (called from tasks/hourly.py) ─────────────────────────

def escalate_overdue_material_requests() -> int:
    """
    Find all breached Material Requests and send one escalation email per doc.

    Returns the number of escalation emails sent (useful for logging).
    """
    overdue = _fetch_overdue_records()
    sent_count = 0

    for record in overdue:
        try:
            doc = frappe.get_doc("Material Request", record["name"])
            _send_escalation(doc)
            _mark_escalated(doc)
            sent_count += 1
        except Exception:
            frappe.log_error(
                title=f"WD Escalation failed for {record['name']}",
                message=frappe.get_traceback(),
            )

    return sent_count


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_overdue_records() -> list[dict]:
    """
    Return Material Requests that:
      • are in the pending PM approval state
      • have a wd_pending_since older than SLA_HOURS
      • have NOT already had an escalation sent (wd_escalation_sent = 0)
    """
    threshold = frappe.utils.add_to_date(now_datetime(), hours=-SLA_HOURS)

    return frappe.get_all(
        "Material Request",
        filters={
            "workflow_state": PENDING_STATE,
            "wd_escalation_sent": 0,
            "wd_pending_since": ["<=", threshold],
            "docstatus": ["!=", 2],           # exclude cancelled
        },
        fields=["name", "owner", "wd_pending_since"],
        order_by="wd_pending_since asc",
    )


def _send_escalation(doc) -> None:
    """Build context and send the escalation email to all SCM users."""
    recipients = get_role_emails(ROLE_SCM)
    if not recipients:
        frappe.logger("workflow_design").warning(
            f"No users for role '{ROLE_SCM}' — skipping escalation for {doc.name}"
        )
        return

    pending_since_dt = get_datetime(doc.wd_pending_since) if doc.wd_pending_since else None
    hours_overdue = (
        round(time_diff_in_hours(now_datetime(), pending_since_dt), 1)
        if pending_since_dt else "?"
    )
    submitted_by = (
        frappe.db.get_value("User", doc.owner, "full_name") or doc.owner
        if doc.owner else "Unknown"
    )

    extra_context = {
        "sla_hours": SLA_HOURS,
        "pending_since": format_datetime(pending_since_dt) if pending_since_dt else "Unknown",
        "hours_overdue": hours_overdue,
        "submitted_by": submitted_by,
        # actor in the escalation context is the system (scheduler), not a user
        "actor_full_name": "Automated Escalation",
    }

    context = _build_context(doc, extra_context)
    message = _render_template("mr_escalation", context)

    frappe.sendmail(
        recipients=recipients,
        subject=_("[Escalation] Material Request {0} overdue by {1} hours").format(
            doc.name, hours_overdue
        ),
        message=message,
        reference_doctype=doc.doctype,
        reference_name=doc.name,
        delayed=False,
    )

    frappe.logger("workflow_design").info(
        f"Escalation sent for {doc.name} ({hours_overdue}h overdue) → {recipients}"
    )


def _mark_escalated(doc) -> None:
    """
    Stamp the escalation fields directly via db_set to avoid triggering
    doc events or workflow transitions.
    """
    frappe.db.set_value(
        "Material Request",
        doc.name,
        {
            "wd_escalation_sent": 1,
            "wd_escalation_datetime": now_datetime(),
        },
        update_modified=False,   # preserve the document's modified timestamp
    )
