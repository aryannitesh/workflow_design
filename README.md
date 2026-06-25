# Workflow Design

A custom Frappe/ERPNext app that brings a proper procurement approval workflow to your organization. Built on top of standard ERPNext doctypes — no new tables, no extra complexity — just smarter behavior layered on what ERPNext already does.

---

## What Problem Does This Solve?

Out of the box, ERPNext lets anyone create a Material Request and convert it to a Purchase Order without any checks. There's no approval chain, no way to compare supplier quotes fairly, and no alerts when things get stuck.

This app fixes all of that. It adds:

- A structured approval process before a purchase request can move forward
- A supplier-facing portal so vendors can submit their own quotes
- An automatic scoring engine that picks the best quotation
- Escalation alerts when approvals are sitting idle too long
- A hard block that prevents Purchase Orders from being created from rejected quotations

Everything runs inside your existing ERPNext setup. No extra services, no extra databases.

---

## Requirements

- Frappe Framework v15
- ERPNext v15
- Python 3.10+

---

## Installation

```bash
# Get the app
bench get-app https://github.com/aryannitesh/workflow_design.git

# Install on your site
bench --site your-site.local install-app workflow_design

# Run migrations to load fixtures
bench --site your-site.local migrate
```

After installation, three custom roles are created automatically:

| Role | What they can do |
|------|-----------------|
| **WD Purchase User** | Create Material Requests, submit for approval |
| **WD Purchase Manager** | Approve, reject, or send back for review |
| **WD Supply Chain Manager** | Final approval, receives escalation alerts |

Assign these roles to your team members from `Settings → User`.

---

## Feature 1 — Material Request Approval Workflow

This is the core of the app. Every Material Request goes through a proper two-level approval before anything can be purchased.

### How it works

```
Purchase User creates MR
        ↓
Clicks "Submit for Approval"
        ↓
Purchase Manager reviews
    ├── Approve → goes to Supply Chain Manager
    ├── Reject  → ends here, user notified
    └── Request Review → sent back to Purchase User for correction
        ↓
Supply Chain Manager reviews
    ├── Approve → MR is fully approved (docstatus = 1)
    ├── Reject  → ends here
    └── Request Review → sent back to Purchase Manager
```

### Workflow States

| State | Who can edit | What it means |
|-------|-------------|---------------|
| WD Draft | Purchase User | Just created, being filled in |
| WD Pending Purchase Manager Approval | Purchase Manager | Waiting for first approval |
| WD Review by Purchase User | Purchase User | PM sent it back for corrections |
| WD Pending Supply Chain Manager Approval | Supply Chain Manager | Waiting for final approval |
| WD Review by Purchase Manager | Purchase Manager | SCM sent it back |
| WD Approved | — | Fully approved, submitted |
| WD Rejected | — | Rejected at some stage |

### What the form looks like

When a Purchase User opens a Material Request in Draft state, they see a **"Submit for Approval"** button as the primary action (the default Save button is hidden to keep things clean). Once submitted, the form locks for them and the Purchase Manager sees Approve / Reject / Request Review buttons.

The list view shows the actual workflow state as a colored badge instead of ERPNext's generic "Pending" status.

---

## Feature 2 — Escalation Alerts

Nobody wants an approval sitting in someone's inbox for days. The app watches for this automatically.

### How it works

Every hour, a scheduler task runs and looks for Material Requests that have been in **"Pending Purchase Manager Approval"** state for more than 24 hours without any action taken.

When it finds one, it:
1. Sends an escalation email to everyone with the **WD Supply Chain Manager** role
2. Records the time the escalation was sent on the document (`wd_escalation_datetime`)
3. Sets a flag (`wd_escalation_sent = 1`) so the same MR never gets escalated twice

If the Purchase Manager eventually acts on it (approve/reject/review), the flag resets. So if the same MR gets resubmitted later and sits again, the escalation clock starts fresh.

### Custom fields on Material Request

| Field | Type | Purpose |
|-------|------|---------|
| `wd_pending_since` | Datetime | When the MR entered pending state |
| `wd_escalation_sent` | Check | Whether an escalation email was already sent |
| `wd_escalation_datetime` | Datetime | When the escalation was sent |

These are all read-only and hidden from print — they're just for the system to track state internally.

### Change the SLA threshold

Open `workflow_design/utils/mr_escalation.py` and change this line:

```python
SLA_HOURS: int = 24  # change to 48 for 2-day threshold
```

Restart workers after changing: `bench restart`

---

## Feature 3 — Supplier Portal

Suppliers don't need a full ERPNext login to submit their quotations. They get their own portal page where they can see the RFQs they've been invited to and submit their pricing.

### Setup (one time per supplier)

