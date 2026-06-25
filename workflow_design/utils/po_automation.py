"""
Purchase Order Automation Utilities
═════════════════════════════════════
Enforces the rule that a PO can only be created from an Approved SQ,
then on submission walks the full MR → RFQ → SQ chain and rejects
every competing quotation.

Public API
──────────
  validate_po_source(po_doc)          → called from before_submit
  process_po_submission(po_doc)       → called from on_submit
  get_procurement_chain(po_doc)       → returns the full traceability chain
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime


# ── Public API ────────────────────────────────────────────────────────────────

def validate_po_source(po_doc) -> None:
    """
    Before-submit guard: every item row that carries a supplier_quotation
    must reference an Approved SQ (wd_evaluation_status = 'Approved').

    Raises frappe.ValidationError on any violation.
    """
    sq_names = _get_source_sq_names(po_doc)

    if not sq_names:
        frappe.throw(
            _(
                "Purchase Order {0} cannot be submitted: no Supplier Quotation reference "
                "found on any item. Please create this PO from an Approved Supplier Quotation."
            ).format(po_doc.name),
            frappe.ValidationError,
        )

    for sq_name in sq_names:
        status = frappe.db.get_value(
            "Supplier Quotation", sq_name, "wd_evaluation_status"
        )
        if status != "Approved":
            frappe.throw(
                _(
                    "Supplier Quotation {0} has evaluation status '{1}'. "
                    "Only Approved quotations can be used to create a Purchase Order."
                ).format(sq_name, status or "Pending"),
                frappe.ValidationError,
            )


def process_po_submission(po_doc) -> None:
    """
    On-submit handler:
      1. Resolve the full MR → RFQ → SQ traceability chain.
      2. Stamp traceability fields on the PO header.
      3. Reject all other SQs competing for the same MR/RFQ.
      4. Notify the procurement team.
    """
    chain = get_procurement_chain(po_doc)
    _stamp_traceability(po_doc, chain)
    rejected_count = _reject_competing_quotations(po_doc, chain)
    _update_rejected_count(po_doc.name, rejected_count)
    _notify_po_submitted(po_doc, chain, rejected_count)

    frappe.logger("workflow_design").info(
        f"[PO Automation] {po_doc.name}: traceability stamped, "
        f"{rejected_count} competing SQ(s) rejected."
    )


def get_procurement_chain(po_doc) -> dict:
    """
    Walk the item rows and resolve the full chain for this PO.

    Returns a dict:
      {
        "source_sq_names":  [str, ...],   # SQs referenced by PO items
        "rfq_names":        [str, ...],   # RFQs linked via SQ items
        "mr_names":         [str, ...],   # MRs linked via PO/SQ items
        "primary_sq":       str | None,   # first/only SQ (most POs have one)
        "primary_rfq":      str | None,
        "primary_mr":       str | None,
      }
    """
    sq_names = _get_source_sq_names(po_doc)

    rfq_names = _get_rfqs_for_sqs(sq_names)
    mr_names  = _get_mrs_for_po(po_doc)

    return {
        "source_sq_names": sq_names,
        "rfq_names":       rfq_names,
        "mr_names":        mr_names,
        "primary_sq":      sq_names[0]  if sq_names  else None,
        "primary_rfq":     rfq_names[0] if rfq_names else None,
        "primary_mr":      mr_names[0]  if mr_names  else None,
    }


# ── Traceability stamping ─────────────────────────────────────────────────────

def _stamp_traceability(po_doc, chain: dict) -> None:
    """Write header traceability links directly via db_set."""
    frappe.db.set_value(
        "Purchase Order",
        po_doc.name,
        {
            "wd_source_sq":  chain["primary_sq"],
            "wd_source_rfq": chain["primary_rfq"],
            "wd_source_mr":  chain["primary_mr"],
        },
        update_modified=False,
    )


def _update_rejected_count(po_name: str, count: int) -> None:
    frappe.db.set_value(
        "Purchase Order",
        po_name,
        "wd_rejected_sq_count",
        count,
        update_modified=False,
    )


# ── Competing quotation rejection ─────────────────────────────────────────────

def _reject_competing_quotations(po_doc, chain: dict) -> int:
    """
    Mark every SQ linked to the same RFQs/MRs as Rejected,
    excluding the SQs already used by this PO.

    Uses db_set (no doc events fired) to avoid recursive hooks.
    Returns the number of SQs rejected.
    """
    approved_sq_names = set(chain["source_sq_names"])
    rfq_names         = chain["rfq_names"]
    mr_names          = chain["mr_names"]

    competing = _find_competing_sqs(rfq_names, mr_names, approved_sq_names)
    if not competing:
        return 0

    rejected_at = now_datetime()
    for sq_name in competing:
        frappe.db.set_value(
            "Supplier Quotation",
            sq_name,
            {
                "wd_evaluation_status": "Rejected",
                "wd_evaluated_on":      rejected_at,
            },
            update_modified=False,
        )

    frappe.db.commit()
    return len(competing)


def _find_competing_sqs(
    rfq_names: list[str],
    mr_names: list[str],
    exclude: set[str],
) -> list[str]:
    """
    Return submitted SQs (docstatus=1) that share any of the given
    RFQs or MRs with the winning PO, minus the winner's own SQs.
    """
    if not rfq_names and not mr_names:
        return []

    competing: set[str] = set()

    # SQs via RFQ linkage (most reliable path)
    if rfq_names:
        rows = frappe.db.sql(
            """
            SELECT DISTINCT sq.name
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sq.docstatus = 1
              AND sq.wd_evaluation_status != 'Rejected'
              AND sqi.request_for_quotation IN ({rfq_ph})
            """.format(rfq_ph=", ".join(["%s"] * len(rfq_names))),
            rfq_names,
            as_dict=True,
        )
        competing.update(r["name"] for r in rows)

    # SQs via Material Request linkage (fallback / additional coverage)
    if mr_names:
        rows = frappe.db.sql(
            """
            SELECT DISTINCT sq.name
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sq.docstatus = 1
              AND sq.wd_evaluation_status != 'Rejected'
              AND sqi.material_request IN ({mr_ph})
            """.format(mr_ph=", ".join(["%s"] * len(mr_names))),
            mr_names,
            as_dict=True,
        )
        competing.update(r["name"] for r in rows)

    return list(competing - exclude)


# ── Chain resolution helpers ──────────────────────────────────────────────────

def _get_source_sq_names(po_doc) -> list[str]:
    """Return deduplicated list of SQ names from PO item rows."""
    return list({
        item.supplier_quotation
        for item in po_doc.items
        if item.supplier_quotation
    })


def _get_rfqs_for_sqs(sq_names: list[str]) -> list[str]:
    """Resolve RFQs linked via Supplier Quotation Item rows."""
    if not sq_names:
        return []

    rows = frappe.db.sql(
        """
        SELECT DISTINCT sqi.request_for_quotation
        FROM `tabSupplier Quotation Item` sqi
        WHERE sqi.parent IN ({ph})
          AND sqi.request_for_quotation IS NOT NULL
          AND sqi.request_for_quotation != ''
        """.format(ph=", ".join(["%s"] * len(sq_names))),
        sq_names,
        as_dict=True,
    )
    return [r["request_for_quotation"] for r in rows]


def _get_mrs_for_po(po_doc) -> list[str]:
    """Return deduplicated list of Material Request names from PO item rows."""
    return list({
        item.material_request
        for item in po_doc.items
        if item.material_request
    })


# ── Notification ──────────────────────────────────────────────────────────────

def _notify_po_submitted(po_doc, chain: dict, rejected_count: int) -> None:
    """Send a procurement summary email when a PO is confirmed."""
    try:
        from workflow_design.utils.po_notifications import send_po_confirmed_email  # noqa: PLC0415
        send_po_confirmed_email(po_doc, chain, rejected_count)
    except Exception:
        frappe.log_error(
            title=f"WD: PO confirmation email failed for {po_doc.name}",
            message=frappe.get_traceback(),
        )
