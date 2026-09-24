frappe.listview_settings["Student Term Result"] = {
	onload(listview) {
		if (!(frappe.user.has_role("Headmaster") || frappe.user.has_role("System Manager"))) {
			return;
		}

		listview.page.add_inner_button(__("Print Class Report Cards"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Print Class Report Cards"),
				fields: [
					{ fieldname: "class_name", label: __("Class"), fieldtype: "Link", options: "Class", reqd: 1 },
					{ fieldname: "term", label: __("Term"), fieldtype: "Link", options: "Term", reqd: 1 },
				],
				primary_action_label: __("Print"),
				primary_action(values) {
					frappe
						.xcall("smart_school.report_card.get_class_report_cards", values)
						.then((names) => {
							if (!names.length) {
								frappe.msgprint(__("No term results for {0} in {1}", [values.class_name, values.term]));
								return;
							}
							// One PDF with every report card, in merit order
							const params = new URLSearchParams({
								doctype: "Student Term Result",
								name: JSON.stringify(names),
								format: "Report Card",
								no_letterhead: 1,
							});
							window.open(`/api/method/frappe.utils.print_format.download_multi_pdf?${params}`);
							dialog.hide();
						});
				},
			});
			frappe.xcall("smart_school.reports.get_default_term").then((term) => term && dialog.set_value("term", term));
			dialog.show();
		});
	},
};
