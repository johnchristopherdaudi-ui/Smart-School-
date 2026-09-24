# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe

from smart_school.reports import FULL_ACCESS_ROLES


def execute(filters=None):
	"""Term results still waiting for a comment: the Headmaster's comment (Headmaster / System Manager),
	or the class teacher's comment for the classes this user is class teacher of."""
	filters = frappe._dict(filters or {})
	full_access = frappe.session.user == "Administrator" or bool(
		set(FULL_ACCESS_ROLES) & set(frappe.get_roles())
	)

	if filters.comment == "Headmaster":
		frappe.only_for(FULL_ACCESS_ROLES)
		field, classes = "headmaster_comment", None
	else:
		field = "class_teacher_comment"
		teacher = frappe.db.get_value("Teacher", {"user": frappe.session.user}, "name")
		classes = (
			None
			if full_access
			else frappe.get_all("Class", filters={"class_teacher": teacher or ""}, pluck="name")
		)

	query_filters = {"term": filters.term, field: ["is", "not set"]}
	if classes is not None:
		query_filters["class"] = ["in", classes or [""]]

	rows = frappe.get_all(
		"Student Term Result",
		filters=query_filters,
		fields=["name", "student", "class", "average", "division"],
		order_by="class asc, average desc",
	)
	names = dict(
		frappe.get_all(
			"Student",
			filters={"name": ["in", [r.student for r in rows] or [""]]},
			fields=["name", "full_name"],
			as_list=True,
		)
	)
	for r in rows:
		r.student_name = names.get(r.student)

	return get_columns(), rows


def get_columns():
	return [
		{
			"fieldname": "name",
			"label": "Term Result",
			"fieldtype": "Link",
			"options": "Student Term Result",
			"width": 130,
		},
		{"fieldname": "student", "label": "Student", "fieldtype": "Link", "options": "Student", "width": 140},
		{"fieldname": "student_name", "label": "Student Name", "fieldtype": "Data", "width": 200},
		{"fieldname": "class", "label": "Class", "fieldtype": "Link", "options": "Class", "width": 90},
		{"fieldname": "average", "label": "Average", "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "division", "label": "Division", "fieldtype": "Data", "width": 110},
	]
