frappe.listview_settings["Stock Entry"] = frappe.listview_settings["Stock Entry"] || {};

frappe.listview_settings["Stock Entry"].add_fields = [
	...(frappe.listview_settings["Stock Entry"].add_fields || []),
	"`tabStock Entry`.`custom_mes_status`",
];

frappe.listview_settings["Stock Entry"].formatters = {
	...(frappe.listview_settings["Stock Entry"].formatters || {}),
	custom_mes_status: function(value) {
		const status = value || "Unpushed";
		const color = status === "Pushed" ? "blue" : "red";

		return `<span class="indicator-pill ${color} no-indicator-dot">${__(status)}</span>`;
	},
};