1. Create the **Supplier** master in ERPNext (`Buying → Supplier → New`)
2. Create a **Contact** with the supplier's email and link it to the Supplier via the Links table
3. Create a **User** with that same email, set User Type to `Website User`, and assign the **Supplier** role

That's it. The supplier can now log in and see their RFQs.

### How it works for the supplier

1. Supplier opens `https://your-site.local/supplier-rfq`
2. Logs in with their portal credentials
3. Sees a list of all RFQs they've been invited to
4. Clicks on an RFQ to open the quotation form
5. Fills in:
   - Rate for each item
   - Delivery Days
   - Payment Days
   - Any remarks or conditions
6. Clicks "Submit Quotation"

This creates a **Supplier Quotation** document in ERPNext automatically. If they come back and update the form, it updates the existing quotation rather than creating a duplicate.

### Security

The portal is locked down at multiple levels. A supplier can only see:
- RFQs where their name appears in the Suppliers child table
- Supplier Quotations that belong to them

Any attempt to access another supplier's RFQ throws a permission error. The access checks happen both in the page controller and in the API layer, so there's no way around them.

---

## Feature 4 — Automatic Quotation Evaluation

Once all invited suppliers have submitted their quotations, the system automatically scores them and picks the best one. No manual comparison needed.

### Scoring formula

```
Total Score = (Rate Score × 40%) + (Delivery Score × 30%) + (Payment Score × 30%)
```

Each dimension is normalized across all candidates using min-max normalization:

- **Rate Score** — lowest grand total gets 1.0, highest gets 0.0
- **Delivery Score** — fewest delivery days gets 1.0, most gets 0.0
- **Payment Score** — most payment days gets 1.0, fewest gets 0.0

The supplier with the highest total score is marked **Approved**. Everyone else is marked **Rejected**.

### When does it run?

Automatically — when the last invited supplier submits their quotation. Once all suppliers have submitted, the engine fires on its own without anyone having to click anything.

You can also trigger it manually from the RFQ form:
`Actions → Evaluate Quotations`

This opens a results dialog showing the ranked list with individual scores for each dimension.

### Tie-breaking

If two suppliers end up with the same total score, the one with the lower grand total wins. If those are also equal, the one with fewer delivery days wins.

### What happens to the losing quotations?

Their `Evaluation Status` field is set to **Rejected**. On the form, they show a red badge — "✘ Not Selected (Rejected)". The **Purchase Order** button is hidden from the Create dropdown so nobody can accidentally raise a PO from a rejected quotation.

---

## Feature 5 — Purchase Order Protection

This is the enforcement layer. Even if someone tries to bypass the UI and create a Purchase Order from a rejected Supplier Quotation, the backend blocks it.

The `before_insert` hook on Purchase Order checks every item row's linked SQ. If any of them has `wd_evaluation_status = Rejected`, the save is aborted with a clear error message.

The only way to create a PO is from an **Approved** quotation.

---

## Full Procurement Flow (End to End)

Here's how a complete procurement cycle looks with this app installed:

```
1. Purchase User creates Material Request
2. Submits for approval → notification sent to Purchase Manager
3. Purchase Manager approves → notification sent to Supply Chain Manager
4. Supply Chain Manager approves → MR is submitted
   [If stuck at step 3 for 24h → escalation email to SCM]

5. Purchase team creates Request for Quotation, adds suppliers
6. Suppliers log into portal, submit their rates + terms

7. Once all suppliers have quoted → auto evaluation runs
8. Best quotation marked Approved, others Rejected

9. Purchase Manager opens winning Supplier Quotation
10. Clicks "Create → Purchase Order"
    [Rejected SQs cannot be converted to PO — button hidden + backend blocks]

11. PO submitted → traceability chain (MR → RFQ → SQ → PO) stamped on document
    → All competing quotations auto-rejected
```

---

## Email Notifications

The app sends emails at every significant step:

| Trigger | Who receives it |
|---------|----------------|
| MR submitted for approval | All Purchase Managers |
| PM approves MR | All Supply Chain Managers |
| PM or SCM rejects MR | Document owner (Purchase User) |
| PM or SCM requests review | Purchase User or Purchase Manager |
| SCM approves MR | Document owner |
| MR stuck for 24h | All Supply Chain Managers (escalation) |
| Daily digest (morning) | All Purchase Managers + Supply Chain Managers |
| SQ evaluation complete | Purchase team |
| PO submitted | Relevant stakeholders |

Email templates are in `workflow_design/templates/emails/`. Edit them to match your company's style.

> **Note:** Emails require outgoing email to be configured in your Frappe site. Without it, the system logs the attempt but nothing gets sent. This is fine for development. For production, set up SMTP in `Settings → Email Account`.

---




---

## License

MIT
