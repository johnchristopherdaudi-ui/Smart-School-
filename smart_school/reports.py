"""Shared helpers for the Script Reports, number cards and dashboard charts."""

import frappe
from frappe.utils import flt, today

from smart_school.fees import get_fee_statement
from smart_school.tasks import get_current_term

FULL_ACCESS_ROLES = ("Headmaster", "System Manager")
FEE_ROLES = ("Accountant", "Headmaster", "System Manager")
ACADEMIC_ROLES = ("Teacher", "Headmaster", "System Manager")


def get_teacher_scope():
	"""None means full access (Headmaster / System Manager). A Teacher gets {class: {subjects}} from their
	Teacher Subject Assignments, so academic reports show only those classes and subjects."""
	if frappe.session.user == "Administrator" or set(FULL_ACCESS_ROLES) & set(frappe.get_roles()):
		return None

	scope = {}
	teacher = frappe.db.get_value("Teacher", {"user": frappe.session.user}, "name")
	if teacher:
		for row in frappe.get_all(
			"Teacher Subject Assignment",
			filters={"parenttype": "Teacher", "parent": teacher},
			fields=["class", "subject"],
		):
			scope.setdefault(row["class"], set()).add(row.subject)
	return scope


def get_allowed_classes(class_name=None):
	"""Classes this user may report on, optionally narrowed to one class (refused if not allowed)."""
	frappe.only_for(ACADEMIC_ROLES)
	scope = get_teacher_scope()
	if class_name:
		if scope is not None and class_name not in scope:
			frappe.throw(f"You are not assigned to teach in {class_name}", frappe.PermissionError)
		return [class_name]

	classes = frappe.get_all("Class", pluck="name", order_by="level asc")
	return classes if scope is None else [c for c in classes if c in scope]


@frappe.whitelist()
def get_default_term():
	"""The term running today (start_date <= today <= end_date): the default Term filter of the reports."""
	frappe.only_for(ACADEMIC_ROLES + FEE_ROLES)
	return frappe.db.get_value("Term", {"start_date": ["<=", today()], "end_date": [">=", today()]}, "name")


def get_current_term_name():
	term = get_current_term()
	return term.name if term else None


# ---------- number cards ----------


@frappe.whitelist()
def get_fees_collected_this_term(filters=None):
	frappe.only_for(FEE_ROLES)
	term = get_current_term_name()
	total = (
		frappe.get_all(
			"Fee Payment", filters={"term": term, "docstatus": 1}, fields=["sum(amount_paid) as total"]
		)[0].total
		if term
		else 0
	)
	return {"value": flt(total), "fieldtype": "Currency"}


@frappe.whitelist()
def get_outstanding_fees(filters=None):
	frappe.only_for(FEE_ROLES)
	students = frappe.get_all("Student", filters={"status": "Active"}, pluck="name")
	return {"value": sum(get_fee_statement(s).balance for s in students), "fieldtype": "Currency"}


# ---------- dashboard chart data ----------


def get_division_distribution():
	term = get_current_term_name()
	classes = get_allowed_classes()
	divisions = frappe.get_all("Division Grading", pluck="division", order_by="minimum_points asc") + [
		"Incomplete"
	]
	counts = dict.fromkeys(divisions, 0)
	for division in frappe.get_all(
		"Student Term Result", filters={"term": term, "class": ["in", classes or [""]]}, pluck="division"
	):
		counts[division] = counts.get(division, 0) + 1
	return {
		"labels": list(counts),
		"datasets": [{"name": f"Divisions ({term})", "values": list(counts.values())}],
	}


def get_fee_collection_by_term():
	frappe.only_for(FEE_ROLES)
	rows = frappe.db.sql(
		"""select fp.term, sum(fp.amount_paid) as total
        from `tabFee Payment` fp join `tabTerm` t on t.name = fp.term
        where fp.docstatus = 1 group by fp.term order by min(t.start_date)""",
		as_dict=True,
	)
	return {
		"labels": [r.term for r in rows],
		"datasets": [{"name": "Collected", "values": [flt(r.total) for r in rows]}],
	}


def get_absence_rate_by_class():
	term = get_current_term_name()
	labels, values = [], []
	for class_name in get_allowed_classes():
		statuses = frappe.get_all("Attendance", filters={"term": term, "class": class_name}, pluck="status")
		labels.append(class_name)
		values.append(flt(absence_rate(statuses), 1))
	return {"labels": labels, "datasets": [{"name": f"Absence rate % ({term})", "values": values}]}


def absence_rate(statuses):
	"""Absent counts fully, Late half, Excused not at all (same rule as the risk score)."""
	if not statuses:
		return 0
	return (statuses.count("Absent") + 0.5 * statuses.count("Late")) / len(statuses) * 100
