import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Material Request Item": [
				{
					"fieldname": "custom_material_request_item_detail_button",
					"fieldtype": "Button",
					"insert_after": "custom_transferred_qty",
					"label": "物料具体明细",
					"in_list_view": 1,
					"columns": 1,
					"no_copy": 1,
				}
			]
		},
		update=True,
	)

	frappe.clear_cache(doctype="Material Request Item")
