const native_material_request_list_settings = frappe.listview_settings["Material Request"] || {};
const native_material_request_indicator = native_material_request_list_settings.get_indicator;
const mes_issue_material_request_types = [
	"Material Transfer for Manufacture",
	"Injection Molding Issuance",
];

frappe.listview_settings["Material Request"] = {
	...native_material_request_list_settings,
	get_indicator: function(doc) {
		if (!mes_issue_material_request_types.includes(doc.material_request_type)) {
			return get_native_material_request_indicator(doc);
		}

		return get_mes_issue_material_request_indicator(doc);
	},
};

function get_mes_issue_material_request_indicator(doc) {
	const precision = frappe.defaults.get_default("float_precision");
	const per_ordered = flt(doc.per_ordered, precision);

	if (doc.status === "Stopped") {
		return [__("Stopped"), "red", "status,=,Stopped"];
	}

	if (doc.docstatus !== 1) {
		return get_native_material_request_indicator(doc);
	}

	if (per_ordered === 0) {
		return [__("Pending"), "orange", "per_ordered,=,0|docstatus,=,1"];
	}

	if (per_ordered < 100) {
		return [__("Partially Ordered"), "yellow", "per_ordered,<,100"];
	}

	if (per_ordered === 100) {
		return [__("Issued"), "green", "per_ordered,=,100"];
	}

	return get_native_material_request_indicator(doc);
}

function get_native_material_request_indicator(doc) {
	return native_material_request_indicator ? native_material_request_indicator(doc) : undefined;
}
