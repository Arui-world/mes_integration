frappe.listview_settings["Delivery Note"] = {
	onload: function (listview) {
		// 为发货放行状态 Select 列的 indicator-pill 注入自定义颜色
		// 覆盖 guess_colour 对 "Ready to Deliver" 返回的默认灰色
		if (!document.getElementById("delivery-readiness-indicator-css")) {
			const style = document.createElement("style");
			style.id = "delivery-readiness-indicator-css";
			style.textContent = `
				.indicator-pill[data-filter^="custom_delivery_readiness_status"] {
					background: var(--bg-gray-100);
					color: var(--text-on-gray);
				}
				.indicator-pill[data-filter="custom_delivery_readiness_status,=,Ready to Deliver"] {
					background: var(--bg-blue);
					color: var(--text-on-blue);
				}
				.indicator-pill[data-filter="custom_delivery_readiness_status,=,Delivered"] {
					background: var(--bg-green);
					color: var(--text-on-green);
				}
				.indicator-pill[data-filter="custom_delivery_readiness_status,=,Pending Release"] {
					background: var(--bg-orange);
					color: var(--text-on-orange);
				}
			`;
			document.head.appendChild(style);
		}
	},
};
