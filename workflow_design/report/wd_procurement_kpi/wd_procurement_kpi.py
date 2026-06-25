"""
WD Procurement KPI — Script Report
====================================
Four KPIs tracked per Material Request:

  1. MR → RFQ Days    : days from MR creation to first linked RFQ creation
  2. Approved RFQs    : count of RFQs in submitted state for the period
  3. MR → PO Days     : days from MR creation to linked PO submission
  4. RFQ → PO Days    : days from first RFQ creation to PO submission

All day calculations use calendar days (DATEDIFF).
"""

import frappe
from frappe import _
from frappe.utils import flt, date_diff, getdate


def execute(filters=None):
    filters = filters or {}
    _validate(filters)
    columns = _get_columns()
    data    = _get_data(filters)
    summary = _get_summary(data)
    chart   = _get_chart(data)
    return columns, data, None, chart, summary


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(filters):
    if filters.get("from_date") and filters.get("to_date"):
        if date_diff(filters["to_date"], filters["from_date"]) < 0:
            frappe.throw(_("To Date cannot be before From Date."))


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def _get_columns():
    return [
        {
            "label": _("Material Request"),
            "fieldname": "material_request",
            "fieldtype": "Link",
            "options": "Material Request",
            "width": 160,
        },
        {
            "label": _("MR Date"),
            "fieldname": "mr_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("First RFQ"),
            "fieldname": "first_rfq",
            "fieldtype": "Link",
            "options": "Request for Quotation",
            "width": 150,
        },
        {
            "label": _("RFQ Date"),
            "fieldname": "rfq_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("MR → RFQ (Days)"),
            "fieldname": "mr_to_rfq_days",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": _("Approved RFQs"),
            "fieldname": "approved_rfq_count",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Purchase Order"),
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 160,
        },
        {
            "label": _("PO Date"),
            "fieldname": "po_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("MR → PO (Days)"),
            "fieldname": "mr_to_po_days",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": _("RFQ → PO (Days)"),
            "fieldname": "rfq_to_po_days",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 120,
        },
    ]


# ---------------------------------------------------------------------------
# Data queries
# ---------------------------------------------------------------------------

