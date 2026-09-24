import frappe
from frappe.model.document import Document
from frappe.utils import flt

from smart_school.api import get_current_teacher
from smart_school.results import get_grade, recompute_student_term_result, round_half_up


class ExamResult(Document):
    def before_insert(self):
        # Never trust a teacher sent by the client
        self.teacher = get_current_teacher() or self.get_assigned_teacher()

    def get_assigned_teacher(self):
        exam_class = frappe.get_value("Exam", self.exam, "class")
        assigned = frappe.get_all(
            "Teacher Subject Assignment",
            filters={"parenttype": "Teacher", "subject": self.subject, "class": exam_class},
            pluck="parent",
        )
        return next((t for t in assigned if frappe.db.exists("Teacher", t)), None)

    def validate(self):
        self.check_duplicate()
        self.set_percentage_and_grade()

    def check_duplicate(self):
        # Cancelled results do not count, so a cancelled result can be amended
        existing = frappe.get_all(
            "Exam Result",
            filters={
                "student": self.student,
                "subject": self.subject,
                "exam": self.exam,
                "docstatus": ["!=", 2],
                "name": ["!=", self.name]
            }
        )

        if existing:
            frappe.throw(
                "A result for this Subject already exists for this Student in this Exam."
            )

    def set_percentage_and_grade(self):
        max_marks = flt(frappe.get_cached_value("Exam", self.exam, "max_marks")) or 100
        if not 0 <= flt(self.marks) <= max_marks:
            frappe.throw(f"Marks must be between 0 and {max_marks:g} for this exam")

        self.percentage = flt(self.marks) / max_marks * 100
        self.grade = get_grade(round_half_up(self.percentage))[0]

    def on_submit(self):
        self.update_student_term_result()

    def on_cancel(self):
        self.update_student_term_result()

    def update_student_term_result(self):
        recompute_student_term_result(self.student, frappe.get_cached_value("Exam", self.exam, "term"))
