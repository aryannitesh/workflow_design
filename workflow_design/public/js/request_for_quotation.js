// Desk customisation for Request for Quotation
// Adds an "Evaluate Quotations" button when the RFQ is submitted
// and at least one Supplier Quotation has been received.

frappe.ui.form.on("Request for Quotation", {
    refresh(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status !== "Cancelled") {
            frm.add_custom_button(
                __("Evaluate Quotations"),
                () => _run_evaluation(frm),
                __("Actions")
            );
        }
    },
});

function _run_evaluation(frm) {
    frappe.confirm(
        __("Run automatic evaluation for all submitted Supplier Quotations linked to this RFQ?"),
        () => {
            frappe.show_progress(__("Evaluating..."), 0, 100, __("Please wait"));

            frappe.call({
                method: "workflow_design.api.sq_evaluation.run_evaluation",
                args: { rfq_name: frm.doc.name },
                callback(r) {
                    frappe.hide_progress();
                    if (r.exc || !r.message) return;
                    _show_result_dialog(frm, r.message);
                },
                error() {
                    frappe.hide_progress();
                },
            });
        }
    );
}

function _show_result_dialog(frm, results) {
    const winner = results.find(r => r.status === "Approved");

    let rows = results.map(r => `
        <tr style="background:${r.status === 'Approved' ? '#f0fff4' : '#fff'}">
            <td style="padding:6px 10px;border:1px solid #ddd">${r.rank}</td>
            <td style="padding:6px 10px;border:1px solid #ddd">
                <a href="/app/supplier-quotation/${r.name}">${r.name}</a>
            </td>
            <td style="padding:6px 10px;border:1px solid #ddd">${r.supplier}</td>
            <td style="padding:6px 10px;border:1px solid #ddd;text-align:right">
                ${format_currency(r.grand_total, frm.doc.currency)}
            </td>
            <td style="padding:6px 10px;border:1px solid #ddd;text-align:right">${r.delivery_days}</td>
            <td style="padding:6px 10px;border:1px solid #ddd;text-align:right">${r.payment_days}</td>
            <td style="padding:6px 10px;border:1px solid #ddd;text-align:right">${r.total_score}</td>
            <td style="padding:6px 10px;border:1px solid #ddd;text-align:center;font-weight:bold;
                        color:${r.status === 'Approved' ? '#16a34a' : '#dc2626'}">
                ${r.status === 'Approved' ? '✔ Approved' : '✘ Rejected'}
            </td>
        </tr>`
    ).join("");

    const html = `
        <p>${winner
            ? `<strong>${winner.supplier}</strong> (${winner.name}) has been selected as the best quotation.`
            : "Evaluation complete."
        }</p>
        <div style="overflow-x:auto">
        <table style="border-collapse:collapse;width:100%;font-size:13px">
            <thead>
                <tr style="background:#f5f5f5">
                    <th style="padding:6px 10px;border:1px solid #ddd">#</th>
                    <th style="padding:6px 10px;border:1px solid #ddd">Quotation</th>
                    <th style="padding:6px 10px;border:1px solid #ddd">Supplier</th>
                    <th style="padding:6px 10px;border:1px solid #ddd;text-align:right">Grand Total</th>
                    <th style="padding:6px 10px;border:1px solid #ddd;text-align:right">Del. Days</th>
                    <th style="padding:6px 10px;border:1px solid #ddd;text-align:right">Pay. Days</th>
                    <th style="padding:6px 10px;border:1px solid #ddd;text-align:right">Score</th>
                    <th style="padding:6px 10px;border:1px solid #ddd;text-align:center">Result</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
        </div>
        <p class="text-muted" style="font-size:11px;margin-top:8px">
            Weights — Rate: 40% | Delivery Days: 30% | Payment Days: 30%
        </p>`;

    frappe.msgprint({
        title: __("Evaluation Results — {0}", [frm.doc.name]),
        message: html,
        wide: true,
    });

    frm.reload_doc();
}
