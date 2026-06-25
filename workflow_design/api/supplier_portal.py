"""
Whitelisted API endpoints for the Supplier Portal.

Called from portal page JavaScript via frappe.call().
All methods validate that the caller is the linked supplier before
reading or writing any data.
"""

import frappe
from frappe import _
from frappe.utils import nowdate, add_days

from workflow_design.portal.supplier_utils import (
    require_supplier_login,
    get_current_supplier,
    assert_supplier_has_rfq_access,
    assert_supplier_has_sq_access,
)


@frappe.whitelist(allow_guest=False)
def submit_supplier_quotation(
    rfq_name: str,
    supplier: str,
    items,
    delivery_days: int,
    payment_days: int,
    remarks: str = "",
) -> dict:
    """
    Create or update a Supplier Quotation from portal input.

    Args:
        rfq_name:      Name of the source Request for Quotation.
        supplier:      Supplier name (validated against session user).
        items:         List of dicts with keys: item_code, request_for_quotation_item, qty, rate.
        delivery_days: Number of days until delivery.
        payment_days:  Credit / payment days.
        remarks:       Optional free-text notes or conditions.

    Returns:
        dict with "name" and "status" of the created/updated Supplier Quotation.
    """
    require_supplier_login()

    # Validate that the session user is actually this supplier
    session_supplier = get_current_supplier()
    if session_supplier != supplier:
        frappe.throw(_("Supplier mismatch."), frappe.PermissionError)

    assert_supplier_has_rfq_access(supplier, rfq_name)

    # Parse items if they come in as a JSON string (frappe.call serialises lists)
    if isinstance(items, str):
        import json
        items = json.loads(items)

    _validate_items(items)

    # Check for an existing non-cancelled SQ for this RFQ + Supplier
    existing_sq_name = _find_existing_sq(supplier, rfq_name)

    if existing_sq_name:
        sq_doc = _update_supplier_quotation(
            existing_sq_name, items, delivery_days, payment_days, remarks
        )
    else:
        sq_doc = _create_supplier_quotation(
            rfq_name, supplier, items, delivery_days, payment_days, remarks
        )

    return {"name": sq_doc.name, "status": sq_doc.status}


@frappe.whitelist(allow_guest=False)
def get_rfq_list() -> list[dict]:
    """
    Return all open RFQs for the currently logged-in supplier.
    Convenience endpoint used when refreshing the list via AJAX.
    """
    require_supplier_login()
    supplier = get_current_supplier()

    from workflow_design.www.supplier_rfq.index import _get_supplier_rfqs  # noqa: PLC0415
    return _get_supplier_rfqs(supplier)


