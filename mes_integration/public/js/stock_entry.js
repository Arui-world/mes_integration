frappe.ui.form.on("Stock Entry", {
	onload: function(frm) {
		add_push_to_mes_button(frm);
		display_mes_status(frm);
	},

	refresh: function(frm) {
		add_push_to_mes_button(frm);
		display_mes_status(frm);
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

	var $pageTitle = $('.page-title');
	if (!$pageTitle.length) {
		return;
	}

	var mesStatus = frm.doc.custom_mes_status || "Unpushed";

	$('.mes-status-badge').remove();

	var statusHtml = '';

	if (mesStatus === "Pushed") {
		statusHtml = '<span class="mes-status-badge indicator-pill no-indicator-dot whitespace-nowrap blue" style="margin-left: 12px;"><span>MES: 已推送</span></span>';
	} else {
		statusHtml = '<span class="mes-status-badge indicator-pill no-indicator-dot whitespace-nowrap red" style="margin-left: 12px;"><span>MES: 未推送</span></span>';
	}

	var $pageHead = $('.page-head');
	if ($pageHead.length) {
		var $target = $pageHead.find('.page-title').length ? $pageHead.find('.page-title') : $pageHead;
		$target.append(statusHtml);
	}
}

function add_push_to_mes_button(frm) {
	if (frm.doc.docstatus === 1) {
		if (!frm.custom_buttons["推送至MES"]) {
			frm._mes_push_button = frm.add_custom_button(__("推送至MES"), function() {
				push_stock_entry_to_mes(frm);
			}, __("MES操作"));

			apply_mes_button_style();
		}
	}
}

function apply_mes_button_style() {
	requestAnimationFrame(function() {
		let $btns = $('.page-head').find('button');

		$btns.each(function() {
			const $this = $(this);
			const text = $this.text().trim();

			if (text === 'MES操作') {
				$this.attr('style', 'background-color: #1f2937 !important; border-color: #1f2937 !important; color: #ffffff !important;')
					.removeClass('btn-default btn-light')
					.addClass('btn-primary');
			}
		});
	});
}

function push_stock_entry_to_mes(frm) {
	const $btn = frm._mes_push_button || $('[data-label="推送至MES"]');
	$btn.prop("disabled", true);

	frappe.call({
		method: "mes_integration.mes_integration.stock_entry.push_to_mes",
		args: {
			stock_entry_name: frm.doc.name
		},
		freeze: true,
		freeze_message: __("正在推送至 MES，请稍候..."),
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
				message: __("MES 推送已返回，但没有收到成功结果，请查看 Error Log 或浏览器控制台。")
			});
		},
		error: function(r) {
			$btn.prop("disabled", false);
			show_mes_push_error(r);
		}
	});
}

function show_mes_push_error(r) {
	let message = __("推送至 MES 失败，请查看 Error Log。");

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
