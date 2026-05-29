const INJECTION_MOLDING_PURPOSE = "Injection Molding Issuance";
const INJECTION_MOLDING_WEIGHT_FIELDS = [
	"custom_new_material_weight",
	"custom_recycled_material_weight"
];
const CUSTOM_ISSUE_MATERIAL_REQUEST_TYPES = [
	"Material Transfer for Manufacture",
	INJECTION_MOLDING_PURPOSE
];

frappe.ui.form.on("Material Request", {
	setup: function(frm) {
		set_item_detail_queries(frm);
	},

	onload: function(frm) {
		toggle_injection_molding_weight_fields(frm);
	},

	onload_post_render: function(frm) {
		toggle_injection_molding_weight_fields(frm);
	},

	refresh: function(frm) {
		toggle_injection_molding_weight_fields(frm);
		add_custom_issue_stock_entry_button(frm);
	},

	material_request_type: function(frm) {
		toggle_injection_molding_weight_fields(frm);
		add_custom_issue_stock_entry_button(frm);
	}
});

frappe.ui.form.on("Material Request Item", {
	items_add: function(frm) {
		toggle_injection_molding_weight_fields(frm);
	},

	custom_material_request_item_detail_button: function(frm, cdt, cdn) {
		show_material_request_item_details(frm, cdt, cdn);
	}
});

frappe.ui.form.on("MES Material Request Item Detail", {
	material_request_item_idx: function(frm, cdt, cdn) {
		set_item_detail_from_item_row(frm, cdt, cdn);
	}
});

function set_item_detail_queries(frm) {
	frm.set_query("item_code", "custom_item_details", function(doc) {
		const item_codes = (doc.items || [])
			.map(function(row) {
				return row.item_code;
			})
			.filter(Boolean);

		return {
			filters: {
				name: ["in", item_codes.length ? item_codes : [""]]
			}
		};
	});
}

function set_item_detail_from_item_row(frm, cdt, cdn) {
	const detail = locals[cdt][cdn];
	const item_row = (frm.doc.items || []).find(function(row) {
		return cint(row.idx) === cint(detail.material_request_item_idx);
	});

	if (!item_row) {
		frappe.model.set_value(cdt, cdn, "material_request_item", "");
		return;
	}

	frappe.model.set_value(cdt, cdn, {
		item_code: item_row.item_code,
		item_name: item_row.item_name,
		material_request_item: item_row.name
	});
}



function show_material_request_item_details(frm, cdt, cdn) {
	const item_row = locals[cdt][cdn];

	if (!item_row || !item_row.item_code) {
		frappe.msgprint(__("请先选择物料编码"));
		return;
	}

	const details = get_material_request_item_details(frm, item_row);
	const dialog = new frappe.ui.Dialog({
		title: __("物料具体明细 - {0}", [item_row.item_code]),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "details_html"
			}
		]
	});

	dialog.fields_dict.details_html.$wrapper.html(
		get_material_request_item_details_html(item_row, details)
	);
	dialog.show();
}

function get_material_request_item_details(frm, item_row) {
	return (frm.doc.custom_item_details || []).filter(function(detail) {
		return detail.item_code === item_row.item_code;
	});
}

function get_material_request_item_details_html(item_row, details) {
	const total_order_qty = details.reduce(function(total, detail) {
		return total + flt(detail.order_qty);
	}, 0);
	const total_issue_qty = details.reduce(function(total, detail) {
		return total + flt(detail.issue_qty);
	}, 0);

	if (!details.length) {
		return `
			<div class="text-muted">
				${__("当前物料在物料具体明细中没有记录")}
			</div>
		`;
	}

	const rows = details.map(function(detail) {
		return `
			<tr>
				<td>${mes_escape_html(detail.material_request_item_idx || "")}</td>
				<td>${mes_escape_html(detail.item_code || "")}</td>
				<td>${mes_escape_html(detail.item_name || item_row.item_name || "")}</td>
				<td>${mes_escape_html(detail.model || "")}</td>
				<td>${mes_escape_html(detail.color || "")}</td>
				<td class="text-right">${mes_format_detail_qty(detail.order_qty)}</td>
				<td class="text-right">${mes_format_detail_qty(detail.issue_qty)}</td>
				<td>${mes_escape_html(detail.remarks || "")}</td>
			</tr>
		`;
	}).join("");

	return `
		<div class="mb-3">
			<div><strong>${mes_escape_html(item_row.item_code || "")}</strong></div>
			<div class="text-muted">${mes_escape_html(item_row.item_name || "")}</div>
		</div>
		<div class="table-responsive">
			<table class="table table-bordered table-hover">
				<thead>
					<tr>
						<th>${__("明细行号")}</th>
						<th>${__("物料编码")}</th>
						<th>${__("物料名称")}</th>
						<th>${__("型号")}</th>
						<th>${__("颜色")}</th>
						<th class="text-right">${__("订单数量")}</th>
						<th class="text-right">${__("领料量")}</th>
						<th>${__("备注")}</th>
					</tr>
				</thead>
				<tbody>
					${rows}
				</tbody>
				<tfoot>
					<tr>
						<th colspan="5" class="text-right">${__("合计")}</th>
						<th class="text-right">${mes_format_detail_qty(total_order_qty)}</th>
						<th class="text-right">${mes_format_detail_qty(total_issue_qty)}</th>
						<th></th>
					</tr>
				</tfoot>
			</table>
		</div>
	`;
}

function mes_escape_html(value) {
	return frappe.utils.escape_html(cstr(value));
}

function mes_format_detail_qty(value) {
	return format_number(flt(value), null, frappe.defaults.get_default("float_precision"));
}

function add_custom_issue_stock_entry_button(frm) {
	if (
		frm.doc.docstatus !== 1 ||
		frm.doc.status === "Stopped" ||
		!CUSTOM_ISSUE_MATERIAL_REQUEST_TYPES.includes(frm.doc.material_request_type)
	) {
		return;
	}

	const precision = frappe.defaults.get_default("float_precision");

	if (flt(frm.doc.per_ordered, precision) >= 100) {
		return;
	}

	frm.add_custom_button(__("发料"), function() {
		frappe.model.open_mapped_doc({
			method: "mes_integration.mes_integration.material_request.make_issue_stock_entry",
			frm: frm
		});
	}, __("Create"));
	frm.page.set_inner_btn_group_as_primary(__("Create"));
}

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
		["custom_recycled_material_weight", 1],
		["custom_transferred_qty", 1]
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
