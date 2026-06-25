"""
Email notifications for Supplier Quotation evaluation results.

send_evaluation_result_email() is called from the API and from
evaluate_sq_on_submit() after a successful evaluation run.
"""

import frappe
from frappe import _
from frappe.utils import get_url_to_form

from workflow_design.utils.email_utils import get_role_emails, _render_template
from workflow_design.utils.sq_evaluation import QuotationCandidate


NOTIFY_ROLES = ["WD Purchase Manager", "WD Supply Chain Manager", "WD Purchase User"]


def send_evaluation_result_email(
    rfq_name: str,
    ranked: list[QuotationCandidate],
) -> None:
    """
    Send a ranked evaluation result email to all Purchase Managers
    and Supply Chain Managers.
    """
    recipients = _collect_recipients()
    if not recipients:
        frappe.logger("workflow_design").warning(
            "[SQ Evaluation] No recipients found for evaluation result email."
        )
        return

    results = [
        {
            "name":          c.name,
            "supplier":      c.supplier,
            "grand_total":   c.grand_total,
            "delivery_days": c.delivery_days,
            "payment_days":  c.payment_days,
            "total_score":   c.total_score,
            "is_winner":     c.is_winner,
            "url":           get_url_to_form("Supplier Quotation", c.name),
        }
        for c in ranked
    ]

    context = {
        "rfq_name":  rfq_name,
        "rfq_url":   get_url_to_form("Request for Quotation", rfq_name),
        "results":   results,
        "site_name": frappe.local.site,
    }

    message = _render_template("sq_evaluation_result", context)

    frappe.sendmail(
        recipients=recipients,
        subject=_("[Evaluation Complete] RFQ {0} — Best Quotation Selected").format(rfq_name),
        message=message,
        reference_doctype="Request for Quotation",
        reference_name=rfq_name,
        delayed=False,
    )


def _collect_recipients() -> list[str]:
    seen: set[str] = set()
    for role in NOTIFY_ROLES:
        seen.update(get_role_emails(role))
    return list(seen)
