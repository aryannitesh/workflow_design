# Material Request Escalation — Implementation Guide

## Overview

The escalation system automatically monitors Material Requests stuck in "Pending Purchase Manager Approval" for more than 24 hours and sends alert emails to Supply Chain Managers.

---

## ✅ What's Already Implemented

### 1. **Custom Fields on Material Request**

Three escalation-tracking fields have been added via `fixtures/custom_field.json`:

| Field | Type | Description |
|-------|------|-------------|
| `wd_pending_since` | Datetime | Timestamp when MR entered "Pending Purchase Manager Approval" state |
| `wd_escalation_sent` | Check | Boolean flag — `1` if escalation email already sent, `0` otherwise |
| `wd_escalation_datetime` | Datetime | Timestamp when escalation email was sent |

**Location in fixture:** `apps/workflow_design/workflow_design/fixtures/custom_field.json`

These fields are:
- **Read-only** (users can't modify them manually)
- **Not printed** on documents
- **Auto-managed** by backend hooks

---

### 2. **Workflow Event Hooks**

The `on_workflow_action` event handler in `events/material_request.py` manages the escalation lifecycle:

**When MR is submitted (`WD Submit for Approval` or `WD Resubmit`):**
```python
def _stamp_pending_since(doc):
    frappe.db.set_value("Material Request", doc.name, {
        "wd_pending_since": now_datetime(),
        "wd_escalation_sent": 0,
        "wd_escalation_datetime": None,
    }, update_modified=False)
```
- Sets `wd_pending_since` to current time
- Resets escalation flags (in case MR was previously escalated and resubmitted)

**When MR moves out of "Pending PM Approval":**
```python
def _reset_escalation_flags(doc):
    frappe.db.set_value("Material Request", doc.name, {
        "wd_pending_since": None,
        "wd_escalation_sent": 0,
        "wd_escalation_datetime": None,
    }, update_modified=False)
```
- Clears all escalation tracking
- Called on: Approve, Reject, Request Review

**Location:** `apps/workflow_design/workflow_design/events/material_request.py`

---

### 3. **Escalation Logic Module**

`utils/mr_escalation.py` contains the core escalation engine:

**Configuration:**
```python
SLA_HOURS = 24  # Breach threshold
PENDING_STATE = "WD Pending Purchase Manager Approval"
ROLE_SCM = "WD Supply Chain Manager"
```

**Main Function:**
```python
def escalate_overdue_material_requests() -> int:
    overdue = _fetch_overdue_records()
    sent_count = 0
    for record in overdue:
        try:
            doc = frappe.get_doc("Material Request", record["name"])
            _send_escalation(doc)
            _mark_escalated(doc)
            sent_count += 1
        except Exception:
            frappe.log_error(...)
    return sent_count
```

**How it queries overdue MRs:**
```python
def _fetch_overdue_records():
    threshold = frappe.utils.add_to_date(now_datetime(), hours=-SLA_HOURS)
    return frappe.get_all("Material Request", filters={
        "workflow_state": PENDING_STATE,
        "wd_escalation_sent": 0,
        "wd_pending_since": ["<=", threshold],
        "docstatus": ["!=", 2],  # exclude cancelled
    }, fields=["name", "owner", "wd_pending_since"])
```

**Location:** `apps/workflow_design/workflow_design/utils/mr_escalation.py`

---

### 4. **Hourly Scheduler Task**

Registered in `hooks.py`:
```python
scheduler_events = {
    "hourly": [
        "workflow_design.tasks.hourly.escalate_overdue_material_requests_task",
    ],
}
```

**Task implementation** (`tasks/hourly.py`):
```python
def escalate_overdue_material_requests_task():
    count = escalate_overdue_material_requests()
    if count:
        frappe.logger("workflow_design").info(
            f"[Hourly] Sent {count} escalation email(s) for overdue Material Requests."
        )
```

**When it runs:** Every hour, on the hour (e.g., 10:00, 11:00, 12:00)

**Location:**
- Hook: `apps/workflow_design/workflow_design/hooks.py`
- Task: `apps/workflow_design/workflow_design/tasks/hourly.py`

---

### 5. **Email Template**

HTML email template at `templates/emails/mr_escalation.html`.

**Email contains:**
- MR document link
- Hours overdue
- Submitted by (user name)
- Pending since timestamp
- Call-to-action button to review the MR

**Email sent to:** All users with the `WD Supply Chain Manager` role

**Location:** `apps/workflow_design/workflow_design/templates/emails/mr_escalation.html`

---

## 🔧 How It Works End-to-End

```
┌──────────────────────────────────────────────────────────────┐
│ Purchase User submits MR                                     │
└───────────────────────┬──────────────────────────────────────┘
                        ▼
            on_workflow_action hook fires
                        │
                        ├─> Sets wd_pending_since = now()
                        ├─> Resets wd_escalation_sent = 0
                        └─> Resets wd_escalation_datetime = None
                        
                    [TIME PASSES]
                        
            ┌──────── Every Hour ────────┐
            │ Scheduler runs hourly task  │
            └──────────┬─────────────────┘
                       ▼
        escalate_overdue_material_requests()
                       │
                       ├─> Queries MRs where:
                       │    • workflow_state = "Pending PM Approval"
                       │    • wd_escalation_sent = 0
                       │    • wd_pending_since <= (now - 24 hours)
                       │
                       ├─> For each overdue MR:
                       │    • Send email to all SCM users
                       │    • Set wd_escalation_sent = 1
                       │    • Set wd_escalation_datetime = now()
                       │
                       └─> Logs count to console
                       
            [No duplicate escalations — flag prevents re-sending]
            
            When PM/SCM acts on the MR:
                       │
                       ├─> on_workflow_action fires again
                       └─> Resets all escalation flags
```

---

## 📊 Verification — Checking If It's Working

### 1. **Check Custom Fields Exist**

```bash
bench --site <site> console
```
```python
import frappe
fields = ["wd_pending_since", "wd_escalation_sent", "wd_escalation_datetime"]
for f in fields:
    exists = frappe.db.exists("Custom Field", f"Material Request-{f}")
    print(f"{f}: {'✓ Exists' if exists else '✗ Missing'}")
```

### 2. **Check Scheduler is Running**

```bash
bench --site <site> doctor
```
Look for "Scheduler Status: Active"

Or check scheduler logs:
```bash
tail -f logs/worker.log | grep escalate
```

### 3. **Manually Trigger Escalation (Testing)**

```bash
bench --site <site> console
```
```python
from workflow_design.utils.mr_escalation import escalate_overdue_material_requests
count = escalate_overdue_material_requests()
print(f"Sent {count} escalation emails")
```

### 4. **Check Escalation Status on an MR**

```python
import frappe
mr = frappe.get_doc("Material Request", "MAT-MR-2026-00008")
print(f"workflow_state: {mr.workflow_state}")
print(f"wd_pending_since: {mr.wd_pending_since}")
print(f"wd_escalation_sent: {mr.wd_escalation_sent}")
print(f"wd_escalation_datetime: {mr.wd_escalation_datetime}")
```

### 5. **View Email Queue (if outgoing email configured)**

```python
emails = frappe.get_all("Email Queue", 
    filters={"subject": ["like", "%Escalation%"]}, 
    fields=["name", "recipients", "status", "creation"],
    order_by="creation desc",
    limit=10)
for e in emails:
    print(e)
```

---

## 🚀 Deploying to Production

### Prerequisites

1. **Outgoing Email Must Be Configured**

Without email setup, escalations will silently fail. Configure in:
```bash
# Either via site_config.json
bench --site <site> set-config mail_server smtp.gmail.com
bench --site <site> set-config mail_port 587
bench --site <site> set-config use_tls 1
bench --site <site> set-config mail_login your@email.com
bench --site <site> set-config mail_password "your-app-password"

# Or via Email Account doctype (recommended)
# Go to: Setup → Email Account → New
```

2. **Scheduler Must Be Enabled**

```bash
bench --site <site> enable-scheduler
```

Verify it's running:
```bash
bench --site <site> execute frappe.utils.scheduler.is_scheduler_inactive
# Should return False
```

3. **Supply Chain Manager Role Users Must Have Valid Emails**

```python
import frappe
users = frappe.get_all("Has Role", 
    filters={"role": "WD Supply Chain Manager"}, 
    pluck="parent")
for u in users:
    email = frappe.db.get_value("User", u, "email")
    print(f"{u}: {email}")
```

---

## ⚙️ Configuration & Customization

### Change SLA Threshold

Edit `apps/workflow_design/workflow_design/utils/mr_escalation.py`:
```python
SLA_HOURS = 48  # Change from 24 to 48 hours
```

Restart workers:
```bash
bench restart
```

### Change Escalation Recipient Role

Edit `apps/workflow_design/workflow_design/utils/mr_escalation.py`:
```python
ROLE_SCM = "Your Custom Role"  # Change from "WD Supply Chain Manager"
```

### Customize Email Template

Edit `apps/workflow_design/workflow_design/templates/emails/mr_escalation.html`

### Add CC/BCC Recipients

Edit `_send_escalation()` in `mr_escalation.py`:
```python
frappe.sendmail(
    recipients=recipients,
    cc=["manager@company.com"],  # Add CC
    bcc=["audit@company.com"],   # Add BCC
    subject=...,
    message=...,
)
```

---

## 🐛 Troubleshooting

### Escalations Not Sending

**1. Check if scheduler is running:**
```bash
bench --site <site> doctor | grep -i scheduler
```

**2. Check for errors in logs:**
```bash
tail -f logs/worker.log | grep -i escalat
tail -f logs/frappe.log | grep -i escalat
```

**3. Manually trigger to see error:**
```python
from workflow_design.utils.mr_escalation import escalate_overdue_material_requests
escalate_overdue_material_requests()
```

### Escalations Sending Multiple Times

Check if `wd_escalation_sent` flag is being set:
```python
mr = frappe.get_doc("Material Request", "MAT-MR-2026-00XXX")
print(mr.wd_escalation_sent)  # Should be 1 after escalation
```

If still `0`, check `_mark_escalated()` function is being called.

### No Overdue MRs Found

**Check query filters:**
```python
from workflow_design.utils.mr_escalation import _fetch_overdue_records
overdue = _fetch_overdue_records()
print(f"Found {len(overdue)} overdue MRs:", overdue)
```

**Check a specific MR:**
```python
mr = frappe.get_doc("Material Request", "MAT-MR-2026-00XXX")
print(f"State: {mr.workflow_state}")
print(f"Pending since: {mr.wd_pending_since}")
print(f"Escalation sent: {mr.wd_escalation_sent}")

from frappe.utils import now_datetime, time_diff_in_hours
if mr.wd_pending_since:
    hours = time_diff_in_hours(now_datetime(), mr.wd_pending_since)
    print(f"Hours overdue: {hours}")
```

---

## 📝 Summary

| Component | File | Purpose |
|-----------|------|---------|
| **Custom Fields** | `fixtures/custom_field.json` | Track pending timestamp & escalation status |
| **Event Hooks** | `events/material_request.py` | Stamp timestamps, reset flags on state changes |
| **Escalation Logic** | `utils/mr_escalation.py` | Query overdue MRs, send emails, mark as escalated |
| **Scheduler Task** | `tasks/hourly.py` | Entry point called every hour |
| **Scheduler Registration** | `hooks.py` | Registers hourly task with Frappe |
| **Email Template** | `templates/emails/mr_escalation.html` | HTML email sent to SCM |

---

## 🎯 Key Design Decisions

1. **`update_modified=False`** — When stamping escalation fields, we don't update the `modified` timestamp to avoid falsely appearing as if the document was edited

2. **One email per document** — Each overdue MR triggers one email to all SCMs (not one email per SCM)

3. **`wd_escalation_sent` flag** — Prevents duplicate escalations even if scheduler runs multiple times while MR is still overdue

4. **Reset on state change** — Escalation flags are cleared when MR moves out of "Pending PM Approval", so a future resubmission starts a fresh SLA clock

5. **`db_set` instead of `doc.save()`** — Direct DB updates avoid retriggering workflow events and validation

---

**Status:** ✅ Fully implemented, tested, ready for production deployment once email is configured.
