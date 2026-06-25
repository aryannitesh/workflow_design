# Workflow Design - Material Request Approval Setup

Complete implementation of a multi-level approval workflow for ERPNext Material Request.

## Business Process

**Purchase User** creates Material Request → submits for approval → **Purchase Manager** reviews → **Supply Chain Manager** approves → Approved.

## Workflow States

| State | doc_status | Editable By | Description |
|-------|------------|-------------|-------------|
| **WD Draft** | 0 (Draft) | WD Purchase User | Initial state - user creating/editing request |
| **WD Pending Purchase Manager Approval** | 0 (Draft) | WD Purchase Manager | Awaiting first approval |
| **WD Review by Purchase User** | 0 (Draft) | WD Purchase User | PM sent back for corrections |
| **WD Pending Supply Chain Manager Approval** | 0 (Draft) | WD Supply Chain Manager | Awaiting final approval |
| **WD Review by Purchase Manager** | 0 (Draft) | WD Purchase Manager | SCM sent back for corrections |
| **WD Approved** | 1 (Submitted) | System Manager | Fully approved, submitted |
| **WD Rejected** | 0 (Draft) | System Manager | Rejected by PM or SCM |

## Workflow Transitions

### From Draft
- **WD Submit for Approval** → Pending Purchase Manager Approval *(WD Purchase User)*

### From Pending Purchase Manager Approval
- **WD Approve** → Pending Supply Chain Manager Approval *(WD Purchase Manager)*
- **WD Reject** → WD Rejected *(WD Purchase Manager)*
- **WD Request Review** → Review by Purchase User *(WD Purchase Manager)*

### From Review by Purchase User
- **WD Resubmit** → Pending Purchase Manager Approval *(WD Purchase User)*

### From Pending Supply Chain Manager Approval
- **WD Approve** → WD Approved *(WD Supply Chain Manager)*
- **WD Reject** → WD Rejected *(WD Supply Chain Manager)*
- **WD Request Review** → Review by Purchase Manager *(WD Supply Chain Manager)*

### From Review by Purchase Manager
- **WD Approve** → Pending Supply Chain Manager Approval *(WD Purchase Manager)*
- **WD Reject** → WD Rejected *(WD Purchase Manager)*

## Roles & Permissions

| Role | Create | Read | Write | Submit | Cancel |
|------|--------|------|-------|--------|--------|
| **WD Purchase User** | ✅ | ✅ | ✅ (Draft/Review states only) | ❌ | ❌ |
| **WD Purchase Manager** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **WD Supply Chain Manager** | ❌ | ✅ | ❌ | ✅ | ✅ |

## Installation

### 1. Manual Setup (Recommended — Already Done)

Run the setup script:

```bash
bench --site <your-site> console < apps/workflow_design/setup_wd_workflow.py
```

This creates:
- 3 roles (WD Purchase User, WD Purchase Manager, WD Supply Chain Manager)
- 7 workflow states
- 5 workflow actions
- 1 workflow (WD Material Request Approval)
- workflow_state custom field on Material Request
- Custom DocPerms for the 3 roles

### 2. Via Fixtures (Future Installs)

The workflow can also be installed via Frappe fixtures:

```bash
bench --site <your-site> install-app workflow_design
bench --site <your-site> migrate
```

All workflow components are exported to `workflow_design/fixtures/` and will be automatically imported.

## Customization

### Change Workflow via UI

1. Go to **Workflow** list
2. Open **WD Material Request Approval**
3. Modify states, transitions, or assigned roles
4. Save

Changes take effect immediately.

### Export After Changes

After customizing via UI, export back to fixtures:

```bash
bench --site <your-site> export-fixtures --app workflow_design
```

This updates the JSON files in `workflow_design/fixtures/` so your custom workflow persists across reinstalls.

## Frontend Integration

### Button Behavior

The custom JavaScript (`public/js/material_request.js`) handles button visibility:

- **Draft state**: Shows "Save" and "Submit for Approval" buttons
- **Review states**: Shows "Save" and "Resubmit" buttons  
- **Pending states**: Shows "Approve", "Reject", "Request Review" buttons (based on role)
- Save button is hidden by default, "Submit for Approval" becomes primary

### List View

Workflow state is displayed as a badge in the Material Request list view with color coding:
- Draft: Gray
- Pending: Orange/Yellow
- Review: Blue
- Approved: Green
- Rejected: Red

## Backend Hooks

### Event Handlers

