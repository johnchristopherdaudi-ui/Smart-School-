import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	"""Announcement: tittle -> title, the legacy hidden `class` field moves into the `classes` table,
	and announcements without classes are addressed to the whole school."""
	rename_field("Announcement", "tittle", "title")

	has_legacy_class = frappe.db.has_column("Announcement", "class")
	for name in frappe.get_all("Announcement", pluck="name"):
		classes = frappe.get_all("Announcement Class", filters={"parent": name}, pluck="class")
		legacy_class = frappe.db.get_value("Announcement", name, "class") if has_legacy_class else None

		if legacy_class and legacy_class not in classes:
			doc = frappe.get_doc("Announcement", name)
			doc.append("classes", {"class": legacy_class})
			doc.save(ignore_permissions=True)
			classes.append(legacy_class)

		audience = "Specific Classes" if classes else "All School"
		frappe.db.set_value("Announcement", name, "audience", audience, update_modified=False)
