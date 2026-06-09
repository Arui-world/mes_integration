frappe.ui.form.on("Stock Entry", {
	onload: function(frm) {
		remember_mes_receipt_stock_entry_no(frm);
		show_mes_receipt_stock_entry_no(frm);
		add_push_to_mes_button(frm);
		display_mes_status(frm);
	},

	refresh: function(frm) {
		sync_mes_stock_entry_fields(frm);
		add_stock_entry_save_and_submit_button(frm);
		add_push_to_mes_button(frm);
		display_mes_status(frm);
	},

	stock_entry_type: function(frm) {
		clear_manual_mes_receipt_stock_entry_no(frm);
		sync_mes_stock_entry_fields(frm);
	},

	validate: function(frm) {
		sync_mes_stock_entry_fields(frm, { immediate: true });
	},

	items_add: function(frm, cdt, cdn) {
		set_manufacturing_warehouse(frm, cdt, cdn);
	},

	after_save: function(frm) {
		if (frm.doc.custom_mes_status === "Pushed") {
			frappe.call({
				method: "mes_integration.mes_integration.stock_entry.reset_mes_status",
				args: {
					stock_entry_name: frm.doc.name
				},
				freeze: false,
				callback: function(r) {
					if (r.message && r.message.status === "success") {
						frm.reload_doc();
					}
				}
			});
		}
	}
});

const MES_RECEIPT_STOCK_ENTRY_TYPES = [
	"Semi Finished Goods Receipt",
	"Finished Goods Receipt"
];

function is_mes_receipt_stock_entry(frm) {
	return frm && frm.doc && MES_RECEIPT_STOCK_ENTRY_TYPES.includes(frm.doc.stock_entry_type);
}

function add_stock_entry_save_and_submit_button(frm) {
	frm.remove_custom_button(__("保存并提交"));

	if (!frm || !frm.doc || frm.doc.docstatus !== 0 || has_stock_entry_submit_button(frm)) {
		return;
	}

	frm._mes_save_submit_button = frm.add_custom_button(__("保存并提交"), function() {
		save_and_submit_stock_entry(frm);
	});
	apply_stock_entry_save_and_submit_button_style(frm);
}

function has_stock_entry_submit_button(frm) {
	const labels = [...new Set(["Submit", __("Submit"), "提交", __("提交")])];
	return labels.some(function(label) {
		return $(frm.page.wrapper)
			.find(`.page-actions button[data-label="${encodeURIComponent(label)}"]`)
			.length > 0;
	});
}

function save_and_submit_stock_entry(frm) {
	frappe.confirm(
		__("确认保存并提交此物料移动？"),
		function() {
			frm.save("Submit");
		}
	);
}

function apply_stock_entry_save_and_submit_button_style(frm) {
	requestAnimationFrame(function() {
		const labels = [...new Set(["保存并提交", __("保存并提交")])];
		const selector = labels
			.map(function(label) {
				return `.page-actions button[data-label="${encodeURIComponent(label)}"]`;
			})
			.join(", ");

		$(frm.page.wrapper)
			.find(selector)
			.removeClass("btn-default btn-secondary btn-xs")
			.addClass("btn-primary btn-sm mes-save-submit-button");
	});
}

function remember_mes_receipt_stock_entry_no(frm) {
	if (!is_mes_receipt_stock_entry(frm) || frm.is_new() || !frm.doc.custom_stock_entry_no) {
		return;
	}

	frm._mes_receipt_stock_entry_no = frm.doc.custom_stock_entry_no;
}

function clear_manual_mes_receipt_stock_entry_no(frm) {
	if (!is_mes_receipt_stock_entry(frm) || !frm.is_new()) {
		return;
	}

	frm._mes_receipt_stock_entry_no = "";
	if (frm.doc.custom_stock_entry_no) {
		frappe.model.set_value(frm.doctype, frm.docname, "custom_stock_entry_no", "");
	}
}

function restore_mes_receipt_stock_entry_no(frm, immediate) {
	if (!is_mes_receipt_stock_entry(frm) || !frm._mes_receipt_stock_entry_no) {
		return;
	}

	const restore = function() {
		if (!frm.doc.custom_stock_entry_no) {
			frappe.model.set_value(
				frm.doctype,
				frm.docname,
				"custom_stock_entry_no",
				frm._mes_receipt_stock_entry_no
			);
		}
	};

	if (immediate) {
		restore();
		return;
	}

	setTimeout(restore, 100);
}

function show_mes_receipt_stock_entry_no(frm) {
	if (!is_mes_receipt_stock_entry(frm)) {
		return;
	}

	frm.toggle_display("custom_stock_entry_no", true);
	frm.set_df_property("custom_stock_entry_no", "hidden", 0);
	frm.refresh_field("custom_stock_entry_no");
}

const MES_MANUFACTURING_TARGET_WAREHOUSE = "Manufacturing - YC";

