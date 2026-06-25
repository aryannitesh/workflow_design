"""
Reusable email helpers for workflow_design notifications.

All notification sending goes through `send_workflow_email()`.  Nothing else
in this module talks to frappe.sendmail directly, keeping the surface area for
testing and future changes minimal.
"""

import frappe
from frappe import _
from frappe.utils import get_url_to_form


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_workflow_email(
    *,
    doc,
    recipient_role: str,
    template_name: str,
    subject: str,
    extra_context: dict | None = None,
):
    """
    Resolve every user who holds `recipient_role` and send them a templated email.

    Args:
        doc:            The Frappe document that triggered the notification.
        recipient_role: Role name whose members should receive the email.
        template_name:  Name of the Jinja template file under
                        workflow_design/templates/emails/<template_name>.html
        subject:        Email subject line (plain string, already translated).
        extra_context:  Optional dict merged into the template context.
    """
    recipients = get_role_emails(recipient_role)
    if not recipients:
        frappe.logger("workflow_design").warning(
            f"No users found for role '{recipient_role}' – skipping notification."
        )
        return

    context = _build_context(doc, extra_context)
    message = _render_template(template_name, context)

    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=message,
        reference_doctype=doc.doctype,
        reference_name=doc.name,
        delayed=False,   # send immediately; change to True for queue-based sending
    )


def get_role_emails(role: str) -> list[str]:
    """
    Return a deduplicated list of enabled user emails that hold `role`.
    System / Guest users are excluded.
    """
    users = frappe.get_all(
        "Has Role",
        filters={"role": role, "parenttype": "User"},
        fields=["parent"],
        pluck="parent",
    )
    if not users:
        return []

    emails = frappe.get_all(
        "User",
        filters={
            "name": ["in", users],
            "enabled": 1,
            "user_type": "System User",
        },
        pluck="email",
    )
    return list({e for e in emails if e})   # deduplicate


def get_doc_url(doc) -> str:
    """Return the full desk URL for a document."""
    return get_url_to_form(doc.doctype, doc.name)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_context(doc, extra_context: dict | None) -> dict:
    context = {
        "doc": doc,
        "doc_url": get_doc_url(doc),
        "doc_name": doc.name,
        "doc_type": doc.doctype,
        "workflow_state": getattr(doc, "workflow_state", ""),
        "actor": frappe.session.user,
        "actor_full_name": frappe.db.get_value("User", frappe.session.user, "full_name")
                           or frappe.session.user,
        "site_name": frappe.local.site,
    }
    if extra_context:
        context.update(extra_context)
    return context


def _render_template(template_name: str, context: dict) -> str:
    template_path = f"workflow_design/templates/emails/{template_name}.html"
    return frappe.render_template(template_path, context)
