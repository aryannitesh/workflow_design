"""Daily scheduled tasks for workflow_design."""
import frappe


def send_pending_approvals_digest():
    """
    Send a daily digest to Purchase Managers and Supply Chain Managers listing
    every Material Request currently stuck in a pending-approval state.
    """
    pending_states = [
        "WD Pending Purchase Manager Approval",
        "WD Pending Supply Chain Manager Approval",
    ]

    rows = frappe.get_all(
        "Material Request",
        filters={"workflow_state": ["in", pending_states], "docstatus": ["<", 2]},
        fields=["name", "owner", "workflow_state", "transaction_date", "schedule_date"],
        order_by="transaction_date asc",
    )

    if not rows:
        return

    from workflow_design.utils.email_utils import get_role_emails, _render_template

    recipients = list(
        set(get_role_emails("WD Purchase Manager"))
        | set(get_role_emails("WD Supply Chain Manager"))
    )
    if not recipients:
        return

    context = {"pending_mrs": rows, "site_name": frappe.local.site}
    message = _render_template("mr_pending_digest", context)

    frappe.sendmail(
        recipients=recipients,
        subject=frappe._("[Daily Digest] {0} Material Request(s) Awaiting Approval").format(len(rows)),
        message=message,
        delayed=False,
    )
    frappe.logger("workflow_design").info(
        f"[Daily] Sent pending-approvals digest — {len(rows)} MR(s) to {len(recipients)} recipient(s)."
    )


def auto_close_expired_quotations():
    """
    Set Supplier Quotations whose valid_till date has passed to 'WD Expired'
    (if they are still in a submitted / open state).
    """
    today = frappe.utils.today()

    expired = frappe.get_all(
        "Supplier Quotation",
        filters={
            "docstatus": 1,
            "status": ["not in", ["Ordered", "Lost", "Cancelled"]],
            "valid_till": ["<", today],
            "workflow_state": ["not in", ["WD Expired"]],
        },
        pluck="name",
    )

    for sq_name in expired:
        try:
            sq = frappe.get_doc("Supplier Quotation", sq_name)
            sq.workflow_state = "WD Expired"
            sq.add_comment("Workflow", frappe._("Auto-expired by daily scheduler (valid_till passed)."))
            sq.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"[Daily] Failed to expire Supplier Quotation {sq_name}")

    if expired:
        frappe.logger("workflow_design").info(
            f"[Daily] Auto-closed {len(expired)} expired Supplier Quotation(s)."
        )
