const native_material_request_list_settings = frappe.listview_settings["Material Request"] || {};
const native_material_request_indicator = native_material_request_list_settings.get_indicator;

frappe.listview_settings["Material Request"] = {
	...native_material_request_list_settings,
	get_indicator: function(doc) {
		if (doc.material_request_type !== "Material Transfer for Manufacture") {
			return get_native_material_request_indicator(doc);
		}

		return get_material_transfer_for_manufacture_indicator(doc);
	},
};

function get_material_transfer_for_manufacture_indicator(doc) {
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
		return [__("Partially Received"), "yellow", "per_ordered,<,100"];
	}

	if (per_ordered === 100) {
		return [__("Issued"), "green", "per_ordered,=,100"];
	}

	return get_native_material_request_indicator(doc);
}

function get_native_material_request_indicator(doc) {
	return native_material_request_indicator ? native_material_request_indicator(doc) : undefined;
}
