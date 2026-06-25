// List view: add workflow_state as a visible column
frappe.listview_settings["Material Request"] = {
	add_fields: ["workflow_state"],
	get_indicator(doc) {
		const state = doc.workflow_state;
		const map = {
			"WD Draft":                                  ["gray",   "workflow_state,=,WD Draft"],
			"WD Pending Purchase Manager Approval":      ["orange", "workflow_state,=,WD Pending Purchase Manager Approval"],
			"WD Pending Supply Chain Manager Approval":  ["yellow", "workflow_state,=,WD Pending Supply Chain Manager Approval"],
			"WD Review by Purchase User":                ["blue",   "workflow_state,=,WD Review by Purchase User"],
			"WD Review by Purchase Manager":             ["blue",   "workflow_state,=,WD Review by Purchase Manager"],
			"WD Approved":                               ["green",  "workflow_state,=,WD Approved"],
			"WD Rejected":                               ["red",    "workflow_state,=,WD Rejected"],
		};
		if (state && map[state]) return [state, map[state][0], map[state][1]];
	},
};

frappe.ui.form.on("Material Request", {
	refresh(frm) {
		const state = frm.doc.workflow_state;
		const roles = frappe.user_roles;

		// Purchase User — Draft state: hide Save, show "Submit for Approval"
		const is_draft_state = !state || state === "WD Draft";
		if (is_draft_state && frm.doc.docstatus === 0 && roles.includes("WD Purchase User")) {
			// Hide the default Save button
			frm.page.btn_primary.hide();

			frm.add_custom_button(__("Save"), () => {
				frm.save();
			});

			frm.add_custom_button(__("Submit for Approval"), () => {
				const do_action = () => _trigger_workflow_action(frm, "WD Submit for Approval");
				if (frm.is_dirty()) {
					frm.save().then(do_action);
				} else {
					do_action();
				}
			}).addClass("btn-primary");
		}

		// Purchase User — resubmit after PM requested review
		if (state === "WD Review by Purchase User" && roles.includes("WD Purchase User")) {
			frm.page.btn_primary.hide();

			frm.add_custom_button(__("Save"), () => {
				frm.save();
			});

			frm.add_custom_button(__("Resubmit"), () => {
				const do_action = () => _trigger_workflow_action(frm, "WD Resubmit");
				if (frm.is_dirty()) {
					frm.save().then(do_action);
				} else {
					do_action();
				}
			}).addClass("btn-primary");
		}

		// Purchase Manager — pending approval
		if (state === "WD Pending Purchase Manager Approval" && roles.includes("WD Purchase Manager")) {
			frm.add_custom_button(__("Approve"), () => {
				_trigger_workflow_action(frm, "WD Approve");
			}, __("Workflow")).addClass("btn-success");

			frm.add_custom_button(__("Reject"), () => {
				_trigger_workflow_action(frm, "WD Reject");
			}, __("Workflow"));

			frm.add_custom_button(__("Request Review"), () => {
				_trigger_workflow_action(frm, "WD Request Review");
			}, __("Workflow"));
		}

		// Purchase Manager — SCM sent back for review
		if (state === "WD Review by Purchase Manager" && roles.includes("WD Purchase Manager")) {
			frm.add_custom_button(__("Approve"), () => {
				_trigger_workflow_action(frm, "WD Approve");
			}, __("Workflow")).addClass("btn-success");

			frm.add_custom_button(__("Reject"), () => {
				_trigger_workflow_action(frm, "WD Reject");
			}, __("Workflow"));
		}

		// Supply Chain Manager
		if (state === "WD Pending Supply Chain Manager Approval" && roles.includes("WD Supply Chain Manager")) {
			frm.add_custom_button(__("Approve"), () => {
				_trigger_workflow_action(frm, "WD Approve");
			}, __("Workflow")).addClass("btn-success");

			frm.add_custom_button(__("Reject"), () => {
				_trigger_workflow_action(frm, "WD Reject");
			}, __("Workflow"));

			frm.add_custom_button(__("Request Review"), () => {
				_trigger_workflow_action(frm, "WD Request Review");
			}, __("Workflow"));
		}
	},
});

function _trigger_workflow_action(frm, action) {
	frappe.confirm(
		__("Are you sure you want to: <b>{0}</b>?", [action]),
		() => {
			frappe.dom.freeze(__("Processing..."));
			frappe.call({
				method: "workflow_design.api.workflow_action.apply_action",
				args: {
					doctype: frm.doc.doctype,
					docname: frm.doc.name,
					action: action,
				},
				callback(r) {
					frappe.dom.unfreeze();
					if (r.message) {
						frappe.model.sync(r.message);
						frm.refresh();
						frappe.show_alert({
							message: __("Done: {0}", [action]),
							indicator: "green",
						});
					}
				},
				error() {
					frappe.dom.unfreeze();
				},
			});
		}
	);
}
