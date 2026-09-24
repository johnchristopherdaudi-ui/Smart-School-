# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from smart_school.reports import get_allowed_classes
from smart_school.results import INCOMPLETE, get_class_positions


def execute(filters=None):
	filters = frappe._dict(filters or {})
	class_name = get_allowed_classes(filters.get("class"))[0]

	results = frappe.get_all(
		"Student Term Result",
		filters={"class": class_name, "term": filters.term},
		fields=["student", "average", "subjects_count", "total_points", "division", "division_display"],
	)
	names = dict(
		frappe.get_all(
			"Student", filters={"name": ["in", [r.student for r in results] or [""]]},
			fields=["name", "full_name"], as_list=True,
		)
	)

	# Standard competition ranking by average: equal averages share a position (1, 2, 2, 4)
	positions, ranked = get_class_positions(class_name, filters.term)
	data = [row(r, names, positions[r.student], "") for r in ranked]

	# Students with fewer than 7 subjects have no division, so they are listed apart without a position
	for r in sorted((r for r in results if r.division == INCOMPLETE), key=lambda r: -flt(r.average, 2)):
		data.append(row(r, names, None, f"Incomplete: {r.subjects_count} subjects"))

	return get_columns(), data


def row(r, names, position, remark):
	return {
		"position": position,
		"student": r.student,
		"student_name": names.get(r.student),
		"subjects_count": r.subjects_count,
		"average": flt(r.average, 2),
		"total_points": r.total_points if r.division != INCOMPLETE else None,
		"division": r.division,
		"remark": remark,
	}


def get_columns():
	return [
		{"fieldname": "position", "label": "Position", "fieldtype": "Int", "width": 80},
		{"fieldname": "student", "label": "Student", "fieldtype": "Link", "options": "Student", "width": 140},
		{"fieldname": "student_name", "label": "Student Name", "fieldtype": "Data", "width": 200},
		{"fieldname": "subjects_count", "label": "Subjects", "fieldtype": "Int", "width": 90},
		{"fieldname": "average", "label": "Average", "fieldtype": "Float", "precision": 2, "width": 100},
		{"fieldname": "total_points", "label": "Points (best 7)", "fieldtype": "Int", "width": 110},
		{"fieldname": "division", "label": "Division", "fieldtype": "Data", "width": 110},
		{"fieldname": "remark", "label": "Remark", "fieldtype": "Data", "width": 180},
	]
