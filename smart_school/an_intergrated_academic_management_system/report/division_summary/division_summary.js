// Copyright (c) 2026, john daudi and contributors
// For license information, please see license.txt

frappe.query_reports["Division Summary"] = {
	filters: [
	  {
	    "fieldname": "term",
	    "label": "Term",
	    "fieldtype": "Link",
	    "options": "Term",
	    "reqd": 1
	  },
	  {
	    "fieldname": "class",
	    "label": "Class",
	    "fieldtype": "Link",
	    "options": "Class",
	    "reqd": 0
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
