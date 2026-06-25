// WD Procurement KPI — filter definitions
frappe.query_reports["WD Procurement KPI"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
            default: frappe.defaults.get_user_default("Company"),
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today(),
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Highlight KPI values: green if within target, amber/red if over
        if (column.fieldname === "mr_to_rfq_days" && data) {
            const v = parseFloat(data.mr_to_rfq_days) || 0;
            if (v > 0 && v <= 3)       value = `<span style="color:green;font-weight:bold">${value}</span>`;
            else if (v > 3 && v <= 7)  value = `<span style="color:#d97706;font-weight:bold">${value}</span>`;
            else if (v > 7)            value = `<span style="color:red;font-weight:bold">${value}</span>`;
        }

        if (column.fieldname === "mr_to_po_days" && data) {
            const v = parseFloat(data.mr_to_po_days) || 0;
            if (v > 0 && v <= 14)      value = `<span style="color:green;font-weight:bold">${value}</span>`;
            else if (v > 14 && v <= 30) value = `<span style="color:#d97706;font-weight:bold">${value}</span>`;
            else if (v > 30)            value = `<span style="color:red;font-weight:bold">${value}</span>`;
        }

        if (column.fieldname === "rfq_to_po_days" && data) {
            const v = parseFloat(data.rfq_to_po_days) || 0;
            if (v > 0 && v <= 10)      value = `<span style="color:green;font-weight:bold">${value}</span>`;
            else if (v > 10 && v <= 21) value = `<span style="color:#d97706;font-weight:bold">${value}</span>`;
            else if (v > 21)            value = `<span style="color:red;font-weight:bold">${value}</span>`;
        }

        return value;
    },
};
