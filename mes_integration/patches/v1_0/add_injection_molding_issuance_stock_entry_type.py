import frappe


STOCK_ENTRY_TYPE_NAME = "Injection Molding Issuance"
BASE_PURPOSE = "Material Transfer for Manufacture"


def execute():
    ensure_injection_molding_issuance_stock_entry_type()
    frappe.clear_cache(doctype="Stock Entry Type")
    frappe.clear_cache(doctype="Stock Entry")


def ensure_injection_molding_issuance_stock_entry_type():
    if frappe.db.exists("Stock Entry Type", STOCK_ENTRY_TYPE_NAME):
        stock_entry_type = frappe.get_doc("Stock Entry Type", STOCK_ENTRY_TYPE_NAME)
        if stock_entry_type.purpose != BASE_PURPOSE:
            stock_entry_type.purpose = BASE_PURPOSE
            stock_entry_type.save(ignore_permissions=True)
        return

    frappe.get_doc(
        {
            "doctype": "Stock Entry Type",
            "name": STOCK_ENTRY_TYPE_NAME,
            "purpose": BASE_PURPOSE,
        }
    ).insert(ignore_permissions=True)
