import frappe
from frappe.utils import flt

from smart_school.results import get_grade, recompute_student_term_result, round_half_up


def execute():
    """Exam Results get a percentage and a grade from the current Grading System, then every
    Student Term Result is recomputed with the per-subject engine; (student, term) becomes unique."""
    max_marks = dict(frappe.get_all("Exam", fields=["name", "max_marks"], as_list=True))
    for r in frappe.get_all("Exam Result", filters={"docstatus": ["<", 2]}, fields=["name", "exam", "marks"]):
        percentage = flt(r.marks) / (flt(max_marks.get(r.exam)) or 100) * 100
        frappe.db.set_value(
            "Exam Result", r.name,
            {"percentage": percentage, "grade": get_grade(round_half_up(percentage))[0]},
            update_modified=False,
        )

    pairs = frappe.db.sql(
        """select distinct er.student, e.term
        from `tabExam Result` er join `tabExam` e on e.name = er.exam
        where er.docstatus = 1""",
        as_dict=True,
    )
    for p in pairs:
        recompute_student_term_result(p.student, p.term)

    # Term results without any submitted result left are stale
    valid = {(p.student, p.term) for p in pairs}
    for s in frappe.get_all("Student Term Result", fields=["name", "student", "term"]):
        if (s.student, s.term) not in valid:
            frappe.delete_doc("Student Term Result", s.name, ignore_permissions=True, force=True)

    frappe.db.add_unique("Student Term Result", ["student", "term"], constraint_name="unique_student_term")
