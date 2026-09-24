import frappe


def execute():
	"""Student Term Result had a site-only Custom DocPerm set (System Manager only) that overrode the doctype
	permissions, so Headmaster and Teacher could not read term results or run the result reports."""
	frappe.db.delete("Custom DocPerm", {"parent": "Student Term Result"})
	frappe.clear_cache(doctype="Student Term Result")
