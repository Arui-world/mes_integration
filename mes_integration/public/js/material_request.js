frappe.ui.form.on("Material Request", {
	onload: function(frm) {
		toggle_injection_molding_weight_fields(frm);
	},

	onload_post_render: function(frm) {
		toggle_injection_molding_weight_fields(frm);
	},

	refresh: function(frm) {
		toggle_injection_molding_weight_fields(frm);
	},

	material_request_type: function(frm) {
		toggle_injection_molding_weight_fields(frm);
	}
});

frappe.ui.form.on("Material Request Item", {
	items_add: function(frm) {
		toggle_injection_molding_weight_fields(frm);
	}
});

function toggle_injection_molding_weight_fields(frm) {
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;

	if (!grid) {
		return;
	}

	ensure_material_request_item_grid_defaults(grid);

	if (frm.doc.material_request_type === "Injection Molding Issuance") {
		apply_injection_molding_item_grid(grid);
	} else {
		restore_material_request_item_grid(grid);
	}

	rebuild_material_request_item_grid(grid);
}

function apply_injection_molding_item_grid(grid) {
	const injection_columns = [
		["item_code", 2],
		["schedule_date", 1],
		["qty", 1],
		["warehouse", 1],
		["uom", 1],
		["custom_new_material_weight", 2],
		["custom_recycled_material_weight", 2]
	];
	const injection_fieldnames = injection_columns.map(function(column) {
		return column[0];
	});

	grid.docfields.forEach(function(df) {
		if (!df.fieldname) {
			return;
		}

		if (df.fieldname === "projected_qty") {
			df.hidden = 1;
			df.in_list_view = 0;
			return;
		}

		if (injection_fieldnames.includes(df.fieldname)) {
			df.hidden = 0;
			df.in_list_view = 1;
		}
	});

	grid.visible_columns = injection_columns
		.map(function(column) {
			const df = grid.docfields.find(function(docfield) {
				return docfield.fieldname === column[0] && !docfield.hidden;
			});

			if (!df) {
				return null;
			}

			df.columns = column[1];
			df.colsize = column[1];

			return [df, column[1]];
		})
		.filter(Boolean);
	grid.user_defined_columns = [];
}

function restore_material_request_item_grid(grid) {
	grid.docfields.forEach(function(df) {
		const defaults = grid.__mes_default_docfield_properties[df.fieldname];

		if (!defaults) {
			return;
		}

		df.hidden = defaults.hidden;
		df.in_list_view = defaults.in_list_view;
		df.columns = defaults.columns;
		df.colsize = defaults.colsize;
	});

	grid.visible_columns = [];
	grid.user_defined_columns = [];
}

function ensure_material_request_item_grid_defaults(grid) {
	if (grid.__mes_default_docfield_properties) {
		return;
	}

	grid.__mes_default_docfield_properties = {};

	grid.docfields.forEach(function(df) {
		if (!df.fieldname) {
			return;
		}

		grid.__mes_default_docfield_properties[df.fieldname] = {
			hidden: df.hidden,
			in_list_view: df.in_list_view,
			columns: df.columns,
			colsize: df.colsize
		};
	});
}

function rebuild_material_request_item_grid(grid) {
	if (grid.grid_rows) {
		grid.grid_rows.forEach(function(row) {
			if (row && row.get_open_form && row.get_open_form()) {
				row.hide_form();
			}
		});
	}

	grid.grid_rows = [];
	grid.grid_rows_by_docname = {};
	grid.wrapper.find(".grid-body .rows .grid-row").remove();
	grid.refresh();
}
