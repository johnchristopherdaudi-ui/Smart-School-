import frappe
from frappe.utils import now_datetime

PUBLISH_PATCH = "smart_school.patches.set_exam_defaults_and_publish_existing"


def execute():
	"""first_published_on drives the "Changed After Publish" check. Exams published with the button take
	their published_on; exams published by the earlier patch (published_on empty on purpose, so the portal
	bell does not announce them as new) take the time that patch ran. published_on is left unchanged."""
	patch_ran_on = frappe.db.get_value("Patch Log", {"patch": PUBLISH_PATCH}, "creation") or now_datetime()
	for exam in frappe.get_all(
		"Exam",
		filters={"results_published": 1, "first_published_on": ["is", "not set"]},
		fields=["name", "published_on"],
	):
		frappe.db.set_value(
			"Exam", exam.name, "first_published_on", exam.published_on or patch_ran_on, update_modified=False
		)
