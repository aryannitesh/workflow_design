"""
Shared portal helper utilities for the Supplier Portal.

These are imported by www page controllers and the API layer.
They are NOT whitelisted — they run server-side only.
"""

import frappe
from frappe import _
from erpnext.controllers.website_list_for_contact import get_customers_suppliers


# ---------------------------------------------------------------------------
# Auth / access guards
# ---------------------------------------------------------------------------

def require_supplier_login():
    """
    Abort with a PermissionError if the current user is not logged in
    or does not hold the 'Supplier' role (portal role).
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to access the Supplier Portal."), frappe.PermissionError)

    if not frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": "Supplier"}):
        frappe.throw(_("You are not authorised to access the Supplier Portal."), frappe.PermissionError)


def get_current_supplier() -> str:
    """
    Resolve the Supplier linked to the currently logged-in portal user.
    ERPNext stores the link via Contact → Dynamic Link → Supplier.
    Raises PermissionError when no supplier is found so the portal
    never shows data to unlinked users.
    """
    _customers, suppliers = get_customers_suppliers(
        "Request for Quotation Supplier", frappe.session.user
    )
    if not suppliers:
        frappe.throw(
            _("No Supplier record is linked to your user account. "
              "Please contact the system administrator."),
            frappe.PermissionError,
        )
    return suppliers[0]


def assert_supplier_has_rfq_access(supplier: str, rfq_name: str):
    """
    Raise PermissionError if `supplier` is not listed in the
    Request for Quotation Supplier child table of `rfq_name`.
    """
    exists = frappe.db.exists(
        "Request for Quotation Supplier",
        {"parent": rfq_name, "supplier": supplier},
    )
    if not exists:
        frappe.throw(
            _("You do not have permission to access RFQ {0}.").format(rfq_name),
            frappe.PermissionError,
        )


def assert_supplier_has_sq_access(supplier: str, sq_name: str):
    """
    Raise PermissionError if `supplier` is not the owner of Supplier Quotation `sq_name`.
    """
    sq_supplier = frappe.db.get_value("Supplier Quotation", sq_name, "supplier")
    if sq_supplier != supplier:
        frappe.throw(
            _("You do not have permission to access Supplier Quotation {0}.").format(sq_name),
            frappe.PermissionError,
        )
