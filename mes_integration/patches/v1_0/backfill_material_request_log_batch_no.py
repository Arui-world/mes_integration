import frappe


def execute():
	if not frappe.db.table_exists("MES Integration Log"):
		return

	if not frappe.db.has_column("MES Integration Log", "batch_no"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabMES Integration Log` log
		INNER JOIN `tabMaterial Request` mr ON mr.name = log.reference_name
		SET log.batch_no = mr.custom_stock_entry_no
		WHERE log.reference_doctype = 'Material Request'
			AND IFNULL(log.batch_no, '') = ''
			AND IFNULL(mr.custom_stock_entry_no, '') != ''
		"""
	)
