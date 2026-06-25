"""
Row-level permission helpers for workflow_design.

Registered in hooks.py under permission_query_conditions and has_permission.

Logic:
 - Desk users (non-portal, non-supplier): fall through to ERPNext defaults.
 - Portal / Supplier role users: restrict to documents linked to their Supplier record.
"""

import frappe
from frappe import _


def get_permission_query_conditions(user=None):
    """
    Called for list views to limit which rows are visible.
    Returns an SQL WHERE clause fragment, or "" for no restriction.
    """
    if not user:
        user = frappe.session.user

    if _is_supplier_portal_user(user):
        supplier = _get_supplier_for_user(user)
        if not supplier:
            return "1=0"   # no supplier linked → show nothing

        doctype = frappe.form_dict.get("doctype") or ""
        conditions_map = {
            "Request for Quotation": _supplier_rfq_conditions,
            "Supplier Quotation":    _supplier_sq_conditions,
            "Purchase Order":        _supplier_po_conditions,
        }
        fn = conditions_map.get(doctype)
        if fn:
            return fn(supplier)

    return ""   # desk users: no additional SQL restriction


def has_permission(doc, ptype="read", user=None):
    """
    Called for single-document access checks.
    Returns True to allow, False to deny, None to fall through to defaults.
    """
    if not user:
        user = frappe.session.user

    if not _is_supplier_portal_user(user):
        return None   # let ERPNext handle desk users

    supplier = _get_supplier_for_user(user)
    if not supplier:
        return False

    dt = doc.doctype

    if dt == "Request for Quotation":
        return bool(frappe.db.exists(
            "Request for Quotation Supplier",
            {"parent": doc.name, "supplier": supplier},
        ))

    if dt == "Supplier Quotation":
        return doc.supplier == supplier

    if dt == "Purchase Order":
        return doc.supplier == supplier

    return None   # unknown doctype → fall through


# ---------------------------------------------------------------------------
# SQL condition builders (used in get_permission_query_conditions)
# ---------------------------------------------------------------------------

def _supplier_rfq_conditions(supplier: str) -> str:
    escaped = frappe.db.escape(supplier)
    return (
        f"`tabRequest for Quotation`.`name` IN ("
        f"  SELECT parent FROM `tabRequest for Quotation Supplier`"
        f"  WHERE supplier = {escaped}"
        f")"
    )


def _supplier_sq_conditions(supplier: str) -> str:
    escaped = frappe.db.escape(supplier)
    return f"`tabSupplier Quotation`.`supplier` = {escaped}"


def _supplier_po_conditions(supplier: str) -> str:
    escaped = frappe.db.escape(supplier)
    return f"`tabPurchase Order`.`supplier` = {escaped}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_supplier_portal_user(user: str) -> bool:
    """Return True if the user has the 'Supplier' portal role."""
    return bool(frappe.db.exists("Has Role", {"parent": user, "role": "Supplier"}))


def _get_supplier_for_user(user: str) -> str | None:
    """
    Resolve the Supplier linked to a portal user via Contact → Dynamic Link.
    Returns None when no link exists.
    """
    try:
        from erpnext.controllers.website_list_for_contact import get_customers_suppliers  # noqa: PLC0415
        _customers, suppliers = get_customers_suppliers(
            "Request for Quotation Supplier", user
        )
        return suppliers[0] if suppliers else None
    except Exception:
        return None
