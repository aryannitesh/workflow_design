"""
Portal page controller: /supplier-rfq/<rfq_name>

Shows a single RFQ with its items and lets the supplier fill in:
  - Rate per item
  - Delivery Days
  - Payment Days
  - Remarks

Submitting the form calls the whitelisted API:
  workflow_design.api.supplier_portal.submit_supplier_quotation
"""

import frappe
from frappe import _
from frappe.utils import formatdate

from workflow_design.portal.supplier_utils import (
    get_current_supplier,
    require_supplier_login,
    assert_supplier_has_rfq_access,
)


def get_context(context):
    require_supplier_login()

    rfq_name = frappe.form_dict.get("name") or frappe.form_dict.get("rfq_name")
    if not rfq_name:
        frappe.throw(_("RFQ name is required"), frappe.DoesNotExistError)

    supplier = get_current_supplier()
    assert_supplier_has_rfq_access(supplier, rfq_name)

    rfq = frappe.get_doc("Request for Quotation", rfq_name)

    # Resolve currency from Supplier master; fall back to company default
    supplier_doc = frappe.get_doc("Supplier", supplier)
    currency = supplier_doc.default_currency or frappe.get_cached_value(
        "Company", rfq.company, "default_currency"
    )
    currency_symbol = frappe.db.get_value("Currency", currency, "symbol", cache=True) or currency

    # Load any existing draft Supplier Quotation for this RFQ+Supplier
    existing_sq = _get_existing_sq(supplier, rfq_name)

    context.no_cache = 1
    context.show_sidebar = True
    context.title = rfq_name
    context.rfq = rfq
    context.supplier = supplier
    context.currency = currency
    context.currency_symbol = currency_symbol
    context.existing_sq = existing_sq
    context.parents = [{"title": _("My RFQs"), "route": "supplier-rfq"}]

    # Pre-fill item rates from existing SQ if available
    if existing_sq:
        _enrich_items_with_sq_data(rfq.items, existing_sq)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_existing_sq(supplier: str, rfq_name: str) -> object | None:
    """Return the most recent non-cancelled Supplier Quotation for this RFQ."""
    result = frappe.db.sql(
        """
        SELECT sq.name
        FROM `tabSupplier Quotation` sq
        INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
        WHERE sq.supplier = %s
          AND sqi.request_for_quotation = %s
          AND sq.docstatus != 2
        ORDER BY sq.creation DESC
        LIMIT 1
        """,
        (supplier, rfq_name),
        as_dict=True,
    )
    if result:
        return frappe.get_doc("Supplier Quotation", result[0]["name"])
    return None


def _enrich_items_with_sq_data(rfq_items, sq_doc):
    """Copy previously submitted rates into the RFQ item rows for display."""
    sq_rate_map = {
        item.request_for_quotation_item: item.rate
        for item in sq_doc.items
        if item.request_for_quotation_item
    }
    for item in rfq_items:
        item.prefill_rate = sq_rate_map.get(item.name, 0)
