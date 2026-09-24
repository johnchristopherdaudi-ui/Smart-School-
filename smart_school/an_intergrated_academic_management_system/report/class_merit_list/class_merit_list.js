// Copyright (c) 2026, john daudi and contributors
// For license information, please see license.txt

frappe.query_reports["Class Merit List"] = {
	filters: [
	  {
	    "fieldname": "class",
	    "label": "Class",
	    "fieldtype": "Link",
	    "options": "Class",
	    "reqd": 1
	  },
	  {
	    "fieldname": "term",
	    "label": "Term",
	    "fieldtype": "Link",
	    "options": "Term",
	    "reqd": 1
	  }
	],
	onload(report) {
		// Default to the term running today
		if (report.get_filter_value("term")) return;
		frappe.xcall("smart_school.reports.get_default_term").then((term) => {
			if (term) report.set_filter_value("term", term);
		});
	},
};
