# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from smart_school.reports import absence_rate, get_allowed_classes

STATUSES = ("Present", "Absent", "Late", "Excused")


def execute(filters=None):
	"""Attendance counts for a term, per class or per student. The absence rate counts Absent fully,
	Late half and Excused not at all, like the risk score."""
	filters = frappe._dict(filters or {})
	classes = get_allowed_classes(filters.get("class"))
	by_student = filters.get("group_by") == "Student"

	records = frappe.get_all(
		"Attendance", filters={"term": filters.term, "class": ["in", classes or [""]]}, fields=["student", "class", "status"]
	)
	groups = {}
	for r in records:
		key = (r["class"], r.student) if by_student else (r["class"],)
		groups.setdefault(key, []).append(r.status)

	names = dict(frappe.get_all("Student", fields=["name", "full_name"], as_list=True)) if by_student else {}
	data = []
	for key, statuses in sorted(groups.items()):
		row = {"class": key[0], "days": len(statuses), "absence_rate": flt(absence_rate(statuses), 1)}
		if by_student:
			row.update({"student": key[1], "student_name": names.get(key[1])})
		row.update({s.lower(): statuses.count(s) for s in STATUSES})
		data.append(row)

	return get_columns(by_student), data


def get_columns(by_student):
	columns = [{"fieldname": "class", "label": "Class", "fieldtype": "Link", "options": "Class", "width": 100}]
	if by_student:
		columns += [
			{"fieldname": "student", "label": "Student", "fieldtype": "Link", "options": "Student", "width": 140},
			{"fieldname": "student_name", "label": "Student Name", "fieldtype": "Data", "width": 190},
		]
	columns += [{"fieldname": "days", "label": "Days Recorded", "fieldtype": "Int", "width": 110}]
	columns += [{"fieldname": s.lower(), "label": s, "fieldtype": "Int", "width": 90} for s in STATUSES]
	columns += [{"fieldname": "absence_rate", "label": "Absence Rate %", "fieldtype": "Percent", "width": 120}]
	return columns
