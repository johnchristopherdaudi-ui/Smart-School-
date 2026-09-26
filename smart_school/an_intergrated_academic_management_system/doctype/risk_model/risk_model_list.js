frappe.listview_settings["Risk Model"] = {
	get_indicator(doc) {
		const colors = { Active: "green", Rejected: "orange", "Insufficient Data": "gray", Retired: "gray" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
	onload(listview) {
		if (!frappe.user.has_role("System Manager")) return;
		listview.page.add_inner_button(__("Train Now"), () => {
			frappe.call({ method: "smart_school.risk_model.retrain" }).then((r) => frappe.show_alert(r.message));
		});
	},
};
