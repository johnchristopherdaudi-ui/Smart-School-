# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe

from smart_school.reports import get_allowed_classes
from smart_school.results import INCOMPLETE


def execute(filters=None):
	"""Number of students per division for a term, split by gender, per class."""
	filters = frappe._dict(filters or {})
	classes = get_allowed_classes(filters.get("class"))
	divisions = frappe.get_all("Division Grading", pluck="division", order_by="minimum_points asc") + [
		INCOMPLETE
	]

	results = frappe.db.sql(
		"""select str.class, str.division, ifnull(s.gender, '') as gender, count(*) as n
		from `tabStudent Term Result` str join `tabStudent` s on s.name = str.student
		where str.term = %(term)s and str.class in %(classes)s
		group by str.class, str.division, s.gender""",
		{"term": filters.term, "classes": classes or [""]},
		as_dict=True,
	)

	counts = {}
	for r in results:
		row = counts.setdefault((r["class"], r.division), {"male": 0, "female": 0, "unspecified": 0})
		key = r.gender.lower() if r.gender in ("Male", "Female") else "unspecified"
		row[key] += r.n

	data = []
	for class_name in classes:
		for division in divisions + sorted({d for c, d in counts if c == class_name and d not in divisions}):
			row = counts.get((class_name, division))
			if row:
				data.append({"class": class_name, "division": division, **row, "total": sum(row.values())})

	return get_columns(), data


def get_columns():
	return [
		{"fieldname": "class", "label": "Class", "fieldtype": "Link", "options": "Class", "width": 100},
		{"fieldname": "division", "label": "Division", "fieldtype": "Data", "width": 130},
		{"fieldname": "male", "label": "Male", "fieldtype": "Int", "width": 90},
		{"fieldname": "female", "label": "Female", "fieldtype": "Int", "width": 90},
		{"fieldname": "unspecified", "label": "Gender Not Set", "fieldtype": "Int", "width": 120},
		{"fieldname": "total", "label": "Total", "fieldtype": "Int", "width": 90},
	]
