app_name = "workflow_design"
app_title = "Workflow Design"
app_publisher = "Your Name"
app_description = "Extends ERPNext procurement doctypes with configurable workflows"
app_email = "your@email.com"
app_license = "mit"

required_apps = ["frappe", "erpnext"]

# Fixtures
# --------
# Fixtures are exported/imported via `bench export-fixtures` and loaded on install.
# Each entry can be a doctype string or a dict with filters.
fixtures = [
    "Workflow State",
    "Workflow Action Master",
    "Workflow",
    "Role",
    "Custom Field",
    "Custom DocPerm",
]

# Installation
# ------------
before_install = "workflow_design.install.before_install"
after_install = "workflow_design.install.after_install"

before_uninstall = "workflow_design.uninstall.before_uninstall"
after_uninstall = "workflow_design.uninstall.after_uninstall"

# Document Events
# ---------------
# Hooks into standard ERPNext procurement doctype lifecycle events.
doc_events = {
    "Material Request": {
        "on_workflow_action": "workflow_design.events.material_request.on_workflow_action",
        "on_submit": "workflow_design.events.material_request.on_submit",
        "on_cancel": "workflow_design.events.material_request.on_cancel",
    },
    "Request for Quotation": {
        "on_submit": "workflow_design.events.request_for_quotation.on_submit",
        "on_cancel": "workflow_design.events.request_for_quotation.on_cancel",
    },
    "Supplier Quotation": {
        "before_submit": "workflow_design.events.supplier_quotation.before_submit",
        "on_submit":     "workflow_design.events.supplier_quotation.on_submit",
        "on_cancel":     "workflow_design.events.supplier_quotation.on_cancel",
    },
    "Quotation": {
        "on_submit": "workflow_design.events.quotation.on_submit",
        "on_cancel": "workflow_design.events.quotation.on_cancel",
    },
    "Purchase Order": {
        "before_insert": "workflow_design.events.purchase_order.before_insert",
        "before_submit": "workflow_design.events.purchase_order.before_submit",
        "on_submit":     "workflow_design.events.purchase_order.on_submit",
        "on_cancel":     "workflow_design.events.purchase_order.on_cancel",
    },
}

# Scheduled Tasks
# ---------------
scheduler_events = {
    "daily": [
        "workflow_design.tasks.daily.send_pending_approvals_digest",
        "workflow_design.tasks.daily.auto_close_expired_quotations",
    ],
    "hourly": [
        "workflow_design.tasks.hourly.check_rfq_deadlines",
        "workflow_design.tasks.hourly.escalate_overdue_material_requests_task",
    ],
    "weekly": [
        "workflow_design.tasks.weekly.procurement_summary_report",
    ],
}

# Jinja
# -----
jinja = {
    "methods": "workflow_design.utils.jinja_methods",
}

# Override doctype dashboards to inject procurement KPIs
override_doctype_dashboards = {
    "Purchase Order": "workflow_design.overrides.purchase_order.get_dashboard_data",
}

# JS/CSS includes
# ---------------
# Injected into the desk for all users
# app_include_js = "/assets/workflow_design/js/workflow_design.js"
# app_include_css = "/assets/workflow_design/css/workflow_design.css"

# Per-doctype JS overrides
doctype_js = {
    "Material Request":       "public/js/material_request.js",
    "Request for Quotation":  "public/js/request_for_quotation.js",
    "Supplier Quotation":     "public/js/supplier_quotation.js",
    "Quotation":              "public/js/quotation.js",
    "Purchase Order":         "public/js/purchase_order.js",
}

# Portal
# ------
# Expose procurement documents to portal users (suppliers)
website_route_rules = [
    {"from_route": "/supplier-rfq",        "to_route": "supplier-rfq"},
    {"from_route": "/supplier-rfq/<name>", "to_route": "supplier-rfq/detail"},
]

portal_menu_items = [
    {
        "title": "My RFQs",
        "route": "/supplier-rfq",
        "reference_doctype": "Request for Quotation",
        "role": "Supplier",
    },
    {
        "title": "My Quotations",
        "route": "/supplier-quotations",
        "reference_doctype": "Supplier Quotation",
        "role": "Supplier",
    },
    {
        "title": "Purchase Orders",
        "route": "/purchase-orders",
        "reference_doctype": "Purchase Order",
        "role": "Supplier",
    },
]

# Portal document-level permissions (single document view guard)
has_website_permission = {
    "Request for Quotation": "workflow_design.permissions.has_permission",
    "Supplier Quotation":    "workflow_design.permissions.has_permission",
    "Purchase Order":        "workflow_design.permissions.has_permission",
}

# Permissions
# -----------
permission_query_conditions = {
    "Material Request":      "workflow_design.permissions.get_permission_query_conditions",
    "Request for Quotation": "workflow_design.permissions.get_permission_query_conditions",
    "Supplier Quotation":    "workflow_design.permissions.get_permission_query_conditions",
    "Purchase Order":        "workflow_design.permissions.get_permission_query_conditions",
}

has_permission = {
    "Material Request":      "workflow_design.permissions.has_permission",
    "Request for Quotation": "workflow_design.permissions.has_permission",
    "Supplier Quotation":    "workflow_design.permissions.has_permission",
    "Purchase Order":        "workflow_design.permissions.has_permission",
}

# Notification Config (desk bell icon counts)
# -------------------------------------------
notification_config = "workflow_design.notifications.get_notification_config"
