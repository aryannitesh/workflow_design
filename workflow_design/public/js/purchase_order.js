// Desk customisation for Purchase Order
// • Shows traceability links (MR → RFQ → SQ) in the form header.
// • Warns the user if a PO is being saved without an Approved SQ reference.

frappe.ui.form.on("Purchase Order", {

    refresh(frm) {
        _render_traceability_links(frm);
        _check_sq_approval_status(frm);
    },

    before_submit(frm) {
        // Client-side pre-check: warn if any item is missing a SQ reference.
        const missing = frm.doc.items.filter(r => !r.supplier_quotation);
        if (missing.length) {
            frappe.throw(
                __("The following item rows have no Supplier Quotation reference: {0}. "
                   + "Please create this PO via Make Purchase Order from an Approved Supplier Quotation.",
                   [missing.map(r => r.item_code).join(", ")])
            );
        }
    },
});

// ---------------------------------------------------------------------------
// Traceability panel
// ---------------------------------------------------------------------------

function _render_traceability_links(frm) {
    if (frm.doc.docstatus !== 1) return;

    const sq  = frm.doc.wd_source_sq;
    const rfq = frm.doc.wd_source_rfq;
    const mr  = frm.doc.wd_source_mr;
    const rej = frm.doc.wd_rejected_sq_count || 0;

    if (!sq && !rfq && !mr) return;

    const link = (doctype, name) =>
        name
        ? `<a href="/app/${doctype.toLowerCase().replace(/ /g, "-")}/${encodeURIComponent(name)}">${name}</a>`
        : "—";

    const html = `
        <div style="font-size:13px;line-height:1.8">
            <strong>${__("Procurement Chain")}</strong><br>
            ${mr  ? `${__("Material Request")}: ${link("material-request", mr)}<br>` : ""}
            ${rfq ? `${__("Request for Quotation")}: ${link("request-for-quotation", rfq)}<br>` : ""}
            ${sq  ? `${__("Approved Quotation")}: ${link("supplier-quotation", sq)}<br>` : ""}
            ${rej ? `<span style="color:#dc2626">${__("{0} competing quotation(s) auto-rejected", [rej])}</span>` : ""}
        </div>`;

    frm.dashboard.set_headline(html);
}

// ---------------------------------------------------------------------------
// SQ approval status check
// ---------------------------------------------------------------------------

function _check_sq_approval_status(frm) {
    if (frm.doc.docstatus !== 0) return;   // only on draft

    const sq_names = [...new Set(
        (frm.doc.items || [])
            .map(r => r.supplier_quotation)
            .filter(Boolean)
    )];

    if (!sq_names.length) return;

    frappe.call({
        method: "workflow_design.api.po_validation.check_sq_approval",
        args:   { sq_names },
        callback(r) {
            if (!r.message) return;
            const unapproved = r.message.filter(s => s.status !== "Approved");
            if (unapproved.length) {
                frm.dashboard.set_headline_alert(
                    __("Warning: {0} linked Supplier Quotation(s) are not Approved. "
                       + "Submission will be blocked.", [unapproved.length]),
                    "orange"
                );
            }
        },
    });
}