frappe.ui.form.on("Stock Entry Detail", {
	material_request: function(frm, cdt, cdn) {
		set_manufacturing_warehouse(frm, cdt, cdn);
		sync_mes_stock_entry_fields(frm);
	},

	material_request_item: function(frm, cdt, cdn) {
		set_manufacturing_warehouse(frm, cdt, cdn);
		sync_mes_stock_entry_fields(frm);
	},

	custom_material_request_no: function(frm) {
		sync_material_request_no(frm);
	}
});

function sync_mes_stock_entry_fields(frm, options) {
	options = options || {};
	clear_manual_mes_receipt_stock_entry_no(frm);
	remember_mes_receipt_stock_entry_no(frm);
	show_mes_receipt_stock_entry_no(frm);
	restore_mes_receipt_stock_entry_no(frm, options.immediate);
	sync_material_request_no(frm);
	sync_stock_entry_no_from_material_request(frm);
	schedule_all_manufacturing_warehouses(frm);
}

function sync_material_request_no(frm) {
	if (is_mes_receipt_stock_entry(frm)) {
		return;
	}

	const firstRow = get_first_stock_entry_item(frm);
	const materialRequestNo = firstRow ? firstRow.custom_material_request_no || "" : "";
	set_form_value_if_changed(frm, "custom_material_request_no", materialRequestNo);
}

function sync_stock_entry_no_from_material_request(frm) {
	if (is_mes_receipt_stock_entry(frm)) {
		return;
	}

	const firstRow = get_first_stock_entry_item(frm);
	const materialRequest = firstRow && firstRow.material_request;

	if (!materialRequest) {
		set_form_value_if_changed(frm, "custom_stock_entry_no", "");
		return;
	}

	frappe.db.get_value("Material Request", materialRequest, "custom_stock_entry_no").then(function(r) {
		const stockEntryNo = r && r.message ? r.message.custom_stock_entry_no || "" : "";
		set_form_value_if_changed(frm, "custom_stock_entry_no", stockEntryNo);
	});
}

function get_first_stock_entry_item(frm) {
	return frm.doc.items && frm.doc.items.length ? frm.doc.items[0] : null;
}

function set_form_value_if_changed(frm, fieldname, value) {
	if (frm.doc[fieldname] === value) {
		return;
	}

	frm.set_value(fieldname, value);
}

function set_manufacturing_warehouse(frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];

	if (!row || frm.doc.purpose !== "Material Transfer for Manufacture") {
		return;
	}

	if ((row.material_request || row.material_request_item) && row.t_warehouse !== MES_MANUFACTURING_TARGET_WAREHOUSE) {
		frappe.model.set_value(cdt, cdn, "t_warehouse", MES_MANUFACTURING_TARGET_WAREHOUSE);
	}
}

function schedule_all_manufacturing_warehouses(frm) {
	if (frm.doc.purpose !== "Material Transfer for Manufacture") {
		return;
	}

	setTimeout(function() {
		set_all_manufacturing_warehouses(frm);
	}, 300);
}

function set_all_manufacturing_warehouses(frm) {
	if (frm.doc.purpose !== "Material Transfer for Manufacture") {
		return;
	}

	(frm.doc.items || []).forEach(function(row) {
		if ((row.material_request || row.material_request_item) && row.t_warehouse !== MES_MANUFACTURING_TARGET_WAREHOUSE) {
			frappe.model.set_value(row.doctype, row.name, "t_warehouse", MES_MANUFACTURING_TARGET_WAREHOUSE);
		}
	});
}

$(document).ready(function() {
	$('.mes-status-badge').remove();
});

$(document).on('page-change', function() {
	$('.mes-status-badge').remove();
});

function display_mes_status(frm) {
	var currentUrl = window.location.pathname;

	if (!currentUrl || currentUrl === '/desk/stock-entry') {
		$('.mes-status-badge').remove();
		return;
	}

	if (!frm || frm.doctype !== 'Stock Entry' || !frm.doc || !frm.doc.name) {
		return;
	}

	if (is_mes_receipt_stock_entry(frm)) {
		$('.mes-status-badge').remove();
		return;
	}

	var $pageHead = $('.page-head');
	if (!$pageHead.length) {
		return;
	}

	var mesStatus = frm.doc.custom_mes_status || "Unpushed";

	$('.mes-status-badge').remove();

	var statusHtml = '';

	if (mesStatus === "Pushed") {
		statusHtml = '<span class="mes-status-badge indicator-pill no-indicator-dot whitespace-nowrap blue"><span>' + get_dlm_status_label(true) + '</span></span>';
	} else {
		statusHtml = '<span class="mes-status-badge indicator-pill no-indicator-dot whitespace-nowrap red"><span>' + get_dlm_status_label(false) + '</span></span>';
	}

	var $titleArea = $pageHead.find('.title-area').first();
	var $statusIndicator = $titleArea.find('.indicator-pill').not('.mes-status-badge').last();

	if ($statusIndicator.length) {
		$statusIndicator.after(statusHtml);
	} else if ($titleArea.length) {
		$titleArea.append(statusHtml);
	} else {
		$pageHead.append(statusHtml);
	}
}

