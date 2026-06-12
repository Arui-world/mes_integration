(function () {
	frappe.listview_settings["MES Integration Log"] = {
		formatters: {
			event(value) {
				return value ? __(value) : value;
			},
		},
	};
})();
