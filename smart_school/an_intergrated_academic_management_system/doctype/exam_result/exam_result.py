import frappe
from frappe.model.document import Document
from smart_school.api import get_current_teacher
from smart_school.notifications import send_notification


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
        self.set_grade()

    def check_duplicate(self):
        existing = frappe.get_all(
            "Exam Result",
            filters={
                "student": self.student,
                "subject": self.subject,
                "exam": self.exam,
                "name": ["!=", self.name]
            }
        )

        if existing:
            frappe.throw(
                "A result for this Subject already exists for this Student in this Exam."
            )

    def set_grade(self):
        grading = frappe.get_all(
            "Grading System",
            filters={"minimum_mark": ["<=", self.marks], "maximum_mark": [">=", self.marks]},
            fields=["grade"]
        )
        self.grade = grading[0].grade if grading else ""

    def on_submit(self):
        self.update_student_term_result()
        if not self.flags.skip_notification:
            self.notify_guardian()

    def get_points(self, marks):
        grading = frappe.get_all(
            "Grading System",
            filters={"minimum_mark": ["<=", marks], "maximum_mark": [">=", marks]},
            fields=["points"]
        )
        return grading[0].points if grading else 0

    def get_division(self, total_points):
        division = frappe.get_all(
            "Division Grading",
            filters={"minimum_points": ["<=", total_points], "maximum_points": [">=", total_points]},
            fields=["division"]
        )
        return division[0].division if division else ""

    def update_student_term_result(self):
        exam = frappe.get_doc("Exam", self.exam)
        term = exam.term

        exam_names = frappe.get_all("Exam", filters={"term": term}, pluck="name")

        results = frappe.get_all(
            "Exam Result",
            filters={"student": self.student, "exam": ["in", exam_names], "docstatus": 1},
            fields=["marks"]
        )

        if not results:
            return

        total_marks = sum([r.marks for r in results])
        average = total_marks / len(results)

        all_points = [self.get_points(r.marks) for r in results]
        all_points.sort()
        best_seven_points = all_points[:7]
        total_points = sum(best_seven_points)

        division = self.get_division(total_points)
        division_display = f"{division}, Points {total_points}" if division else ""

        existing = frappe.get_all(
            "Student Term Result",
            filters={"student": self.student, "term": term}
        )

        if existing:
            str_doc = frappe.get_doc("Student Term Result", existing[0].name)
            str_doc.average = average
            str_doc.division = division
            str_doc.total_points = total_points
            str_doc.division_display = division_display
            str_doc.save(ignore_permissions=True)
        else:
            str_doc = frappe.get_doc({
                "doctype": "Student Term Result",
                "student": self.student,
                "term": term,
                "average": average,
                "division": division,
                "total_points": total_points,
                "division_display": division_display
            })
            str_doc.insert(ignore_permissions=True)

    def notify_guardian(self):
        student_name = frappe.get_value("Student", self.student, "full_name")
        message = f"Dear Parent, {student_name} has a new result for {self.subject}: {self.marks} marks (Grade {self.grade})."
        send_notification(self.student, message, "Exam Result")