"""
Hourly scheduled tasks for workflow_design.
Registered in hooks.py → scheduler_events["hourly"].
"""

import frappe

from workflow_design.utils.mr_escalation import escalate_overdue_material_requests


def check_rfq_deadlines():
    """Placeholder — RFQ deadline logic will be added in a later iteration."""
    pass


def escalate_overdue_material_requests_task():
    """
    Entry point called by the Frappe scheduler every hour.

    Finds Material Requests that have been stuck in
    "WD Pending Purchase Manager Approval" for more than 24 hours
    and sends a single escalation email to all Supply Chain Managers.
    """
    count = escalate_overdue_material_requests()
    if count:
        frappe.logger("workflow_design").info(
            f"[Hourly] Sent {count} escalation email(s) for overdue Material Requests."
        )
