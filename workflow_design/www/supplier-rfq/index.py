"""
Portal page controller: /supplier-rfq

Lists all open Request for Quotations assigned to the logged-in supplier.
Only users with the "Supplier" role and a linked Supplier record can access this.
"""

import frappe
from frappe import _

from workflow_design.portal.supplier_utils import (
    get_current_supplier,
    require_supplier_login,
)


def get_context(context):
    require_supplier_login()

    supplier = get_current_supplier()

    context.no_cache = 1
    context.show_sidebar = True
    context.title = _("My RFQs")
    context.supplier = supplier
    context.rfqs = _get_supplier_rfqs(supplier)


def _get_supplier_rfqs(supplier: str) -> list[dict]:
    """
    Return all open/submitted RFQs that include this supplier in their
    Request for Quotation Supplier child table.
    """
    rfq_names = frappe.db.sql_list(
        """
        SELECT DISTINCT rfqs.parent
        FROM `tabRequest for Quotation Supplier` rfqs
        INNER JOIN `tabRequest for Quotation` rfq ON rfq.name = rfqs.parent
        WHERE rfqs.supplier = %s
          AND rfq.docstatus = 1
          AND rfq.status NOT IN ('Cancelled', 'Expired')
        ORDER BY rfq.transaction_date DESC
        """,
        (supplier,),
    )

    if not rfq_names:
        return []

    rfqs = frappe.get_all(
        "Request for Quotation",
        filters={"name": ["in", rfq_names]},
        fields=[
            "name", "transaction_date", "status",
            "schedule_date", "company", "message_for_supplier",
        ],
        order_by="transaction_date desc",
    )

    # Attach existing Supplier Quotation status for each RFQ
    for rfq in rfqs:
        sq = frappe.db.get_value(
            "Supplier Quotation",
            {"supplier": supplier, "docstatus": ["!=", 2]},
            ["name", "status"],
            as_dict=True,
            order_by="creation desc",
        )
        # Check if a SQ exists specifically quoting this RFQ
        sq_for_rfq = frappe.db.sql(
            """
            SELECT sq.name, sq.status
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sq.supplier = %s
              AND sqi.request_for_quotation = %s
              AND sq.docstatus != 2
            ORDER BY sq.creation DESC
            LIMIT 1
            """,
            (supplier, rfq["name"]),
            as_dict=True,
        )
        rfq["existing_quotation"] = sq_for_rfq[0] if sq_for_rfq else None
        rfq["quoted"] = bool(sq_for_rfq)

    return rfqs
