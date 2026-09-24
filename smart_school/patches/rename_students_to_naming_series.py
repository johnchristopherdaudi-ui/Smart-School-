import frappe
from frappe.model.naming import make_autoname


def execute():
	"""Students used to be named by full name. Move them to the STU-.YYYY.-.##### series;
	rename_doc updates every Link, child table row and attachment that points to them."""
	students = frappe.get_all(
		"Student", filters={"name": ["not like", "STU-%"]}, pluck="name", order_by="creation asc"
	)
	for old_name in students:
		frappe.rename_doc(
			"Student",
			old_name,
			make_autoname("STU-.YYYY.-.#####", "Student"),
			force=True,
			show_alert=False,
			rebuild_search=False,
		)
