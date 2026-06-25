"""
Document event handlers for Request for Quotation.
Hooked via hooks.py doc_events.
"""

import frappe
from frappe import _


def on_submit(doc, method=None):
    """
    When an RFQ is submitted (sent to suppliers), reset evaluation
    status on any previously linked SQs so stale results are cleared.
    """
    _reset_linked_sq_evaluation(doc)


def on_cancel(doc, method=None):
    """Cancel any open Supplier Quotations linked to this RFQ."""
    pass  # ERPNext handles linked SQ cancellation natively.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_linked_sq_evaluation(doc) -> None:
    """Clear wd_evaluation_* fields on all submitted SQs for this RFQ."""
    sq_names = frappe.db.sql_list(
        """
        SELECT DISTINCT sq.name
        FROM `tabSupplier Quotation` sq
        INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
        WHERE sqi.request_for_quotation = %s
          AND sq.docstatus = 1
        """,
        (doc.name,),
    )
    for sq_name in sq_names:
        frappe.db.set_value(
            "Supplier Quotation",
            sq_name,
            {
                "wd_evaluation_status": "Pending",
                "wd_evaluation_score":  0,
                "wd_evaluated_on":      None,
            },
            update_modified=False,
        )
