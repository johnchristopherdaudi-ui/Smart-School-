# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import json

import frappe

from smart_school.reports import get_allowed_classes

PARTS = ("attendance", "discipline", "low_average", "failed_subjects", "decline")


def execute(filters=None):
	"""Students by risk score with the points of each part, as stored by the daily risk job."""
	filters = frappe._dict(filters or {})
	classes = get_allowed_classes(filters.get("class"))

	student_filters = {"status": "Active", "current_class": ["in", classes or [""]], "risk_level": ["is", "set"]}
	if filters.get("risk_level"):
		student_filters["risk_level"] = filters.risk_level

	data = []
	for s in frappe.get_all(
		"Student", filters=student_filters,
		fields=["name", "full_name", "current_class", "risk_score", "risk_level", "risk_breakdown", "risk_updated_on"],
		order_by="risk_score desc",
	):
		breakdown = json.loads(s.risk_breakdown or "{}")
		row = {
			"student": s.name,
			"student_name": s.full_name,
			"class": s.current_class,
			"risk_score": s.risk_score,
			"risk_level": s.risk_level,
			"term": breakdown.get("term"),
			"failed": ", ".join((breakdown.get("failed_subjects") or {}).get("subjects") or []),
			"updated_on": s.risk_updated_on,
		}
		row.update({part: (breakdown.get(part) or {}).get("score") for part in PARTS})
		data.append(row)

	return get_columns(), data


def get_columns():
	pts = lambda fieldname, label: {"fieldname": fieldname, "label": label, "fieldtype": "Float", "precision": 1, "width": 100}
	return [
		{"fieldname": "student", "label": "Student", "fieldtype": "Link", "options": "Student", "width": 140},
		{"fieldname": "student_name", "label": "Student Name", "fieldtype": "Data", "width": 190},
		{"fieldname": "class", "label": "Class", "fieldtype": "Link", "options": "Class", "width": 90},
		{"fieldname": "risk_score", "label": "Risk Score", "fieldtype": "Float", "precision": 1, "width": 100},
		{"fieldname": "risk_level", "label": "Level", "fieldtype": "Data", "width": 80},
		pts("attendance", "Attendance"),
		pts("discipline", "Discipline"),
		pts("low_average", "Low Average"),
		pts("failed_subjects", "Failed Subjects"),
		pts("decline", "Decline"),
		{"fieldname": "failed", "label": "Subjects with F", "fieldtype": "Data", "width": 180},
		{"fieldname": "term", "label": "Term", "fieldtype": "Link", "options": "Term", "width": 90},
		{"fieldname": "updated_on", "label": "Updated On", "fieldtype": "Datetime", "width": 150},
	]