`workflow_design/events/material_request.py` provides:
- `on_workflow_action` - Triggers on every workflow transition
- `on_submit` - Fires when docstatus changes to 1 (Approved)
- `on_cancel` - Fires when docstatus changes to 2

### Email Notifications

Configured in `workflow_design/utils/mr_notifications.py`:
- Purchase Manager notified on submit
- Supply Chain Manager notified when PM approves
- Purchase User notified on rejection or review request
- Purchase User notified on final approval

### Escalation

`workflow_design/utils/mr_escalation.py` + hourly scheduler:
- Tracks Material Requests pending with PM for >24 hours
- Sends escalation email to all Supply Chain Managers
- One escalation per submission cycle

## File Structure

```
workflow_design/
├── fixtures/
│   ├── workflow.json                    # Workflow definition with states & transitions
│   ├── workflow_state.json              # 7 workflow states
│   ├── workflow_action_master.json      # 5 workflow actions
│   ├── role.json                        # 3 custom roles
│   ├── custom_field.json                # workflow_state field + escalation fields
│   └── custom_docperm.json              # Role-based permissions
├── events/
│   └── material_request.py              # Document event handlers
├── utils/
│   ├── mr_notifications.py              # Email notification dispatcher
│   ├── mr_escalation.py                 # SLA escalation logic
│   └── email_utils.py                   # Reusable email helpers
├── api/
│   ├── workflow_action.py               # Whitelisted workflow trigger endpoint
│   └── setup.py                         # One-shot setup API
├── public/js/
│   └── material_request.js              # Desk form customizations
├── tasks/
│   ├── hourly.py                        # Escalation scheduler
│   └── daily.py                         # Pending approvals digest
├── hooks.py                             # Frappe app hooks
├── install.py                           # Installation logic
└── setup_wd_workflow.py                 # Manual setup script

```

## Troubleshooting

### Workflow not showing

```bash
# Check if workflow is active
bench --site <site> console
>>> frappe.db.get_value("Workflow", "WD Material Request Approval", "is_active")
```

If `0` or `None`, activate it:

```bash
>>> frappe.db.set_value("Workflow", "WD Material Request Approval", "is_active", 1)
>>> frappe.db.commit()
```

### workflow_state field missing

```bash
bench --site <site> console < apps/workflow_design/setup_wd_workflow.py
```

This ensures the field exists.

### Old Material Requests have no workflow_state

Backfill them:

```bash
bench --site <site> console
>>> mrs = frappe.get_all("Material Request", filters={"docstatus": 0, "workflow_state": ["in", ["", None]]}, pluck="name")
>>> for mr in mrs:
...     frappe.db.set_value("Material Request", mr, "workflow_state", "WD Draft", update_modified=False)
>>> frappe.db.commit()
```

### Buttons not showing

```bash
# Rebuild assets
bench build --app workflow_design

# Clear browser cache
Ctrl+Shift+R (hard refresh)
```

### Permission errors

Check role assignment:

```bash
# In User doctype, ensure users have the appropriate WD roles assigned
```

## API Usage

The workflow can be triggered programmatically:

```python
import frappe
from workflow_design.api.workflow_action import apply_action

doc = frappe.get_doc("Material Request", "MAT-MR-2026-00001")
apply_action(
    doctype="Material Request",
    docname=doc.name,
    action="WD Submit for Approval"
)
```

Or from JavaScript:

```javascript
frappe.call({
    method: "workflow_design.api.workflow_action.apply_action",
    args: {
        doctype: "Material Request",
        docname: frm.doc.name,
        action: "WD Submit for Approval"
    },
    callback(r) {
        if (r.message) {
            frappe.model.sync(r.message);
            frm.refresh();
        }
    }
});
```

## Notes

- **doc_status Mapping**: Draft=0, Submitted=1, Cancelled=2. WD Rejected uses doc_status=0 (not 2) to allow corrections after rejection.
- **allow_edit**: Required field on every state. Terminal states (Approved/Rejected) use "System Manager" to prevent accidental edits.
- **Escalation**: Tracks `wd_pending_since` timestamp when entering PM approval state. Hourly job checks for breaches.
- **Frontend**: Buttons are controlled via `material_request.js` which checks `frm.doc.workflow_state` and `frappe.user_roles`.

## Support

For issues or questions, check:
- Frappe Workflow documentation: https://frappeframework.com/docs/user/en/desk/workflows
- ERPNext documentation: https://docs.erpnext.com/
