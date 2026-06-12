import frappe


def execute():
	if frappe.db.exists("Custom Field", "Delivery Note-custom_delivery_readiness_status"):
		frappe.db.set_value(
			"Custom Field",
			"Delivery Note-custom_delivery_readiness_status",
			"options",
			"\nPending Release\nReady to Deliver\nDelivered",
			update_modified=False,
		)

	frappe.clear_cache(doctype="Delivery Note")
	backfill_delivered_status()


def backfill_delivered_status():
	if not frappe.db.has_column("Delivery Note", "custom_delivery_readiness_status"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabDelivery Note` dn
		SET dn.custom_delivery_readiness_status = 'Delivered'
		WHERE dn.docstatus = 1
			AND EXISTS (
				SELECT 1
				FROM `tabDelivery Note Item` dni
				WHERE dni.parent = dn.name
					AND IFNULL(dni.against_sales_order, '') != ''
			)
		"""
	)