function get_dlm_status_label(is_pushed) {
	const lang = (frappe.boot && frappe.boot.lang) || frappe.lang || '';
	if (lang.toLowerCase().startsWith('es')) {
		return is_pushed ? 'DLM: Enviado' : 'DLM: No enviado';
	}

	return is_pushed ? __('DLM: 已推送') : __('DLM: 未推送');
}

function add_push_to_mes_button(frm) {
	frm.remove_custom_button(__("推送至MES"), __("MES操作"));
	frm.remove_custom_button(__("推送至DLM"));

	if (is_mes_receipt_stock_entry(frm)) {
		return;
	}

	if (frm.doc.docstatus === 1 && frm.doc.custom_stock_entry_no) {
		frm._mes_push_button = frm.add_custom_button(__("推送至DLM"), function() {
			push_stock_entry_to_mes(frm);
		});

		apply_mes_button_style(frm);
	}
}

function apply_mes_button_style(frm) {
	requestAnimationFrame(function() {
		const $btn = frm && frm._mes_push_button ? frm._mes_push_button : $('[data-label="' + __("推送至DLM") + '"]');
		$btn.addClass('mes-push-dlm-button btn-primary')
			.removeClass('btn-default btn-light');
	});
}

function push_stock_entry_to_mes(frm) {
	const $btn = frm._mes_push_button || $('.mes-push-dlm-button');
	$btn.prop("disabled", true);

	frappe.call({
		method: "mes_integration.mes_integration.stock_entry.push_to_mes",
		args: {
			stock_entry_name: frm.doc.name
		},
		freeze: true,
		freeze_message: __("正在推送至 DLM，请稍候..."),
		callback: function(r) {
			$btn.prop("disabled", false);

			if (r.exc) {
				show_mes_push_error(r);
				return;
			}

			if (r.message && r.message.status === "success") {
				frappe.msgprint({
					title: __("成功"),
					indicator: "green",
					message: r.message.message
				});

				frm.reload_doc();
				frm.refresh_fields();
				return;
			}

			frappe.msgprint({
				title: __("提示"),
				indicator: "orange",
				message: __("DLM 推送已返回，但没有收到成功结果，请查看 Error Log 或浏览器控制台。")
			});
		},
		error: function(r) {
			$btn.prop("disabled", false);
			show_mes_push_error(r);
		}
	});
}

function show_mes_push_error(r) {
	let message = __("推送至 DLM 失败，请查看 Error Log。");

	if (r && r._server_messages) {
		try {
			const serverMessages = JSON.parse(r._server_messages);
			message = serverMessages.map(function(item) {
				return JSON.parse(item).message;
			}).join("<br>");
		} catch (e) {
			message = r._server_messages;
		}
	} else if (r && r.message) {
		message = r.message;
	} else if (r && r.responseJSON && r.responseJSON.message) {
		message = r.responseJSON.message;
	}

	frappe.msgprint({
		title: __("错误"),
		indicator: "red",
		message: message
	});
}

const MES_MATERIAL_REQUEST_TYPES_FOR_STOCK_ENTRY = [
	"Material Transfer",
	"Material Issue",
	"Customer Provided",
	"Material Transfer for Manufacture",
	"Injection Molding Issuance"
];

frappe.ui.form.on("Stock Entry", {
	refresh: function(frm) {
		replace_material_request_button(frm);
	}
});

function replace_material_request_button(frm) {
	if (frm.doc.docstatus !== 0 || frm.doc.subcontracting_inward_order) {
		return;
	}

	frm.remove_custom_button(__("Material Request"), __("Get Items From"));
	frm.add_custom_button(__("Material Request"), function() {
		open_material_request_mapper(frm);
	}, __("Get Items From"));
}

function open_material_request_mapper(frm) {
	const depends_on_condition = "eval:doc.material_request_type==='Customer Provided'";
	const d = erpnext.utils.map_current_doc({
		method: "mes_integration.mes_integration.material_request.make_stock_entry_from_material_request",
		source_doctype: "Material Request",
		target: frm,
		date_field: "schedule_date",
		setters: [
			{
				fieldtype: "Select",
				label: __("Purpose"),
				options: MES_MATERIAL_REQUEST_TYPES_FOR_STOCK_ENTRY.join("\n"),
				fieldname: "material_request_type",
				default: frm.doc.purpose === "Material Issue" ? "Material Issue" : "Material Transfer",
				mandatory: 1,
				change() {
					if (this.value === "Customer Provided") {
						d.dialog.get_field("customer").set_focus();
					}
				},
			},
			{
				fieldtype: "Link",
				label: __("Customer"),
				options: "Customer",
				fieldname: "customer",
				depends_on: depends_on_condition,
				mandatory_depends_on: depends_on_condition,
			},
		],
		get_query_filters: {
			docstatus: 1,
			material_request_type: ["in", MES_MATERIAL_REQUEST_TYPES_FOR_STOCK_ENTRY],
			status: ["not in", ["Transferred", "Issued", "Cancelled", "Stopped"]],
		},
	});
}
