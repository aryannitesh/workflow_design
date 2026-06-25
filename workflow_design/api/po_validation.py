"""
Whitelisted API endpoints for Purchase Order validation and traceability.
"""

import frappe
from frappe import _

from workflow_design.utils.po_automation import get_procurement_chain


@frappe.whitelist()
def check_sq_approval(sq_names: list | str) -> list[dict]:
    """
    Return the wd_evaluation_status for each Supplier Quotation.
    Called from the PO desk form JS to show a pre-submit warning.
    """
    if isinstance(sq_names, str):
        import json
        sq_names = json.loads(sq_names)

    if not sq_names:
        return []

    rows = frappe.get_all(
        "Supplier Quotation",
        filters={"name": ["in", sq_names]},
        fields=["name", "supplier", "wd_evaluation_status", "grand_total"],
    )
    return rows


@frappe.whitelist()
def get_po_chain(po_name: str) -> dict:
    """
    Return the full MR → RFQ → SQ → PO traceability chain for a submitted PO.
    """
    frappe.has_permission("Purchase Order", ptype="read", doc=po_name, throw=True)
    po_doc = frappe.get_doc("Purchase Order", po_name)
    return get_procurement_chain(po_doc)
