import frappe

frappe.init(site="frappe.localhost")
frappe.connect()

print("=== Checking existing records ===")
states = frappe.get_all("Workflow State", filters={"workflow_state_name": ["like", "WD %"]}, pluck="name")
print("WD States:", states)
actions = frappe.get_all("Workflow Action Master", filters={"workflow_action_name": ["like", "WD %"]}, pluck="name")
print("WD Actions:", actions)

print("\n=== Creating Roles ===")
for role_name in ["WD Purchase User", "WD Purchase Manager", "WD Supply Chain Manager"]:
    if not frappe.db.exists("Role", role_name):
        frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1, "is_custom": 1}).insert(ignore_permissions=True)
        print(f"  Created: {role_name}")
    else:
        print(f"  Exists: {role_name}")

print("\n=== Creating Workflow States ===")
for state_name, style in [
    ("WD Draft", ""), ("WD Pending Purchase Manager Approval", "Warning"),
    ("WD Review by Purchase User", "Info"), ("WD Pending Supply Chain Manager Approval", "Warning"),
    ("WD Review by Purchase Manager", "Info"), ("WD Approved", "Success"), ("WD Rejected", "Danger"),
]:
    if not frappe.db.exists("Workflow State", state_name):
        frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state_name, "style": style}).insert(ignore_permissions=True)
        print(f"  Created: {state_name}")
    else:
        frappe.db.set_value("Workflow State", state_name, "style", style)
        print(f"  OK: {state_name}")

print("\n=== Creating Workflow Actions ===")
for action_name in ["WD Submit for Approval", "WD Approve", "WD Reject", "WD Request Review", "WD Resubmit"]:
    if not frappe.db.exists("Workflow Action Master", action_name):
        frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action_name}).insert(ignore_permissions=True)
        print(f"  Created: {action_name}")
    else:
        print(f"  Exists: {action_name}")

print("\n=== Creating Workflow ===")
WORKFLOW_NAME = "WD Material Request Approval"
if frappe.db.exists("Workflow", WORKFLOW_NAME):
    frappe.delete_doc("Workflow", WORKFLOW_NAME, ignore_permissions=True, force=True)
    print("  Deleted old workflow")

wf_doc = frappe.get_doc({
    "doctype": "Workflow",
    "workflow_name": WORKFLOW_NAME,
    "document_type": "Material Request",
    "workflow_state_field": "workflow_state",
    "is_active": 1,
    "send_email_alert": 0,
    "override_status": 0,
    "states": [
        {"state": "WD Draft",                                 "doc_status": "0", "allow_edit": "WD Purchase User"},
        {"state": "WD Pending Purchase Manager Approval",     "doc_status": "0", "allow_edit": "WD Purchase Manager"},
        {"state": "WD Review by Purchase User",               "doc_status": "0", "allow_edit": "WD Purchase User"},
        {"state": "WD Pending Supply Chain Manager Approval", "doc_status": "0", "allow_edit": "WD Supply Chain Manager"},
        {"state": "WD Review by Purchase Manager",            "doc_status": "0", "allow_edit": "WD Purchase Manager"},
        {"state": "WD Approved",                              "doc_status": "1", "allow_edit": "System Manager"},
        {"state": "WD Rejected",                              "doc_status": "0", "allow_edit": "System Manager"},
    ],
    "transitions": [
        {"state": "WD Draft",                                "action": "WD Submit for Approval", "next_state": "WD Pending Purchase Manager Approval",     "allowed": "WD Purchase User",        "allow_self_approval": 0},
        {"state": "WD Review by Purchase User",              "action": "WD Resubmit",            "next_state": "WD Pending Purchase Manager Approval",     "allowed": "WD Purchase User",        "allow_self_approval": 0},
        {"state": "WD Pending Purchase Manager Approval",    "action": "WD Approve",             "next_state": "WD Pending Supply Chain Manager Approval", "allowed": "WD Purchase Manager",     "allow_self_approval": 0},
        {"state": "WD Pending Purchase Manager Approval",    "action": "WD Reject",              "next_state": "WD Rejected",                              "allowed": "WD Purchase Manager",     "allow_self_approval": 0},
        {"state": "WD Pending Purchase Manager Approval",    "action": "WD Request Review",      "next_state": "WD Review by Purchase User",               "allowed": "WD Purchase Manager",     "allow_self_approval": 0},
        {"state": "WD Review by Purchase Manager",           "action": "WD Approve",             "next_state": "WD Pending Supply Chain Manager Approval", "allowed": "WD Purchase Manager",     "allow_self_approval": 0},
        {"state": "WD Review by Purchase Manager",           "action": "WD Reject",              "next_state": "WD Rejected",                              "allowed": "WD Purchase Manager",     "allow_self_approval": 0},
        {"state": "WD Pending Supply Chain Manager Approval","action": "WD Approve",             "next_state": "WD Approved",                              "allowed": "WD Supply Chain Manager", "allow_self_approval": 0},
        {"state": "WD Pending Supply Chain Manager Approval","action": "WD Reject",              "next_state": "WD Rejected",                              "allowed": "WD Supply Chain Manager", "allow_self_approval": 0},
        {"state": "WD Pending Supply Chain Manager Approval","action": "WD Request Review",      "next_state": "WD Review by Purchase Manager",            "allowed": "WD Supply Chain Manager", "allow_self_approval": 0},
    ],
})
wf_doc.insert(ignore_permissions=True)
print(f"  Workflow created: {WORKFLOW_NAME}")

print("\n=== workflow_state custom field ===")
if not frappe.db.exists("Custom Field", "Material Request-workflow_state"):
    frappe.get_doc({
        "doctype": "Custom Field", "dt": "Material Request",
        "fieldname": "workflow_state", "label": "Workflow State",
        "fieldtype": "Link", "options": "Workflow State",
        "insert_after": "amended_from", "read_only": 1,
        "no_copy": 1, "print_hide": 1, "in_list_view": 1,
        "in_standard_filter": 1, "module": "Workflow Design",
    }).insert(ignore_permissions=True)
    print("  Created")
else:
    print("  Already exists")

print("\n=== Custom DocPerms ===")
for role, read, write, create, submit, cancel in [
    ("WD Purchase User",        1, 1, 1, 0, 0),
    ("WD Purchase Manager",     1, 1, 1, 1, 1),
    ("WD Supply Chain Manager", 1, 0, 0, 1, 1),
]:
    existing = frappe.db.get_value("Custom DocPerm", {"parent": "Material Request", "role": role, "permlevel": 0}, "name")
    if existing:
        doc = frappe.get_doc("Custom DocPerm", existing)
    else:
        doc = frappe.new_doc("Custom DocPerm")
        doc.parent = "Material Request"; doc.parenttype = "DocType"
        doc.parentfield = "permissions"; doc.role = role; doc.permlevel = 0
    doc.update({"read": read, "write": write, "create": create, "submit": submit, "cancel": cancel,
                 "delete": 0, "amend": 0, "print": 1, "email": 1, "export": 1, "report": 1,
                 "import": 0, "share": 1 if write else 0})
    doc.save(ignore_permissions=True)
    print(f"  {role}: OK")

frappe.db.commit()
frappe.clear_cache(doctype="Material Request")
print("\n=== ALL DONE ===")