@frappe.whitelist(allow_guest=False)
def get_rfq_detail(rfq_name: str) -> dict:
    """
    Return RFQ document data for a single RFQ, validated for the current supplier.
    """
    require_supplier_login()
    supplier = get_current_supplier()
    assert_supplier_has_rfq_access(supplier, rfq_name)

    rfq = frappe.get_doc("Request for Quotation", rfq_name)
    existing_sq_name = _find_existing_sq(supplier, rfq_name)
    existing_sq = frappe.get_doc("Supplier Quotation", existing_sq_name) if existing_sq_name else None

    return {
        "rfq": rfq.as_dict(),
        "existing_sq": existing_sq.as_dict() if existing_sq else None,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_items(items: list):
    if not items:
        frappe.throw(_("At least one item with a rate is required."))
    if not any(float(item.get("rate") or 0) > 0 for item in items):
        frappe.throw(_("Please enter a rate for at least one item."))


def _find_existing_sq(supplier: str, rfq_name: str) -> str | None:
    """Return the name of an existing draft/open Supplier Quotation for this RFQ."""
    result = frappe.db.sql(
        """
        SELECT sq.name
        FROM `tabSupplier Quotation` sq
        INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
        WHERE sq.supplier = %s
          AND sqi.request_for_quotation = %s
          AND sq.docstatus = 0
        ORDER BY sq.creation DESC
        LIMIT 1
        """,
        (supplier, rfq_name),
        as_dict=True,
    )
    return result[0]["name"] if result else None


def _create_supplier_quotation(
    rfq_name: str,
    supplier: str,
    items: list,
    delivery_days: int,
    payment_days: int,
    remarks: str,
) -> object:
    """Build and save a new Supplier Quotation document."""
    rfq = frappe.get_doc("Request for Quotation", rfq_name)

    supplier_doc = frappe.get_doc("Supplier", supplier)
    currency = supplier_doc.default_currency or frappe.get_cached_value(
        "Company", rfq.company, "default_currency"
    )

    sq = frappe.new_doc("Supplier Quotation")
    sq.supplier          = supplier
    sq.company           = rfq.company
    sq.currency          = currency
    sq.transaction_date  = nowdate()
    sq.schedule_date     = add_days(nowdate(), int(delivery_days))
    sq.payment_terms_template = _resolve_payment_template(supplier_doc, int(payment_days))
    sq.terms             = remarks
    sq.buying_price_list = supplier_doc.default_price_list or ""
    # Custom evaluation fields — populated here so evaluation engine can score them
    sq.wd_delivery_days  = int(delivery_days)
    sq.wd_payment_days   = int(payment_days)

    # Build item rows from the RFQ items
    rfq_item_map = {item.name: item for item in rfq.items}
    for row in items:
        rate = float(row.get("rate") or 0)
        rfq_item_name = row.get("request_for_quotation_item")
        rfq_item = rfq_item_map.get(rfq_item_name)
        if not rfq_item:
            continue

        sq.append("items", {
            "item_code":                rfq_item.item_code,
            "item_name":                rfq_item.item_name,
            "description":              rfq_item.description,
            "qty":                      rfq_item.qty,
            "uom":                      rfq_item.uom,
            "rate":                     rate,
            "request_for_quotation":    rfq_name,
            "request_for_quotation_item": rfq_item_name,
            "warehouse":                rfq_item.warehouse,
            "schedule_date":            add_days(nowdate(), int(delivery_days)),
        })

    sq.insert(ignore_permissions=True)
    frappe.db.commit()
    return sq


def _update_supplier_quotation(
    sq_name: str,
    items: list,
    delivery_days: int,
    payment_days: int,
    remarks: str,
) -> object:
    """Update rates and terms on an existing draft Supplier Quotation."""
    sq = frappe.get_doc("Supplier Quotation", sq_name)

    if sq.docstatus != 0:
        frappe.throw(
            _("Supplier Quotation {0} is already submitted and cannot be edited.").format(sq_name)
        )

    # Build a rate lookup keyed by rfq item name
    rate_map = {
        row.get("request_for_quotation_item"): float(row.get("rate") or 0)
        for row in items
    }

    for item in sq.items:
        if item.request_for_quotation_item in rate_map:
            item.rate = rate_map[item.request_for_quotation_item]
            item.schedule_date = add_days(nowdate(), int(delivery_days))

    sq.schedule_date     = add_days(nowdate(), int(delivery_days))
    sq.terms             = remarks
    sq.wd_delivery_days  = int(delivery_days)
    sq.wd_payment_days   = int(payment_days)
    sq.save(ignore_permissions=True)
    frappe.db.commit()
    return sq


def _resolve_payment_template(supplier_doc, payment_days: int) -> str | None:
    """
    Return a Payment Terms Template name if one matches the given days,
    otherwise return None (the Supplier Quotation will have no payment terms).
    ERPNext supports custom Payment Terms Templates; this does a best-effort match.
    """
    if supplier_doc.payment_terms:
        return supplier_doc.payment_terms

    # Try to find a single-instalment template matching payment_days
    match = frappe.db.get_value(
        "Payment Terms Template",
        {"name": ["like", f"%{payment_days}%"]},
        "name",
    )
    return match or None
