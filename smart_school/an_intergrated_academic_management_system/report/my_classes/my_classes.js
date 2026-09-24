// Copyright (c) 2026, john daudi and contributors
// For license information, please see license.txt

frappe.query_reports["My Classes"] = {
	filters: [{ fieldname: "term", label: __("Term"), fieldtype: "Link", options: "Term", reqd: 1 }],
	onload(report) {
		if (report.get_filter_value("term")) return;
		frappe.xcall("smart_school.reports.get_default_term").then((term) => {
			if (term) report.set_filter_value("term", term);
		});
	},
};
