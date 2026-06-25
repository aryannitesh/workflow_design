"""
Document event handlers for Purchase Order.
Hooked via hooks.py doc_events.
"""

import frappe
from frappe import _

from workflow_design.utils.po_automation import (
    validate_po_source,
    process_po_submission,
    get_procurement_chain,
)


def before_submit(doc, method=None):
    """
    Enforce that every SQ referenced in this PO has been Approved
    by the evaluation engine before allowing submission.
    """
    validate_po_source(doc)


def before_insert(doc, method=None):
    """
    Block PO creation if any source Supplier Quotation is Rejected.
    This fires when 'Make Purchase Order' is triggered from the SQ form,
    catching it before the document is even saved as draft.
    """
    _block_po_from_rejected_sq(doc)


def on_submit(doc, method=None):
    """
    After the PO is submitted:
      - Stamp the full MR → RFQ → SQ → PO traceability chain.
      - Reject all competing Supplier Quotations.
      - Send a confirmation notification.
    """
    process_po_submission(doc)


def on_cancel(doc, method=None):
    """
    When a PO is cancelled, restore the source SQ's evaluation
    status to Approved and clear the traceability fields so a
    new PO can be raised from the same quotation.
    """
    _restore_source_sq(doc)
    _clear_traceability(doc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _restore_source_sq(doc) -> None:
    """Re-approve the winning SQ so it can be used to raise a new PO."""
    sq_names = list({
        item.supplier_quotation
        for item in doc.items
        if item.supplier_quotation
    })
    for sq_name in sq_names:
        current_status = frappe.db.get_value(
            "Supplier Quotation", sq_name, "wd_evaluation_status"
        )
        # Only restore if the SQ was the winner (it won't be "Rejected")
        if current_status == "Approved":
            continue  # already correct — nothing to do
        # If somehow it got set to Rejected during cancellation cycle, restore it
        frappe.db.set_value(
            "Supplier Quotation",
            sq_name,
            "wd_evaluation_status",
            "Approved",
            update_modified=False,
        )


def _clear_traceability(doc) -> None:
    """Remove the WD traceability header fields when the PO is cancelled."""
    frappe.db.set_value(
        "Purchase Order",
        doc.name,
        {
            "wd_source_sq":          None,
            "wd_source_rfq":         None,
            "wd_source_mr":          None,
            "wd_rejected_sq_count":  0,
        },
        update_modified=False,
    )


def _block_po_from_rejected_sq(doc) -> None:
    """
    Raise ValidationError if any item row references a Rejected SQ.
    Called from before_insert so the PO draft is never created.
    """
    rejected = []
    for item in doc.items:
        sq_name = item.get("supplier_quotation")
        if not sq_name:
            continue
        status = frappe.db.get_value("Supplier Quotation", sq_name, "wd_evaluation_status")
        if status == "Rejected":
            rejected.append(sq_name)

    if rejected:
        frappe.throw(
            _(
                "Cannot create Purchase Order from the following Rejected "
                "Supplier Quotation(s): {0}. "
                "Only the Approved (best-scored) quotation can be converted to a Purchase Order."
            ).format(", ".join(set(rejected))),
            frappe.ValidationError,
        )
