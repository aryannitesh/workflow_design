"""
Email notifications for Purchase Order confirmation.
"""

import frappe
from frappe import _
from frappe.utils import get_url_to_form

from workflow_design.utils.email_utils import get_role_emails, _render_template


NOTIFY_ROLES = ["WD Purchase Manager", "WD Supply Chain Manager", "WD Purchase User"]


def send_po_confirmed_email(po_doc, chain: dict, rejected_count: int) -> None:
    recipients = _collect_recipients()
    if not recipients:
        return

    context = {
        "po_name":         po_doc.name,
        "po_url":          get_url_to_form("Purchase Order", po_doc.name),
        "supplier":        po_doc.supplier,
        "grand_total":     po_doc.grand_total,
        "currency":        po_doc.currency,
        "source_sq":       chain["primary_sq"],
        "source_rfq":      chain["primary_rfq"],
        "source_mr":       chain["primary_mr"],
        "rejected_count":  rejected_count,
        "sq_url":          get_url_to_form("Supplier Quotation", chain["primary_sq"])
                           if chain["primary_sq"] else "",
        "rfq_url":         get_url_to_form("Request for Quotation", chain["primary_rfq"])
                           if chain["primary_rfq"] else "",
        "mr_url":          get_url_to_form("Material Request", chain["primary_mr"])
                           if chain["primary_mr"] else "",
        "site_name":       frappe.local.site,
    }

    message = _render_template("po_confirmed", context)
    frappe.sendmail(
        recipients=recipients,
        subject=_("[Purchase Order Confirmed] {0} — {1}").format(po_doc.name, po_doc.supplier),
        message=message,
        reference_doctype="Purchase Order",
        reference_name=po_doc.name,
        delayed=False,
    )


def _collect_recipients() -> list[str]:
    seen: set[str] = set()
    for role in NOTIFY_ROLES:
        seen.update(get_role_emails(role))
    return list(seen)
