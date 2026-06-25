"""
Supplier Quotation Evaluation Engine
═════════════════════════════════════
Evaluates all submitted Supplier Quotations linked to a given RFQ,
computes a composite score for each, marks the winner as "Approved"
and all others as "Rejected".

Scoring Model (weights are configurable via constants below)
────────────────────────────────────────────────────────────
Three normalised dimensions are combined into one score in [0, 1].
Higher score = better quotation.

  rate_score        →  lowest grand_total wins         (weight: WEIGHT_RATE)
  delivery_score    →  fewest delivery days wins        (weight: WEIGHT_DELIVERY)
  payment_score     →  most payment days wins           (weight: WEIGHT_PAYMENT)

Each dimension is min-max normalised across the candidate set so that
the best value always gets 1.0 and the worst always gets 0.0.
When all values are equal the normalised score is 1.0 for every candidate.

Public API
──────────
  evaluate_rfq(rfq_name)              → evaluate all SQs for an RFQ
  evaluate_sq_on_submit(sq_doc)       → trigger evaluation after a SQ is submitted
  get_evaluation_result(rfq_name)     → read-only: return ranked result list
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import frappe
from frappe import _
from frappe.utils import now_datetime, flt, cint


# ── Weights (must sum to 1.0) ─────────────────────────────────────────────────
WEIGHT_RATE     = 0.40
WEIGHT_DELIVERY = 0.30
WEIGHT_PAYMENT  = 0.30

assert abs(WEIGHT_RATE + WEIGHT_DELIVERY + WEIGHT_PAYMENT - 1.0) < 1e-9, \
    "Evaluation weights must sum to 1.0"

# Minimum number of submitted SQs required before evaluation runs
MIN_QUOTATIONS_REQUIRED = 2

# ── Data container ────────────────────────────────────────────────────────────

@dataclass
class QuotationCandidate:
    name: str
    supplier: str
    grand_total: float
    delivery_days: int
    payment_days: int
    # Populated by the scorer
    rate_score: float     = 0.0
    delivery_score: float = 0.0
    payment_score: float  = 0.0
    total_score: float    = 0.0
    is_winner: bool       = False


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_rfq(rfq_name: str) -> list[QuotationCandidate]:
    """
    Run a full evaluation cycle for all submitted Supplier Quotations
    linked to `rfq_name`.

    Steps:
      1. Fetch candidates
      2. Validate readiness (min count, non-zero rates)
      3. Score each candidate
      4. Identify winner
      5. Persist results to the database

    Returns the ranked candidate list (highest score first).
    Raises frappe.ValidationError when preconditions are not met.
    """
    candidates = _fetch_candidates(rfq_name)
    _validate_candidates(rfq_name, candidates)
    _score(candidates)
    _persist(candidates)

    ranked = sorted(candidates, key=lambda c: c.total_score, reverse=True)
    frappe.logger("workflow_design").info(
        f"[SQ Evaluation] RFQ {rfq_name}: evaluated {len(ranked)} quotations. "
        f"Winner: {ranked[0].name} (score={ranked[0].total_score:.4f})"
    )

    # Send result notification — import here to avoid circular imports
    try:
        from workflow_design.utils.sq_notifications import send_evaluation_result_email  # noqa: PLC0415
        send_evaluation_result_email(rfq_name, ranked)
    except Exception:
        frappe.log_error(
            title=f"WD: evaluation result email failed for {rfq_name}",
            message=frappe.get_traceback(),
        )

    return ranked


def evaluate_sq_on_submit(sq_doc) -> None:
    """
    Called from the Supplier Quotation on_submit event.
    Triggers evaluation only when all invited suppliers have submitted.
    Safe to call even when the RFQ is not yet fully quoted.
    """
    rfq_names = _get_linked_rfqs(sq_doc)
    for rfq_name in rfq_names:
        if _all_suppliers_quoted(rfq_name):
            try:
                evaluate_rfq(rfq_name)
            except frappe.ValidationError as exc:
                # Log but don't abort the SQ submission
                frappe.logger("workflow_design").warning(
                    f"[SQ Evaluation] Skipped for {rfq_name}: {exc}"
                )


def get_evaluation_result(rfq_name: str) -> list[dict]:
    """
    Return a list of dicts representing the scored SQs for an RFQ,
    ordered by score descending. Read-only, no side effects.
    """
    return frappe.get_all(
        "Supplier Quotation",
        filters={
            "docstatus": 1,
            "wd_evaluation_score": [">", 0],
        },
        fields=[
            "name", "supplier", "grand_total", "wd_delivery_days",
            "wd_payment_days", "wd_evaluation_score", "wd_evaluation_status",
            "wd_evaluated_on",
        ],
        # Filter to SQs that quote at least one item from this RFQ
        # by joining via item child table
        order_by="wd_evaluation_score desc",
    )


# ── Validation helpers ────────────────────────────────────────────────────────

def validate_sq_before_submit(sq_doc) -> None:
    """
    Called from Supplier Quotation before_submit.
    Ensures mandatory evaluation fields are populated.
    """
    if flt(sq_doc.grand_total) <= 0:
        frappe.throw(
            _("Cannot submit Supplier Quotation {0}: grand total must be greater than zero.").format(
                sq_doc.name
            )
        )

    delivery_days = cint(getattr(sq_doc, "wd_delivery_days", 0))
    if delivery_days <= 0:
        frappe.throw(
            _("Cannot submit Supplier Quotation {0}: Delivery Days must be greater than zero.").format(
                sq_doc.name
            )
        )


# ── Internals ─────────────────────────────────────────────────────────────────

def _fetch_candidates(rfq_name: str) -> list[QuotationCandidate]:
    """
    Return all submitted (docstatus=1) Supplier Quotations that quote
    at least one item from `rfq_name`.
    """
    rows = frappe.db.sql(
        """
        SELECT DISTINCT
            sq.name,
            sq.supplier,
            sq.grand_total,
            COALESCE(sq.wd_delivery_days, 0)  AS delivery_days,
            COALESCE(sq.wd_payment_days, 0)   AS payment_days
        FROM `tabSupplier Quotation` sq
        INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
        WHERE sq.docstatus = 1
          AND sqi.request_for_quotation = %s
        ORDER BY sq.creation ASC
        """,
        (rfq_name,),
        as_dict=True,
    )

    return [
        QuotationCandidate(
            name          = r["name"],
            supplier      = r["supplier"],
            grand_total   = flt(r["grand_total"]),
            delivery_days = cint(r["delivery_days"]),
            payment_days  = cint(r["payment_days"]),
        )
        for r in rows
    ]


def _validate_candidates(rfq_name: str, candidates: list[QuotationCandidate]) -> None:
    if len(candidates) < MIN_QUOTATIONS_REQUIRED:
        frappe.throw(
            _(
                "RFQ {0} has only {1} submitted quotation(s). "
                "At least {2} are required to run evaluation."
            ).format(rfq_name, len(candidates), MIN_QUOTATIONS_REQUIRED),
            frappe.ValidationError,
        )

    zero_rate = [c.name for c in candidates if c.grand_total <= 0]
    if zero_rate:
        frappe.throw(
            _("The following quotations have a zero grand total and cannot be evaluated: {0}").format(
                ", ".join(zero_rate)
            ),
            frappe.ValidationError,
        )


def _score(candidates: list[QuotationCandidate]) -> None:
    """
    Compute normalised scores for each dimension and combine into total_score.
    Mutates candidates in place.
    """
    totals      = [c.grand_total   for c in candidates]
    deliveries  = [c.delivery_days for c in candidates]
    payments    = [c.payment_days  for c in candidates]

    min_total,  max_total   = min(totals),     max(totals)
    min_deliv,  max_deliv   = min(deliveries), max(deliveries)
    min_pay,    max_pay     = min(payments),   max(payments)

    for c in candidates:
        # Rate: lower is better → invert after normalisation
        c.rate_score     = _normalise_inverted(c.grand_total,   min_total, max_total)
        # Delivery: fewer days is better → invert
        c.delivery_score = _normalise_inverted(c.delivery_days, min_deliv, max_deliv)
        # Payment: more days is better → direct normalisation
        c.payment_score  = _normalise(c.payment_days, min_pay, max_pay)

        c.total_score = round(
            WEIGHT_RATE     * c.rate_score
            + WEIGHT_DELIVERY * c.delivery_score
            + WEIGHT_PAYMENT  * c.payment_score,
            6,
        )

    # Mark the highest scorer as winner (first in list after sort = highest score)
    best_score = max(c.total_score for c in candidates)
    for c in candidates:
        c.is_winner = (c.total_score == best_score)

    # If there's a tie, pick the one with the lower grand total as the single winner
    if sum(1 for c in candidates if c.is_winner) > 1:
        tied = sorted(
            [c for c in candidates if c.is_winner],
            key=lambda c: (c.grand_total, c.delivery_days, -c.payment_days),
        )
        for c in candidates:
            c.is_winner = (c.name == tied[0].name)


def _persist(candidates: list[QuotationCandidate]) -> None:
    """Write scores and evaluation status back to the database."""
    evaluated_at = now_datetime()
    for c in candidates:
        status = "Approved" if c.is_winner else "Rejected"
        frappe.db.set_value(
            "Supplier Quotation",
            c.name,
            {
                "wd_evaluation_score":  c.total_score,
                "wd_evaluation_status": status,
                "wd_evaluated_on":      evaluated_at,
            },
            update_modified=False,
        )

    frappe.db.commit()


def _get_linked_rfqs(sq_doc) -> list[str]:
    """Return all RFQ names referenced by the SQ's item rows."""
    return list({
        item.request_for_quotation
        for item in sq_doc.items
        if item.request_for_quotation
    })


def _all_suppliers_quoted(rfq_name: str) -> bool:
    """
    Return True when every supplier in the RFQ Supplier child table
    has at least one submitted Supplier Quotation.
    """
    invited = frappe.get_all(
        "Request for Quotation Supplier",
        filters={"parent": rfq_name},
        pluck="supplier",
    )
    if not invited:
        return False

    for supplier in invited:
        submitted_count = frappe.db.sql(
            """
            SELECT COUNT(sq.name)
            FROM `tabSupplier Quotation` sq
            INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
            WHERE sq.supplier = %s
              AND sqi.request_for_quotation = %s
              AND sq.docstatus = 1
            """,
            (supplier, rfq_name),
        )[0][0]
        if not submitted_count:
            return False

    return True


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _normalise(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalise: 0.0 (worst) → 1.0 (best). Equal values → 1.0."""
    if max_val == min_val:
        return 1.0
    return (value - min_val) / (max_val - min_val)


def _normalise_inverted(value: float, min_val: float, max_val: float) -> float:
    """Inverted min-max: lowest value → 1.0 (best)."""
    if max_val == min_val:
        return 1.0
    return 1.0 - (value - min_val) / (max_val - min_val)