def _get_data(filters: dict) -> list[dict]:
    """
    Main query: anchor on Material Request, LEFT JOIN to first RFQ and first PO.
    """
    company_cond = "AND mr.company = %(company)s" if filters.get("company") else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            mr.name                              AS material_request,
            DATE(mr.creation)                    AS mr_date,
            mr.company                           AS company,

            -- First RFQ linked via RFQ Item → material_request field
            MIN(rfq.name)                        AS first_rfq,
            DATE(MIN(rfq.creation))              AS rfq_date,

            -- Count of submitted RFQs for this MR in the window
            COUNT(DISTINCT CASE
                WHEN rfq.docstatus = 1
                THEN rfq.name END)               AS approved_rfq_count,

            -- First PO linked via PO Item → material_request field
            MIN(po.name)                         AS purchase_order,
            DATE(MIN(po.modified))               AS po_date

        FROM `tabMaterial Request` mr

        -- RFQ linkage via items
        LEFT JOIN `tabRequest for Quotation Item` rfqi
               ON rfqi.material_request = mr.name
        LEFT JOIN `tabRequest for Quotation` rfq
               ON rfq.name = rfqi.parent
              AND rfq.docstatus IN (0, 1)

        -- PO linkage via items
        LEFT JOIN `tabPurchase Order Item` poi
               ON poi.material_request = mr.name
        LEFT JOIN `tabPurchase Order` po
               ON po.name = poi.parent
              AND po.docstatus = 1

        WHERE mr.docstatus != 2
          AND DATE(mr.creation) BETWEEN %(from_date)s AND %(to_date)s
          {company_cond}

        GROUP BY mr.name
        ORDER BY mr.creation DESC
        """,
        {
            "from_date": filters.get("from_date"),
            "to_date":   filters.get("to_date"),
            "company":   filters.get("company"),
        },
        as_dict=True,
    )

    # Calculate derived day-diff columns in Python for clarity and safety
    for row in rows:
        mr_dt  = getdate(row["mr_date"])  if row.get("mr_date")  else None
        rfq_dt = getdate(row["rfq_date"]) if row.get("rfq_date") else None
        po_dt  = getdate(row["po_date"])  if row.get("po_date")  else None

        row["mr_to_rfq_days"] = (
            flt(date_diff(rfq_dt, mr_dt), 1) if mr_dt and rfq_dt else None
        )
        row["mr_to_po_days"] = (
            flt(date_diff(po_dt, mr_dt), 1) if mr_dt and po_dt else None
        )
        row["rfq_to_po_days"] = (
            flt(date_diff(po_dt, rfq_dt), 1) if rfq_dt and po_dt else None
        )

    return rows


# ---------------------------------------------------------------------------
# Summary row (shown below the table)
# ---------------------------------------------------------------------------

def _get_summary(data: list[dict]) -> list[dict]:
    mr_to_rfq = [r["mr_to_rfq_days"] for r in data if r.get("mr_to_rfq_days") is not None]
    mr_to_po  = [r["mr_to_po_days"]  for r in data if r.get("mr_to_po_days")  is not None]
    rfq_to_po = [r["rfq_to_po_days"] for r in data if r.get("rfq_to_po_days") is not None]
    approved  = sum(r.get("approved_rfq_count") or 0 for r in data)

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 0

    return [
        {
            "label":        _("Avg MR → RFQ (Days)"),
            "value":        avg(mr_to_rfq),
            "datatype":     "Float",
            "indicator":    "blue",
        },
        {
            "label":        _("Total Approved RFQs"),
            "value":        approved,
            "datatype":     "Int",
            "indicator":    "green",
        },
        {
            "label":        _("Avg MR → PO (Days)"),
            "value":        avg(mr_to_po),
            "datatype":     "Float",
            "indicator":    "blue",
        },
        {
            "label":        _("Avg RFQ → PO (Days)"),
            "value":        avg(rfq_to_po),
            "datatype":     "Float",
            "indicator":    "blue",
        },
    ]


# ---------------------------------------------------------------------------
# Embedded chart (bar — avg turnaround days per month)
# ---------------------------------------------------------------------------

def _get_chart(data: list[dict]) -> dict:
    """
    Group data by month and plot average MR→RFQ, MR→PO, RFQ→PO days as a
    grouped bar chart.
    """
    from collections import defaultdict

    monthly: dict[str, dict] = defaultdict(lambda: {
        "mr_to_rfq": [], "mr_to_po": [], "rfq_to_po": []
    })

    for row in data:
        if not row.get("mr_date"):
            continue
        month_key = str(row["mr_date"])[:7]   # "YYYY-MM"
        if row.get("mr_to_rfq_days") is not None:
            monthly[month_key]["mr_to_rfq"].append(row["mr_to_rfq_days"])
        if row.get("mr_to_po_days") is not None:
            monthly[month_key]["mr_to_po"].append(row["mr_to_po_days"])
        if row.get("rfq_to_po_days") is not None:
            monthly[month_key]["rfq_to_po"].append(row["rfq_to_po_days"])

    labels = sorted(monthly.keys())

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 0

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name":   _("Avg MR → RFQ Days"),
                    "values": [avg(monthly[m]["mr_to_rfq"]) for m in labels],
                },
                {
                    "name":   _("Avg MR → PO Days"),
                    "values": [avg(monthly[m]["mr_to_po"]) for m in labels],
                },
                {
                    "name":   _("Avg RFQ → PO Days"),
                    "values": [avg(monthly[m]["rfq_to_po"]) for m in labels],
                },
            ],
        },
        "type":   "bar",
        "height": 320,
        "fieldtype": "Float",
    }
