"""
One-shot setup API — call this after install to push all fixtures into the DB
and wire up the workflow correctly.

Usage (bench console or whitelisted call from Administrator):
    bench --site <site> execute workflow_design.api.setup.run_setup
"""

import frappe
from frappe import _
from frappe.utils.fixtures import sync_fixtures


@frappe.whitelist()
def run_setup():
    """Load all fixtures and activate the workflow. Administrator only."""
    if frappe.session.user != "Administrator":
        frappe.throw(_("Only Administrator can run setup."), frappe.PermissionError)

    _load_fixtures()
    _ensure_workflow_state_field()
    _activate_workflow()
    frappe.db.commit()
    return {"status": "ok", "message": "Workflow Design setup complete."}


def _load_fixtures():
    sync_fixtures("workflow_design")


def _ensure_workflow_state_field():
    if frappe.db.exists("Custom Field", "Material Request-workflow_state"):
        return
    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Material Request",
        "fieldname": "workflow_state",
        "label": "Workflow State",
        "fieldtype": "Link",
        "options": "Workflow State",
        "insert_after": "amended_from",
        "read_only": 1,
        "no_copy": 1,
        "print_hide": 1,
        "in_list_view": 1,
        "in_standard_filter": 1,
        "module": "Workflow Design",
    }).insert(ignore_permissions=True)
    frappe.clear_cache(doctype="Material Request")


def _activate_workflow():
    if frappe.db.exists("Workflow", "WD Material Request Approval"):
        frappe.db.set_value("Workflow", "WD Material Request Approval", "is_active", 1)
        frappe.clear_cache(doctype="Material Request")
