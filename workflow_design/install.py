"""
Installation hooks for workflow_design.

Execution order on `bench --site <site> install-app workflow_design`:
  1. before_install()   – pre-flight checks
  2. Frappe loads fixtures automatically (fixtures/ *.json)
  3. after_install()    – post-fixture wiring (permissions, workflow field)
"""

import frappe
from frappe import _


ROLES = ["WD Purchase User", "WD Purchase Manager", "WD Supply Chain Manager"]

WORKFLOW_NAME = "WD Material Request Approval"
WORKFLOW_DOCTYPE = "Material Request"
WORKFLOW_STATE_FIELD = "workflow_state"


# ---------------------------------------------------------------------------
# Entry points (referenced in hooks.py)
# ---------------------------------------------------------------------------

def before_install():
    _check_erpnext_installed()


def after_install():
    _ensure_roles_exist()
    _ensure_workflow_state_field()
    _ensure_escalation_fields()
    _ensure_sq_evaluation_fields()
    _ensure_po_traceability_fields()
    _apply_doctype_permissions()
    _activate_workflow()
    frappe.db.commit()
    frappe.msgprint(_("Workflow Design installed successfully."), alert=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_erpnext_installed():
    if "erpnext" not in frappe.get_installed_apps():
        frappe.throw(_("workflow_design requires ERPNext to be installed first."))


def _ensure_roles_exist():
    """Create the three custom roles if they do not already exist."""
    for role_name in ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role_name,
                "desk_access": 1,
                "is_custom": 1,
            }).insert(ignore_permissions=True)


def _ensure_workflow_state_field():
    """
    Add a 'workflow_state' custom field to Material Request if it is missing.
    Frappe's workflow engine reads this field to track the current state.
    """
    field_name = f"{WORKFLOW_DOCTYPE}-{WORKFLOW_STATE_FIELD}"
    if frappe.db.exists("Custom Field", field_name):
        return

    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": WORKFLOW_DOCTYPE,
        "fieldname": WORKFLOW_STATE_FIELD,
        "label": "Workflow State",
        "fieldtype": "Link",
        "options": "Workflow State",
        "read_only": 1,
        "no_copy": 1,
        "print_hide": 1,
        "hidden": 0,
        "insert_after": "amended_from",
        "module": "Workflow Design",
    }).insert(ignore_permissions=True)


def _apply_doctype_permissions():
    """
    Add Custom DocPerm rows for each WD role on Material Request.
    Uses update_or_insert pattern so re-running install is safe.
    """
    perms = [
        # (role,                      read, write, create, submit, cancel)
        ("WD Purchase User",          1,    1,     1,      0,      0),
        ("WD Purchase Manager",       1,    1,     1,      1,      1),
        ("WD Supply Chain Manager",   1,    0,     0,      1,      1),
    ]

    for role, read, write, create, submit, cancel in perms:
        existing = frappe.db.get_value(
            "Custom DocPerm",
            {"parent": WORKFLOW_DOCTYPE, "role": role, "permlevel": 0},
            "name",
        )
        if existing:
            doc = frappe.get_doc("Custom DocPerm", existing)
        else:
            doc = frappe.new_doc("Custom DocPerm")
            doc.parent = WORKFLOW_DOCTYPE
            doc.parenttype = "DocType"
            doc.parentfield = "permissions"
            doc.role = role
            doc.permlevel = 0

        doc.update({
            "read": read, "write": write, "create": create,
            "submit": submit, "cancel": cancel,
            "delete": 0, "amend": 0,
            "print": 1, "email": 1, "export": 1, "report": 1,
            "import": 0, "share": 1 if write else 0,
        })
        doc.save(ignore_permissions=True)

    # Rebuild permission cache so changes take effect immediately
    frappe.clear_cache(doctype=WORKFLOW_DOCTYPE)


def _activate_workflow():
    """Mark the workflow as active (fixtures set is_active=1 but a fresh reload is safer)."""
    if frappe.db.exists("Workflow", WORKFLOW_NAME):
        frappe.db.set_value("Workflow", WORKFLOW_NAME, "is_active", 1)
        frappe.clear_cache(doctype=WORKFLOW_DOCTYPE)


# ---------------------------------------------------------------------------
# Escalation custom fields
# ---------------------------------------------------------------------------

_ESCALATION_FIELDS = [
    {
        "fieldname": "wd_escalation_section",
        "label": "Escalation",
        "fieldtype": "Section Break",
        "insert_after": "workflow_state",
        "collapsible": 1,
        "read_only": 1,
        "print_hide": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_escalation_sent",
        "label": "Escalation Sent",
        "fieldtype": "Check",
        "insert_after": "wd_escalation_section",
        "default": "0",
        "read_only": 1,
        "print_hide": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_escalation_datetime",
        "label": "Escalation Sent On",
        "fieldtype": "Datetime",
        "insert_after": "wd_escalation_sent",
        "read_only": 1,
        "print_hide": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_pending_since",
        "label": "Pending Since",
        "fieldtype": "Datetime",
        "insert_after": "wd_escalation_datetime",
        "read_only": 1,
        "print_hide": 1,
        "no_copy": 1,
        "description": "Set automatically when document enters Pending Purchase Manager Approval state.",
    },
]


