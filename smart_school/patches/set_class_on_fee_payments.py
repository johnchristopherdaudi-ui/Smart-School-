import frappe


def execute():
	"""Fee Payment now records the student's class so past terms stay priced correctly after promotion.
	Fill it from the Student Academic Record of the term's academic year, else the current class."""
	payments = frappe.get_all(
		"Fee Payment", filters={"class": ["is", "not set"]}, fields=["name", "student", "term"]
	)
	for p in payments:
		academic_year = frappe.db.get_value("Term", p.term, "academic_year")
		student_class = frappe.db.get_value(
			"Student Academic Record", {"student": p.student, "academic_year": academic_year}, "class"
		) or frappe.db.get_value("Student", p.student, "current_class")
		frappe.db.set_value("Fee Payment", p.name, "class", student_class, update_modified=False)
