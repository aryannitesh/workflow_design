"""Weekly scheduled tasks for workflow_design."""
import frappe


def procurement_summary_report():
    """
    Send a weekly procurement summary email to Purchase Managers and Supply Chain Managers.

    Covers the previous 7 days:
      - MRs raised / approved / rejected
      - RFQs issued
      - Supplier Quotations received
      - Purchase Orders created
    """
    from frappe.utils import add_days, today

    from workflow_design.utils.email_utils import get_role_emails, _render_template

    end_date = today()
    start_date = add_days(end_date, -7)

    def _count(doctype, extra_filters=None):
        filters = {"creation": ["between", [start_date, end_date]], "docstatus": ["<", 2]}
        if extra_filters:
            filters.update(extra_filters)
        return frappe.db.count(doctype, filters)

    stats = {
        "period_start":        start_date,
        "period_end":          end_date,
        "mrs_raised":          _count("Material Request"),
        "mrs_approved":        _count("Material Request", {"workflow_state": "WD Approved"}),
        "mrs_rejected":        _count("Material Request", {"workflow_state": "WD Rejected"}),
        "rfqs_issued":         _count("Request for Quotation"),
        "sq_received":         _count("Supplier Quotation"),
        "pos_created":         _count("Purchase Order"),
        "site_name":           frappe.local.site,
    }

    recipients = list(
        set(get_role_emails("WD Purchase Manager"))
        | set(get_role_emails("WD Supply Chain Manager"))
    )
    if not recipients:
        return

    message = _render_template("procurement_weekly_summary", stats)

    frappe.sendmail(
        recipients=recipients,
        subject=frappe._("[Weekly Summary] Procurement Activity {0} – {1}").format(start_date, end_date),
        message=message,
        delayed=False,
    )
    frappe.logger("workflow_design").info(
        f"[Weekly] Sent procurement summary to {len(recipients)} recipient(s)."
    )
