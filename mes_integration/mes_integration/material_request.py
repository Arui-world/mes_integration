import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt


CUSTOM_ISSUE_MATERIAL_REQUEST_TYPES = (
    "Material Transfer for Manufacture",
    "Injection Molding Issuance",
)
STOCK_ENTRY_PURPOSE = "Material Transfer for Manufacture"


@frappe.whitelist()
def make_issue_stock_entry(source_name, target_doc=None):
    def update_item(source, target, source_parent):
        qty = (
            flt(flt(source.stock_qty) - flt(source.ordered_qty)) / target.conversion_factor
            if flt(source.stock_qty) > flt(source.ordered_qty)
            else 0
        )
        target.qty = qty
        target.transfer_qty = qty * source.conversion_factor
        target.conversion_factor = source.conversion_factor
        target.s_warehouse = (
            source.get("from_warehouse")
            or source_parent.get("set_from_warehouse")
            or source.get("warehouse")
        )
        target.t_warehouse = source_parent.get("set_warehouse") or source.get("warehouse")

    def set_missing_values(source, target):
        target.purpose = STOCK_ENTRY_PURPOSE
        target.stock_entry_type = STOCK_ENTRY_PURPOSE
        target.from_warehouse = source.get("set_from_warehouse")
        target.to_warehouse = source.get("set_warehouse")
        target.set_transfer_qty()
        target.set_actual_qty()
        target.calculate_rate_and_amount(raise_error_if_no_rate=False)
        target.set_job_card_data()

    return get_mapped_doc(
        "Material Request",
        source_name,
        {
            "Material Request": {
                "doctype": "Stock Entry",
                "validation": {
                    "docstatus": ["=", 1],
                    "material_request_type": ["in", CUSTOM_ISSUE_MATERIAL_REQUEST_TYPES],
                },
            },
            "Material Request Item": {
                "doctype": "Stock Entry Detail",
                "field_map": {
                    "name": "material_request_item",
                    "parent": "material_request",
                    "uom": "stock_uom",
                    "job_card_item": "job_card_item",
                },
                "field_no_map": ["expense_account"],
                "postprocess": update_item,
                "condition": lambda doc: (
                    flt(doc.ordered_qty, doc.precision("ordered_qty"))
                    < flt(doc.stock_qty, doc.precision("ordered_qty"))
                ),
            },
        },
        target_doc,
        set_missing_values,
    )
