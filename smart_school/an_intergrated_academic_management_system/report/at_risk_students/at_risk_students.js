// Copyright (c) 2026, john daudi and contributors
// For license information, please see license.txt

frappe.query_reports["At-Risk Students"] = {
	filters: [
	  {
	    "fieldname": "class",
	    "label": "Class",
	    "fieldtype": "Link",
	    "options": "Class",
	    "reqd": 0
	  },
	  {
	    "fieldname": "risk_level",
	    "label": "Risk Level",
	    "fieldtype": "Select",
	    "options": "\nHigh\nMedium\nLow",
	    "default": "High"
	  }
	],
};
