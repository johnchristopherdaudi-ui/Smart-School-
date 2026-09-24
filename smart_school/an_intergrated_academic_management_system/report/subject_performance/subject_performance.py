# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from smart_school.reports import get_allowed_classes, get_teacher_scope
from smart_school.results import get_grade, get_subject_scores

GRADES = ("A", "B", "C", "D", "F")


def execute(filters=None):
	"""Per class and subject for a term: mean subject score, pass rate (A-D pass, F fails), grade distribution
	and the teacher who entered the marks. Teachers see only the subjects they are assigned to."""
	filters = frappe._dict(filters or {})
	classes = get_allowed_classes(filters.get("class"))
	scope = get_teacher_scope()

	scores = {}
	for r in frappe.get_all(
		"Student Term Result",
		filters={"term": filters.term, "class": ["in", classes or [""]]},
		fields=["student", "class"],
	):
		for subject, score in get_subject_scores(r.student, filters.term)[0].items():
			if filters.subject and subject != filters.subject:
				continue
			if scope is not None and subject not in scope.get(r["class"], ()):
				continue
			scores.setdefault((r["class"], subject), []).append(score)

	teachers = get_subject_teachers(filters.term)
	teacher_names = dict(frappe.get_all("Teacher", fields=["name", "full_name"], as_list=True))

	data = []
	for (class_name, subject), values in sorted(scores.items()):
		teacher = teachers.get((class_name, subject))
		if filters.teacher and teacher != filters.teacher:
			continue
		grades = [get_grade(v)[0] for v in values]
		row = {
			"class": class_name,
			"subject": subject,
			"teacher": teacher,
			"teacher_name": teacher_names.get(teacher),
			"students": len(values),
			"mean": flt(sum(values) / len(values), 2),
			"pass_rate": flt(sum(g != "F" for g in grades) / len(grades) * 100, 1),
		}
		row.update({g.lower(): grades.count(g) for g in GRADES})
		data.append(row)

	return get_columns(), data


def get_subject_teachers(term):
	"""The teacher who entered most results for each (class, subject) in the term."""
	teachers = {}
	for r in frappe.db.sql(
		"""select e.class, er.subject, er.teacher, count(*) as n
		from `tabExam Result` er join `tabExam` e on e.name = er.exam
		where e.term = %s and er.docstatus = 1 and ifnull(er.teacher, '') != ''
		group by e.class, er.subject, er.teacher order by n desc""",
		term,
		as_dict=True,
	):
		teachers.setdefault((r["class"], r.subject), r.teacher)
	return teachers


def get_columns():
	return [
		{"fieldname": "class", "label": "Class", "fieldtype": "Link", "options": "Class", "width": 90},
		{"fieldname": "subject", "label": "Subject", "fieldtype": "Link", "options": "Subject", "width": 130},
		{"fieldname": "teacher", "label": "Teacher", "fieldtype": "Link", "options": "Teacher", "width": 130},
		{"fieldname": "teacher_name", "label": "Teacher Name", "fieldtype": "Data", "width": 150},
		{"fieldname": "students", "label": "Students", "fieldtype": "Int", "width": 90},
		{"fieldname": "mean", "label": "Mean", "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "pass_rate", "label": "Pass Rate %", "fieldtype": "Percent", "width": 100},
	] + [{"fieldname": g.lower(), "label": g, "fieldtype": "Int", "width": 60} for g in GRADES]
