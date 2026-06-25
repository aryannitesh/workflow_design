"""Desk bell-icon notification counts for procurement doctypes."""

import frappe


def get_notification_config():
    return {
        "for_doctype": {
            "Material Request":      {"status": "Pending"},
            "Request for Quotation": {"status": "Open"},
            "Purchase Order":        {"per_billed": ["<", 100]},
        }
    }
