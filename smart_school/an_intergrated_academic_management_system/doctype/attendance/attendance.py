import frappe
from frappe.model.document import Document


class Attendance(Document):
	def validate(self):
		self.check_duplicate()
		if not self.get("class"):
			self.set("class", frappe.get_cached_value("Student", self.student, "current_class"))
		self.set_term()

	def check_duplicate(self):
		other = frappe.db.get_value(
			"Attendance", {"student": self.student, "date": self.date, "name": ["!=", self.name]}, "name"
		)
		if other:
			frappe.throw(f"Attendance for {self.student} on {self.date} already exists ({other})")

	def set_term(self):
		if not self.date:
			return

		term = frappe.get_all(
			"Term",
			filters={"start_date": ["<=", self.date], "end_date": [">=", self.date]},
			fields=["name"],
			limit=1,
		)

		if term:
			self.term = term[0].name
		else:
			self.term = None
			frappe.msgprint(
				f"Hakuna Term inayolingana na tarehe {self.date}. "
				"Attendance hii haitaunganishwa na term yoyote.",
				alert=True,
			)
