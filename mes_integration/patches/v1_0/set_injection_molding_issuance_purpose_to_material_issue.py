import frappe


STOCK_ENTRY_TYPE_NAME = "Injection Molding Issuance"
BASE_PURPOSE = "Material Issue"


def execute():
    if frappe.db.exists("Stock Entry Type", STOCK_ENTRY_TYPE_NAME):
        current_purpose = frappe.db.get_value("Stock Entry Type", STOCK_ENTRY_TYPE_NAME, "purpose")
        if current_purpose != BASE_PURPOSE:
            frappe.db.set_value(
                "Stock Entry Type",
                STOCK_ENTRY_TYPE_NAME,
                "purpose",
                BASE_PURPOSE,
                update_modified=False,
            )
    else:
        frappe.get_doc(
            {
                "doctype": "Stock Entry Type",
                "name": STOCK_ENTRY_TYPE_NAME,
                "purpose": BASE_PURPOSE,
            }
        ).insert(ignore_permissions=True)

    frappe.clear_cache(doctype="Stock Entry Type")
    frappe.clear_cache(doctype="Stock Entry")
