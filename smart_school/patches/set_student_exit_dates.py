import json

import frappe
from frappe.utils import getdate

from smart_school.an_intergrated_academic_management_system.doctype.student.student import NO_RISK


def execute():
	"""Students who already left get an exit_date: the day their status changed from Active (from the
	document history), else the day the record was created (e.g. imported as Dropped). Their risk
	prediction is cleared. The date can be corrected on the Student."""
	for student in frappe.get_all(
		"Student",
		filters={"status": ["!=", "Active"], "exit_date": ["is", "not set"]},
		fields=["name", "creation"],
	):
		left_on = status_change_date(student.name) or student.creation
		frappe.db.set_value(
			"Student",
			student.name,
			{"exit_date": getdate(left_on), **NO_RISK},
			update_modified=False,
		)


def status_change_date(student):
	"""When the status last changed from Active, from the Version history."""
	for version in frappe.get_all(
		"Version",
		filters={"ref_doctype": "Student", "docname": student},
		fields=["creation", "data"],
		order_by="creation desc",
	):
		changes = json.loads(version.data or "{}").get("changed") or []
		if any(field == "status" and old == "Active" for field, old, _ in changes):
			return version.creation
	return None
