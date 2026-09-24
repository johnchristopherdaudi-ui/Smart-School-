import frappe


def execute():
	"""Existing exams are out of 100 and were already visible to parents, so mark them published
	(without notifications) to keep the portal unchanged. published_on stays empty so the portal bell
	does not announce them as new results."""
	frappe.db.set_value("Exam", {"max_marks": ["in", [0, None]]}, "max_marks", 100, update_modified=False)
	frappe.db.set_value("Exam", {"results_published": 0}, "results_published", 1, update_modified=False)
