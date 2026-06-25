"""
Document event handlers for Supplier Quotation.
Hooked via hooks.py doc_events.
"""

import frappe
from frappe import _

from workflow_design.utils.sq_evaluation import (
    validate_sq_before_submit,
    evaluate_sq_on_submit,
)


def before_submit(doc, method=None):
    """
    Validate mandatory evaluation fields before the SQ is submitted.
    Aborts submission when wd_delivery_days is missing or grand_total is zero.
    """
    validate_sq_before_submit(doc)

def on_submit(doc, method=None):
    """
    After submission:
      1. Trigger automatic evaluation when all invited suppliers have quoted.
      2. Send result notifications when evaluation completes.
    """
    evaluate_sq_on_submit(doc)


def on_cancel(doc, method=None):
    """
    When a SQ is cancelled, reset its evaluation status to Pending
    and re-run evaluation for the remaining submitted SQs if enough remain.
    """
    _reset_evaluation_status(doc)
    _re_evaluate_after_cancel(doc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_evaluation_status(doc) -> None:
    frappe.db.set_value(
        "Supplier Quotation",
        doc.name,
        {
            "wd_evaluation_status": "Pending",
            "wd_evaluation_score":  0,
            "wd_evaluated_on":      None,
        },
        update_modified=False,
    )


def _re_evaluate_after_cancel(doc) -> None:
    """Re-run evaluation for linked RFQs so the winner is recalculated."""
    from workflow_design.utils.sq_evaluation import evaluate_rfq  # noqa: PLC0415

    rfq_names = list({
        item.request_for_quotation
        for item in doc.items
        if item.request_for_quotation
    })

    for rfq_name in rfq_names:
        try:
            evaluate_rfq(rfq_name)
        except frappe.ValidationError:
            # Not enough remaining quotations — leave statuses as-is
            pass