def _ensure_escalation_fields():
    """Create the four escalation custom fields on Material Request if missing."""
    for spec in _ESCALATION_FIELDS:
        field_key = f"{WORKFLOW_DOCTYPE}-{spec['fieldname']}"
        if frappe.db.exists("Custom Field", field_key):
            continue
        doc = frappe.new_doc("Custom Field")
        doc.dt = WORKFLOW_DOCTYPE
        doc.module = "Workflow Design"
        doc.update(spec)
        doc.insert(ignore_permissions=True)

    frappe.clear_cache(doctype=WORKFLOW_DOCTYPE)


# ---------------------------------------------------------------------------
# Supplier Quotation evaluation custom fields
# ---------------------------------------------------------------------------

_SQ_EVALUATION_FIELDS = [
    {
        "fieldname": "wd_evaluation_section",
        "label": "WD Evaluation",
        "fieldtype": "Section Break",
        "insert_after": "terms",
        "collapsible": 1,
        "print_hide": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_evaluation_status",
        "label": "Evaluation Status",
        "fieldtype": "Select",
        "options": "\nPending\nApproved\nRejected",
        "insert_after": "wd_evaluation_section",
        "default": "Pending",
        "read_only": 1,
        "in_list_view": 1,
        "in_standard_filter": 1,
        "print_hide": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_evaluation_score",
        "label": "Evaluation Score",
        "fieldtype": "Float",
        "insert_after": "wd_evaluation_status",
        "read_only": 1,
        "print_hide": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_cb_evaluation",
        "label": "",
        "fieldtype": "Column Break",
        "insert_after": "wd_evaluation_score",
        "print_hide": 1,
    },
    {
        "fieldname": "wd_payment_days",
        "label": "Payment Days",
        "fieldtype": "Int",
        "insert_after": "wd_cb_evaluation",
        "default": "0",
    },
    {
        "fieldname": "wd_delivery_days",
        "label": "Delivery Days",
        "fieldtype": "Int",
        "insert_after": "wd_payment_days",
        "default": "0",
    },
    {
        "fieldname": "wd_evaluated_on",
        "label": "Evaluated On",
        "fieldtype": "Datetime",
        "insert_after": "wd_delivery_days",
        "read_only": 1,
        "print_hide": 1,
        "no_copy": 1,
    },
]

_SQ_DOCTYPE = "Supplier Quotation"


def _ensure_sq_evaluation_fields():
    """Create the SQ evaluation custom fields if missing."""
    for spec in _SQ_EVALUATION_FIELDS:
        field_key = f"{_SQ_DOCTYPE}-{spec['fieldname']}"
        if frappe.db.exists("Custom Field", field_key):
            continue
        doc = frappe.new_doc("Custom Field")
        doc.dt = _SQ_DOCTYPE
        doc.module = "Workflow Design"
        doc.update(spec)
        doc.insert(ignore_permissions=True)

    frappe.clear_cache(doctype=_SQ_DOCTYPE)


# ---------------------------------------------------------------------------
# Purchase Order traceability custom fields
# ---------------------------------------------------------------------------

_PO_TRACEABILITY_FIELDS = [
    {
        "fieldname": "wd_traceability_section",
        "label": "Procurement Traceability",
        "fieldtype": "Section Break",
        "insert_after": "terms",
        "collapsible": 1,
        "print_hide": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_source_sq",
        "label": "Source Supplier Quotation",
        "fieldtype": "Link",
        "options": "Supplier Quotation",
        "insert_after": "wd_traceability_section",
        "read_only": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_source_rfq",
        "label": "Source RFQ",
        "fieldtype": "Link",
        "options": "Request for Quotation",
        "insert_after": "wd_source_sq",
        "read_only": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_col_break_trace",
        "label": "",
        "fieldtype": "Column Break",
        "insert_after": "wd_source_rfq",
        "print_hide": 1,
    },
    {
        "fieldname": "wd_source_mr",
        "label": "Source Material Request",
        "fieldtype": "Link",
        "options": "Material Request",
        "insert_after": "wd_col_break_trace",
        "read_only": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "wd_rejected_sq_count",
        "label": "Other Quotations Rejected",
        "fieldtype": "Int",
        "insert_after": "wd_source_mr",
        "read_only": 1,
        "no_copy": 1,
        "default": "0",
    },
]

_PO_DOCTYPE = "Purchase Order"


def _ensure_po_traceability_fields():
    """Create the PO traceability custom fields if missing."""
    for spec in _PO_TRACEABILITY_FIELDS:
        field_key = f"{_PO_DOCTYPE}-{spec['fieldname']}"
        if frappe.db.exists("Custom Field", field_key):
            continue
        doc = frappe.new_doc("Custom Field")
        doc.dt = _PO_DOCTYPE
        doc.module = "Workflow Design"
        doc.update(spec)
        doc.insert(ignore_permissions=True)

    frappe.clear_cache(doctype=_PO_DOCTYPE)
