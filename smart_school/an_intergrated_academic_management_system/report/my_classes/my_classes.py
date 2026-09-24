# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe

from smart_school.reports import get_teacher_scope


def execute(filters=None):
	"""The classes and subjects a teacher is assigned to (all assignments for Headmaster / System Manager),
	with how many students of the class already have submitted marks for the term."""
	filters = frappe._dict(filters or {})
	scope = get_teacher_scope()
	teacher = frappe.db.get_value("Teacher", {"user": frappe.session.user}, "name")

	assignment_filters = {"parenttype": "Teacher"}
	if scope is not None:
		assignment_filters["parent"] = teacher or ""
	assignments = frappe.get_all(
		"Teacher Subject Assignment",
		filters=assignment_filters,
		fields=["parent", "class", "subject"],
		order_by="class asc, subject asc",
	)
	teacher_names = dict(frappe.get_all("Teacher", fields=["name", "full_name"], as_list=True))
	class_teachers = dict(frappe.get_all("Class", fields=["name", "class_teacher"], as_list=True))

	data = []
	for a in assignments:
		students = frappe.db.count("Student", {"current_class": a["class"], "status": "Active"})
		entered = frappe.db.sql(
			"""select count(distinct er.student) from `tabExam Result` er join `tabExam` e on e.name = er.exam
			where e.term = %s and e.class = %s and er.subject = %s and er.docstatus = 1""",
			(filters.term, a["class"], a.subject),
		)[0][0]
		data.append(
			{
				"class": a["class"],
				"subject": a.subject,
				"teacher": teacher_names.get(a.parent),
				"students": students,
				"with_marks": entered,
				"missing": max(students - entered, 0),
				"class_teacher": "Yes" if class_teachers.get(a["class"]) == a.parent else "",
			}
		)
	return get_columns(), data


def get_columns():
	return [
		{"fieldname": "class", "label": "Class", "fieldtype": "Link", "options": "Class", "width": 90},
		{"fieldname": "subject", "label": "Subject", "fieldtype": "Link", "options": "Subject", "width": 140},
		{"fieldname": "teacher", "label": "Teacher", "fieldtype": "Data", "width": 160},
		{"fieldname": "students", "label": "Active Students", "fieldtype": "Int", "width": 120},
		{"fieldname": "with_marks", "label": "With Marks This Term", "fieldtype": "Int", "width": 150},
		{"fieldname": "missing", "label": "Missing Marks", "fieldtype": "Int", "width": 110},
		{"fieldname": "class_teacher", "label": "Class Teacher", "fieldtype": "Data", "width": 110},
	]
