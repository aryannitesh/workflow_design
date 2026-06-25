# Supplier Portal — Complete Setup & Usage Guide

## 📋 Overview

The Supplier Portal allows suppliers to:
- Log in via standard ERPNext portal
- View assigned Request for Quotations (RFQs)
- Submit/update quotations with rates, delivery terms, payment terms
- Auto-creates/updates **Supplier Quotation** doctype

---

## ✅ What's Already Implemented

### Portal Pages

| URL | Purpose |
|-----|---------|
| `/supplier-rfq` | List all RFQs assigned to logged-in supplier |
| `/supplier-rfq/<rfq_name>` | View single RFQ + submit quotation form |

### Backend API

| Method | Purpose |
|--------|---------|
| `submit_supplier_quotation()` | Create/update Supplier Quotation |
| `get_rfq_list()` | Return all open RFQs for supplier |
| `get_rfq_detail()` | Return single RFQ data |

### Files

```
apps/workflow_design/
├── www/supplier-rfq/
│   ├── index.py                     # List view controller
│   ├── index.html                   # List view template
│   ├── detail.py                    # Detail view controller
│   └── detail.html                  # Quotation form template
├── api/supplier_portal.py           # Whitelisted API methods
├── portal/supplier_utils.py         # Auth guards & helpers
└── hooks.py                         # Routes configured
```

---

## 🚀 Setup Instructions

### 1. Create Supplier Master

```
Buying → Supplier → New
```

- **Supplier Name:** ABC Traders
- **Supplier Type:** Company
- **Default Currency:** (optional)
- Save

### 2. Create Contact for Supplier

```
CRM → Contact → New
```

- **First Name:** John
- **Last Name:** Doe
- **Email:** `john@abctraders.com`

**In "Links" child table:**
- **Link DocType:** `Supplier`
- **Link Name:** `ABC Traders`

Save

### 3. Create Portal User

```
Settings → User → New
```

- **Email:** `john@abctraders.com` (must match Contact email)
- **First Name:** John
- **User Type:** **Website User** (NOT System User)
- **Send Welcome Email:** Yes (optional)

**In "Roles" table:**
- Add role: **`Supplier`**

Send password reset link or set password manually.

### 4. Create Request for Quotation

```
Buying → Request for Quotation → New
```

- **Transaction Date:** Today
- **Schedule Date:** 7 days from now

**Items table:**
- Add items (e.g., "Widget A", qty 100)

**Suppliers table:**
- Add `ABC Traders`

**Submit** the RFQ (docstatus must be 1 — suppliers only see submitted RFQs)

---

## 🧪 Testing the Portal

### Login as Supplier

1. Open browser → `http://your-site.local/supplier-rfq`
2. If not logged in → redirects to `/login`
3. Login with: `john@abctraders.com` / password
4. Should see "My Request for Quotations" page

### RFQ List Page

Shows table with columns:
- RFQ No. (clickable link)
- Date
- Required By
- Status
- Quotation (shows existing SQ if submitted)
- Action (Submit Quotation / Update Quotation button)

### Submit Quotation

1. Click "Submit Quotation" on any RFQ
2. Form shows:
   - RFQ header (date, required by, status)
   - Items table with columns: Item, Qty, UOM, Rate, Amount
   - **Rate input fields** (editable)
   - Amount auto-calculates (Qty × Rate)
   - Grand Total at bottom
3. Fill in:
   - **Rate** for each item
   - **Delivery Days** (e.g., 7)
   - **Payment Days** (e.g., 30)
   - **Remarks** (optional notes)
4. Click "Submit Quotation"

**What happens:**
- JavaScript collects form data
- Calls `workflow_design.api.supplier_portal.submit_supplier_quotation`
- Backend creates **Supplier Quotation** doctype
- Redirects to `/supplier-quotations/<sq_name>`

### Update Existing Quotation

1. If supplier already submitted once, clicking RFQ shows:
   - Alert: "You have already submitted a quotation"
   - Form pre-filled with previous rates
   - Button says "Update Quotation"
2. Edit rates/terms
3. Click "Update Quotation"

**What happens:**
- Updates the existing draft Supplier Quotation
- Does not create duplicate

---

## 🔐 Security & Permissions

### Auth Guards

All portal pages and API calls check:

1. **User is logged in**
   ```python
   if frappe.session.user == "Guest":
       throw PermissionError
   ```

2. **User has Supplier role**
   ```python
   if not has_role("Supplier"):
       throw PermissionError
   ```

3. **User is linked to a Supplier**
   ```python
   supplier = get_current_supplier()  # via Contact → Dynamic Link
   if not supplier:
       throw PermissionError
   ```

4. **Supplier has access to the RFQ**
   ```python
   # Check supplier is in RFQ Suppliers child table
   exists = frappe.db.exists("Request for Quotation Supplier", {
       "parent": rfq_name, "supplier": supplier
   })
   ```

### Row-Level Security

Implemented in `permissions.py`:

**For RFQ list queries:**
- Supplier users only see RFQs where they are invited

**For SQ list queries:**
- Supplier users only see their own Supplier Quotations

---

## 🛠 Customization

### Change Portal Base URL

Routes are configurable in `hooks.py`:

```python
website_route_rules = [
    {"from_route": "/supplier-rfq", "to_route": "supplier-rfq"},
    {"from_route": "/supplier-rfq/<name>", "to_route": "supplier-rfq/detail"},
]
```

To change `/supplier-rfq` → `/vendor-portal`:

1. Rename folder: `www/supplier-rfq` → `www/vendor-portal`
2. Update `hooks.py`:
   ```python
   {"from_route": "/vendor-portal", "to_route": "vendor-portal"},
   {"from_route": "/vendor-portal/<name>", "to_route": "vendor-portal/detail"},
   ```

