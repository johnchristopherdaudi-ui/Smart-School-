# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe

from smart_school.fees import get_fee_statement
from smart_school.reports import FEE_ROLES


def execute(filters=None):
	"""Per active student: fees due, paid, credit from overpayments and what is still owed, from the same
	fee statement the parent portal uses (credit pays the oldest debt first)."""
	frappe.only_for(FEE_ROLES)
	filters = frappe._dict(filters or {})

	student_filters = {"status": "Active"}
	if filters.get("class"):
		student_filters["current_class"] = filters.get("class")

	data = []
	for student in frappe.get_all(
		"Student", filters=student_filters, fields=["name", "full_name", "current_class"], order_by="current_class, full_name"
	):
		statement = get_fee_statement(student.name)
		rows = [r for r in statement.rows if (r.term == filters.term if filters.term else r.is_due)]
		if not rows:
			continue

		outstanding = sum(r.remaining for r in rows)
		if filters.only_defaulters and outstanding <= 0:
			continue

		data.append({
			"student": student.name,
			"student_name": student.full_name,
			"class": student.current_class,
			"terms": ", ".join(r.term for r in rows),
			"amount_due": sum(r.amount_due for r in rows),
			"paid": sum(r.total_paid for r in rows),
			"credit_applied": sum(r.credit_applied for r in rows),
			"outstanding": outstanding,
			"credit_left": statement.credit,
			"status": "Defaulter" if outstanding > 0 else "Cleared",
		})

	return get_columns(), data


def get_columns():
	return [
		{"fieldname": "student", "label": "Student", "fieldtype": "Link", "options": "Student", "width": 140},
		{"fieldname": "student_name", "label": "Student Name", "fieldtype": "Data", "width": 190},
		{"fieldname": "class", "label": "Class", "fieldtype": "Link", "options": "Class", "width": 90},
		{"fieldname": "terms", "label": "Terms", "fieldtype": "Data", "width": 160},
		{"fieldname": "amount_due", "label": "Fees Due", "fieldtype": "Currency", "width": 120},
		{"fieldname": "paid", "label": "Paid", "fieldtype": "Currency", "width": 120},
		{"fieldname": "credit_applied", "label": "Paid from Credit", "fieldtype": "Currency", "width": 130},
		{"fieldname": "outstanding", "label": "Outstanding", "fieldtype": "Currency", "width": 120},
		{"fieldname": "credit_left", "label": "Credit Left", "fieldtype": "Currency", "width": 110},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 100},
	]
