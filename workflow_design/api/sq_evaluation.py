"""
Whitelisted API endpoints for manual Supplier Quotation evaluation.
Callable from the desk via frappe.call() or the custom JS button.
"""

import frappe
from frappe import _

from workflow_design.utils.sq_evaluation import evaluate_rfq, get_evaluation_result


@frappe.whitelist()
def run_evaluation(rfq_name: str) -> list[dict]:
    """
    Manually trigger evaluation for all submitted SQs linked to `rfq_name`.

    Returns the ranked result list as a list of dicts suitable for
    rendering in a desk dialog or report.

    Raises frappe.ValidationError when fewer than MIN_QUOTATIONS_REQUIRED
    SQs are available.
    """
    frappe.has_permission("Request for Quotation", ptype="write", doc=rfq_name, throw=True)

    ranked = evaluate_rfq(rfq_name)

    return [
        {
            "rank":          idx + 1,
            "name":          c.name,
            "supplier":      c.supplier,
            "grand_total":   c.grand_total,
            "delivery_days": c.delivery_days,
            "payment_days":  c.payment_days,
            "rate_score":    round(c.rate_score, 4),
            "delivery_score": round(c.delivery_score, 4),
            "payment_score": round(c.payment_score, 4),
            "total_score":   round(c.total_score, 4),
            "status":        "Approved" if c.is_winner else "Rejected",
        }
        for idx, c in enumerate(ranked)
    ]


@frappe.whitelist()
def get_result(rfq_name: str) -> list[dict]:
    """
    Return the last saved evaluation result for an RFQ without re-running it.
    Safe to call from the portal or desk at any time.
    """
    frappe.has_permission("Request for Quotation", ptype="read", doc=rfq_name, throw=True)
    return get_evaluation_result(rfq_name)