### Add Custom Fields to Quotation Form

Edit `www/supplier-rfq/detail.html`:

```html
<div class="col-md-4">
  <label class="form-label" for="wd-warranty">{{ _("Warranty Period") }}</label>
  <input type="text" id="wd-warranty" name="warranty" class="form-control">
</div>
```

Edit `api/supplier_portal.py` → `submit_supplier_quotation()`:

```python
def submit_supplier_quotation(..., warranty: str = ""):
    ...
    sq.warranty_period = warranty  # custom field on Supplier Quotation
```

### Email Notifications

Add in `api/supplier_portal.py` after `sq.insert()`:

```python
from workflow_design.utils.email_utils import send_workflow_email

frappe.sendmail(
    recipients=["purchase@company.com"],
    subject=f"New Supplier Quotation from {supplier}",
    message=f"Supplier {supplier} submitted quotation {sq.name} for RFQ {rfq_name}",
)
```

---

## 🐛 Troubleshooting

### "Permission Denied" when accessing portal

**Check 1:** User has `Supplier` role
```bash
bench --site <site> console
```
```python
import frappe
user = "john@abctraders.com"
roles = frappe.get_all("Has Role", filters={"parent": user}, pluck="role")
print(roles)  # Must include 'Supplier'
```

**Fix:**
```python
frappe.get_doc("User", user).add_roles("Supplier")
```

**Check 2:** User is linked to Supplier via Contact
```python
from erpnext.controllers.website_list_for_contact import get_customers_suppliers
_customers, suppliers = get_customers_suppliers("Request for Quotation Supplier", user)
print(suppliers)  # Must return supplier name
```

**Fix:** Create Contact → add Dynamic Link to Supplier

### "No RFQs showing" on portal

**Check:** RFQ must be submitted (docstatus = 1)
```python
rfq = frappe.get_doc("Request for Quotation", "RFQ-00001")
print(rfq.docstatus)  # Must be 1
```

**Check:** Supplier is in RFQ Suppliers table
```python
exists = frappe.db.exists("Request for Quotation Supplier", {
    "parent": "RFQ-00001",
    "supplier": "ABC Traders"
})
print(exists)  # Must be True
```

### "Form submission fails"

**Check browser console:** Press F12 → Console tab → look for errors

**Check server logs:**
```bash
tail -f logs/frappe.log | grep supplier_portal
```

**Common issue:** Items list empty or malformed

Ensure frontend JS correctly builds items array:
```javascript
{
  item_code: "...",
  request_for_quotation_item: "...",
  qty: 100,
  rate: 50.00
}
```

### Portal user cannot access desk

This is correct — `Supplier` role is a **portal role**, not a desk role.

If supplier needs desk access:
1. Change User Type to "System User"
2. Assign additional roles (Purchase User, etc.)

---

## 📊 Database Schema

### Request for Quotation Supplier (Child Table)

| Field | Type | Purpose |
|-------|------|---------|
| parent | Link | RFQ name |
| supplier | Link | Supplier name |
| email_sent | Check | Email notification flag |

**Portal Query:**
```sql
SELECT DISTINCT rfqs.parent
FROM `tabRequest for Quotation Supplier` rfqs
WHERE rfqs.supplier = 'ABC Traders'
```

### Supplier Quotation

| Field | Type | Purpose |
|-------|------|---------|
| supplier | Link | Supplier name |
| transaction_date | Date | Quote date |
| schedule_date | Date | Delivery date (nowdate + delivery_days) |
| terms | Text Editor | Remarks from portal form |

**Portal Creates:**
- Supplier Quotation header
- Supplier Quotation Item rows (linked to RFQ via `request_for_quotation_item`)

---

## 🎯 Workflow Integration

### After Supplier submits quotation:

1. **Supplier Quotation** created (draft, docstatus = 0)
2. Purchase team reviews in desk
3. Purchase team can submit the SQ
4. **Evaluation engine** can run (if configured in `workflow_design`)
5. Purchase Order created from winning SQ

### Custom Fields on Supplier Quotation

If evaluation is enabled, these fields auto-populate:
- `wd_delivery_days` → from portal form
- `wd_payment_days` → from portal form
- `wd_evaluation_status` → Pending/Approved/Rejected
- `wd_evaluation_score` → Composite score

---

## 🔗 Related Components

### Permissions Module

File: `workflow_design/permissions.py`

Implements:
- `get_permission_query_conditions()` — row-level filters
- `has_permission()` — single-document access checks

Registered in `hooks.py`:
```python
has_website_permission = {
    "Request for Quotation": "workflow_design.permissions.has_permission",
    "Supplier Quotation": "workflow_design.permissions.has_permission",
}
```

### Portal Menu

Configured in `hooks.py`:
```python
portal_menu_items = [
    {
        "title": "My RFQs",
        "route": "/supplier-rfq",
        "reference_doctype": "Request for Quotation",
        "role": "Supplier",
    },
]
```

This adds "My RFQs" link to the portal sidebar.

---

## 📝 Summary

**Status:** ✅ Fully implemented

**Access URL:** `http://your-site.local/supplier-rfq`

**Required Setup:**
1. Supplier master
2. Contact linked to Supplier
3. Portal user with Supplier role
4. Submitted RFQ with supplier invited

**Features:**
- List all assigned RFQs
- View RFQ details
- Submit/update quotation with rates & terms
- Auto-creates Supplier Quotation in ERPNext
- Secure row-level permissions

**Next Steps:**
- Configure email notifications when SQ is submitted
- Enable evaluation engine if needed
- Customize portal branding/styling
