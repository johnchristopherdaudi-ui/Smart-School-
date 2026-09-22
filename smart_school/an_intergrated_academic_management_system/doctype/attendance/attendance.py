import frappe
from frappe.model.document import Document


class Attendance(Document):
    def validate(self):
        self.set_term()

    def set_term(self):
        if not self.date:
            return

        term = frappe.get_all(
            "Term",
            filters={
                "start_date": ["<=", self.date],
                "end_date": [">=", self.date]
            },
            fields=["name"],
            limit=1
        )

        if term:
            self.term = term[0].name
        else:
            self.term = None
            frappe.msgprint(
                f"Hakuna Term inayolingana na tarehe {self.date}. "
                "Attendance hii haitaunganishwa na term yoyote.",
                alert=True
            )
