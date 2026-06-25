"""
Uninstallation hooks for workflow_design.

Removes the workflow, custom field, permissions, and roles added by this app
so that the standard Material Request doctype is restored to its original state.
"""

import frappe
from frappe import _

ROLES = ["WD Purchase User", "WD Purchase Manager", "WD Supply Chain Manager"]
WORKFLOW_NAME = "WD Material Request Approval"
WORKFLOW_DOCTYPE = "Material Request"
WORKFLOW_STATE_FIELD = "workflow_state"


def before_uninstall():
    _deactivate_workflow()


def after_uninstall():
    _remove_custom_field()
    _remove_escalation_fields()
    _remove_sq_evaluation_fields()
    _remove_po_traceability_fields()
    _remove_custom_permissions()
    _remove_roles()
    frappe.db.commit()


def _deactivate_workflow():
    if frappe.db.exists("Workflow", WORKFLOW_NAME):
        frappe.db.set_value("Workflow", WORKFLOW_NAME, "is_active", 0)
        frappe.clear_cache(doctype=WORKFLOW_DOCTYPE)


def _remove_custom_field():
    field_name = f"{WORKFLOW_DOCTYPE}-{WORKFLOW_STATE_FIELD}"
    if frappe.db.exists("Custom Field", field_name):
        frappe.delete_doc("Custom Field", field_name, ignore_permissions=True)
        frappe.clear_cache(doctype=WORKFLOW_DOCTYPE)


def _remove_custom_permissions():
    for role in ROLES:
        perm_name = frappe.db.get_value(
            "Custom DocPerm",
            {"parent": WORKFLOW_DOCTYPE, "role": role},
            "name",
        )
        if perm_name:
            frappe.delete_doc("Custom DocPerm", perm_name, ignore_permissions=True)
    frappe.clear_cache(doctype=WORKFLOW_DOCTYPE)


def _remove_roles():
    for role_name in ROLES:
        if frappe.db.exists("Role", role_name):
            frappe.delete_doc("Role", role_name, ignore_permissions=True)


def _remove_escalation_fields():
    escalation_fieldnames = [
        "wd_escalation_section",
        "wd_escalation_sent",
        "wd_escalation_datetime",
        "wd_column_break_escalation",
        "wd_pending_since",
    ]
    for fieldname in escalation_fieldnames:
        field_key = f"{WORKFLOW_DOCTYPE}-{fieldname}"
        if frappe.db.exists("Custom Field", field_key):
            frappe.delete_doc("Custom Field", field_key, ignore_permissions=True)
    frappe.clear_cache(doctype=WORKFLOW_DOCTYPE)


def _remove_sq_evaluation_fields():
    sq_fieldnames = [
        "wd_evaluation_section",
        "wd_evaluation_status",
        "wd_evaluation_score",
        "wd_cb_evaluation",
        "wd_payment_days",
        "wd_delivery_days",
        "wd_evaluated_on",
    ]
    for fieldname in sq_fieldnames:
        field_key = f"Supplier Quotation-{fieldname}"
        if frappe.db.exists("Custom Field", field_key):
            frappe.delete_doc("Custom Field", field_key, ignore_permissions=True)
    frappe.clear_cache(doctype="Supplier Quotation")


def _remove_po_traceability_fields():
    po_fieldnames = [
        "wd_traceability_section",
        "wd_source_sq",
        "wd_source_rfq",
        "wd_col_break_trace",
        "wd_source_mr",
        "wd_rejected_sq_count",
    ]
    for fieldname in po_fieldnames:
        field_key = f"Purchase Order-{fieldname}"
        if frappe.db.exists("Custom Field", field_key):
            frappe.delete_doc("Custom Field", field_key, ignore_permissions=True)
    frappe.clear_cache(doctype="Purchase Order")
