const INJECTION_MOLDING_PURPOSE = "Injection Molding Issuance";
const INJECTION_MOLDING_WEIGHT_FIELDS = [
	"custom_new_material_weight",
	"custom_recycled_material_weight"
];

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

	if (frm.doc.material_request_type === INJECTION_MOLDING_PURPOSE) {
		apply_injection_molding_item_grid(grid);
	} else {
		restore_material_request_item_grid(grid);
		hide_injection_molding_weight_fields(grid);
	}

	rebuild_material_request_item_grid(grid);
}

function apply_injection_molding_item_grid(grid) {
	const injection_columns = [
		["item_code", 2],
		["schedule_date", 2],
		["qty", 1],
		["warehouse", 2],
		["uom", 1],
		["projected_qty", 1],
		["custom_new_material_weight", 1],
		["custom_recycled_material_weight", 1]
	];
	const injection_fieldnames = injection_columns.map(function(column) {
		return column[0];
	});

	grid.docfields.forEach(function(df) {
		if (!df.fieldname || !injection_fieldnames.includes(df.fieldname)) {
			return;
		}

		set_material_request_item_docfield_property(grid, df.fieldname, "hidden", 0);
		set_material_request_item_docfield_property(grid, df.fieldname, "in_list_view", 1);
	});

	grid.visible_columns = injection_columns
		.map(function(column) {
			const df = grid.docfields.find(function(docfield) {
				return docfield.fieldname === column[0] && !docfield.hidden;
			});

			if (!df) {
				return null;
			}

			set_material_request_item_docfield_property(grid, df.fieldname, "columns", column[1]);
			set_material_request_item_docfield_property(grid, df.fieldname, "colsize", column[1]);

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

		set_material_request_item_docfield_property(grid, df.fieldname, "hidden", defaults.hidden);
		set_material_request_item_docfield_property(grid, df.fieldname, "in_list_view", defaults.in_list_view);
		set_material_request_item_docfield_property(grid, df.fieldname, "columns", defaults.columns);
		set_material_request_item_docfield_property(grid, df.fieldname, "colsize", defaults.colsize);
	});

	grid.visible_columns = [];
	grid.user_defined_columns = [];
}

function hide_injection_molding_weight_fields(grid) {
	INJECTION_MOLDING_WEIGHT_FIELDS.forEach(function(fieldname) {
		set_material_request_item_docfield_property(grid, fieldname, "hidden", 1);
		set_material_request_item_docfield_property(grid, fieldname, "in_list_view", 0);
		set_material_request_item_docfield_property(grid, fieldname, "columns", undefined);
		set_material_request_item_docfield_property(grid, fieldname, "colsize", undefined);
	});
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

function set_material_request_item_docfield_property(grid, fieldname, property, value) {
	const grid_docfield = grid.docfields.find(function(df) {
		return df.fieldname === fieldname;
	});

	if (grid_docfield) {
		grid_docfield[property] = value;
	}

	const meta_docfield = frappe.meta.get_docfield("Material Request Item", fieldname);

	if (meta_docfield) {
		meta_docfield[property] = value;
	}

	(grid.grid_rows || []).forEach(function(row) {
		const row_docfield = row.docfields && row.docfields.find(function(df) {
			return df.fieldname === fieldname;
		});

		if (row_docfield) {
			row_docfield[property] = value;
		}
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
