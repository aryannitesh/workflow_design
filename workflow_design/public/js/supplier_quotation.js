// Desk customisation for Supplier Quotation
// Hides the "Purchase Order" button in the Create group for Rejected SQs

frappe.ui.form.on("Supplier Quotation", {
	onload_post_render(frm) {
		_maybe_hide_po_button(frm);
	},

	refresh(frm) {
		_render_evaluation_badge(frm);
		_maybe_hide_po_button(frm);
	},
});

function _maybe_hide_po_button(frm) {
	if (frm.doc.wd_evaluation_status !== "Rejected" || frm.doc.docstatus !== 1) return;

	// ERPNext controller runs its own refresh after ours.
	// Override cur_frm.add_custom_button so any subsequent call to add
	// "Purchase Order" in the "Create" group is silently dropped.
	const _original = frm.add_custom_button.bind(frm);
	frm.add_custom_button = function (label, fn, group) {
		if (label === __("Purchase Order") && group === __("Create")) {
			return $(); // return empty jQuery object — button not added
		}
		return _original(label, fn, group);
	};

	// Also remove it if it was already added before our override fired
	frm.remove_custom_button(__("Purchase Order"), __("Create"));
}

function _render_evaluation_badge(frm) {
	const status = frm.doc.wd_evaluation_status;
	if (!status || status === "Pending") return;

	const isApproved = status === "Approved";
	const colour = isApproved ? "green" : "red";
	const label = isApproved
		? __("✔ Best Quotation (Approved)  — Score: {0}", [(frm.doc.wd_evaluation_score || 0).toFixed(4)])
		: __("✘ Not Selected (Rejected)  — Score: {0}", [(frm.doc.wd_evaluation_score || 0).toFixed(4)]);

	frm.dashboard.set_headline_alert(
		`<span class="indicator-pill ${colour}" style="font-size:13px;padding:4px 10px">${label}</span>`,
		colour
	);
}
