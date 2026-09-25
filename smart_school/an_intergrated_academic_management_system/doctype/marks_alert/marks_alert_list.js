frappe.listview_settings["Marks Alert"] = {
	add_fields: ["status", "severity"],
	get_indicator(doc) {
		const colors = { Open: "orange", "Reviewed-OK": "green", Corrected: "blue", "Auto-resolved": "gray" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
