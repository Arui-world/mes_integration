import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Material Request": [
				{
					"fieldname": "custom_item_details",
					"fieldtype": "Table",
					"insert_after": "items",
					"label": "物料具体明细",
					"options": "MES Material Request Item Detail",
				}
			]
		},
		update=True,
	)

	frappe.clear_cache(doctype="Material Request")
