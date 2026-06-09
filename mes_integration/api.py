import frappe


@frappe.whitelist()
def create_stock_entry(data=None, stock_entry=None):
    """Short public alias for MES to create a draft Stock Entry."""
    from mes_integration.mes_integration.stock_entry import (
        create_draft_stock_entry_from_mes,
    )

    return create_draft_stock_entry_from_mes(data=data, stock_entry=stock_entry)
