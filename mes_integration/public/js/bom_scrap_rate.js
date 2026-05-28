(() => {
	const get_scrap_adjusted_amount = (row) => {
		const custom_scrap_rate = flt(row.custom_scrap_rate);
		if (custom_scrap_rate >= 100) {
			return 0;
		}

		return (flt(row.rate) / (1 - custom_scrap_rate / 100)) * flt(row.qty);
	};

	const calculate_rm_cost = (doc) => {
		const rm = doc.items || [];
		let total_rm_cost = 0;
		let base_total_rm_cost = 0;

		for (const row of rm) {
			const amount = get_scrap_adjusted_amount(row);
			const base_amount = amount * flt(doc.conversion_rate);

			frappe.model.set_value("BOM Item", row.name, {
				base_rate: flt(row.rate) * flt(doc.conversion_rate),
				amount: amount,
				base_amount: base_amount,
				qty_consumed_per_unit: flt(row.stock_qty) / flt(doc.quantity),
			});

			total_rm_cost += amount;
			base_total_rm_cost += base_amount;
		}

		cur_frm.set_value("raw_material_cost", total_rm_cost);
		cur_frm.set_value("base_raw_material_cost", base_total_rm_cost);
	};

	const calculate_total = (frm) => {
		if (!window.erpnext?.bom) {
			return;
		}

		erpnext.bom.calculate_rm_cost(frm.doc);
		erpnext.bom.calculate_total(frm.doc);
	};

	if (window.erpnext?.bom) {
		erpnext.bom.calculate_rm_cost = calculate_rm_cost;
	}

	frappe.ui.form.on("BOM", {
		refresh(frm) {
			calculate_total(frm);
		},
	});

	frappe.ui.form.on("BOM Item", {
		custom_scrap_rate: calculate_total,
		rate: calculate_total,
		qty: calculate_total,
	});
})();
