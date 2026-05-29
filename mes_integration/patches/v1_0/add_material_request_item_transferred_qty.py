import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Material Request Item": [
				{
					"fieldname": "custom_transferred_qty",
					"fieldtype": "Float",
					"insert_after": "ordered_qty",
					"label": "已发料数量",
					"read_only": 1,
					"no_copy": 1,
				}
			]
		},
		update=True,
	)

	frappe.clear_cache(doctype="Material Request Item")
