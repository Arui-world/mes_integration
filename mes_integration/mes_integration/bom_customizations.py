import frappe
from frappe import _
from frappe.utils import flt


def validate_custom_scrap_rate(doc, method=None):
	for row in doc.get("items"):
		custom_scrap_rate = flt(row.get("custom_scrap_rate"))
		if custom_scrap_rate >= 100:
			frappe.throw(
				_("Row {0}: Scrap Rate must be less than 100.").format(row.idx),
				title=_("Invalid Scrap Rate"),
			)


class BOMScrapRateMixin:
	def calculate_rm_cost(self, save=False):
		"""Calculate raw material cost with BOM Item custom_scrap_rate."""

		total_rm_cost = 0
		base_total_rm_cost = 0

		for row in self.get("items"):
			old_rate = row.rate
			if not self.bom_creator and (row.is_stock_item or row.is_phantom_item):
				row.rate = self.get_rm_rate(
					{
						"company": self.company,
						"item_code": row.item_code,
						"bom_no": row.bom_no,
						"qty": row.qty,
						"uom": row.uom,
						"stock_uom": row.stock_uom,
						"conversion_factor": row.conversion_factor,
						"sourced_by_supplier": row.sourced_by_supplier,
						"is_phantom_item": row.is_phantom_item,
					},
					notify=False,
				)

			custom_scrap_rate = flt(row.get("custom_scrap_rate"))
			if custom_scrap_rate >= 100:
				frappe.throw(
					_("Row {0}: Scrap Rate must be less than 100.").format(row.idx),
					title=_("Invalid Scrap Rate"),
				)

			row.base_rate = flt(row.rate) * flt(self.conversion_rate)
			row.amount = flt(
				flt(row.rate, row.precision("rate"))
				/ (1 - custom_scrap_rate / 100)
				* flt(row.qty, row.precision("qty")),
				row.precision("amount"),
			)
			row.base_amount = row.amount * flt(self.conversion_rate)
			row.qty_consumed_per_unit = flt(row.stock_qty, row.precision("stock_qty")) / flt(
				self.quantity, self.precision("quantity")
			)

			total_rm_cost += row.amount
			base_total_rm_cost += row.base_amount
			if save and old_rate != row.rate:
				row.db_update()

		self.raw_material_cost = total_rm_cost
		self.base_raw_material_cost = base_total_rm_cost
