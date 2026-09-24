// Copyright (c) 2026, john daudi and contributors
// For license information, please see license.txt

frappe.query_reports["Pending Report Card Comments"] = {
	filters: [
		{ fieldname: "term", label: __("Term"), fieldtype: "Link", options: "Term", reqd: 1 },
		{
			fieldname: "comment",
			label: __("Comment"),
			fieldtype: "Select",
			options: "Class Teacher\nHeadmaster",
			default: frappe.user.has_role("Headmaster") ? "Headmaster" : "Class Teacher",
			reqd: 1,
		},
	],
	onload(report) {
		if (report.get_filter_value("term")) return;
		frappe.xcall("smart_school.reports.get_default_term").then((term) => {
			if (term) report.set_filter_value("term", term);
		});
	},
};
