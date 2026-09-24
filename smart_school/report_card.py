"""Report card: data for the "Report Card" print format, the parent portal download and class printing."""

import frappe
from frappe.utils import flt, formatdate, getdate

from smart_school.results import (
    BEST_SUBJECTS,
    INCOMPLETE,
    get_class_positions,
    get_grade,
    get_subject_scores,
    is_term_summary_published,
)

PRINT_FORMAT = "Report Card"
PRINTER_ROLES = ("Headmaster", "System Manager")


def get_report_card_data(term_result):
    """Everything the report card shows for one Student Term Result (used from the print format via jinja)."""
    doc = frappe.get_doc("Student Term Result", term_result) if isinstance(term_result, str) else term_result
    student = frappe.get_doc("Student", doc.student)
    term = frappe.get_doc("Term", doc.term)
    settings = frappe.get_cached_doc("Smart School Settings")

    exams = frappe.get_all(
        "Exam", filters={"term": doc.term, "class": doc.get("class")},
        fields=["name", "exam_name", "max_marks", "weight"], order_by="creation asc",
    )
    marks = {}
    for r in frappe.get_all(
        "Exam Result",
        filters={"student": doc.student, "exam": ["in", [e.name for e in exams] or [""]], "docstatus": 1},
        fields=["exam", "subject", "marks"],
    ):
        marks[(r.subject, r.exam)] = flt(r.marks)

    remarks = dict(frappe.get_all("Grading System", fields=["grade", "remark"], as_list=True))
    subjects = []
    for subject, score in sorted(get_subject_scores(doc.student, doc.term)[0].items()):
        grade, points = get_grade(score)
        subjects.append(frappe._dict(
            subject=subject,
            exam_marks=[marks.get((subject, e.name)) for e in exams],
            score=score, grade=grade, remark=remarks.get(grade) or "", points=points,
        ))

    positions, ranked = get_class_positions(doc.get("class"), doc.term)
    position = positions.get(doc.student)

    statuses = frappe.get_all("Attendance", filters={"student": doc.student, "term": doc.term}, pluck="status")
    attended = statuses.count("Present") + statuses.count("Late")

    next_term = frappe.get_all(
        "Term", filters={"start_date": [">", term.start_date]}, fields=["start_date"], order_by="start_date asc", limit=1
    )

    return frappe._dict(
        school=settings,
        student=student,
        term=term,
        result=doc,
        exams=exams,
        subjects=subjects,
        best_subjects=BEST_SUBJECTS,
        is_incomplete=doc.division == INCOMPLETE,
        position=position,
        out_of=len(ranked),
        position_text=f"Position {position} out of {len(ranked)}" if position else "Not ranked (fewer than 7 subjects)",
        attendance=frappe._dict(
            days=len(statuses), present=statuses.count("Present"), absent=statuses.count("Absent"),
            late=statuses.count("Late"), excused=statuses.count("Excused"),
            rate=flt(attended / len(statuses) * 100, 1) if statuses else None,
        ),
        next_term_opens=formatdate(next_term[0].start_date, "dd MMMM yyyy") if next_term else "To be announced",
        printed_on=formatdate(getdate(), "dd MMMM yyyy"),
    )


@frappe.whitelist()
def download_report_card(student, term):
    """Parent portal: the guardian's own child, and only once every exam of that term is published."""
    from smart_school.portal_utils import get_logged_in_guardian

    guardian = get_logged_in_guardian()
    if student not in [row.student for row in guardian.students]:
        frappe.throw("Huna ruhusa ya kupakua report card hii", frappe.PermissionError)

    result = frappe.db.get_value("Student Term Result", {"student": student, "term": term}, ["name", "class"], as_dict=True)
    if not result or not is_term_summary_published(term, result["class"]):
        frappe.throw("Report card itapatikana matokeo yote ya muhula huu yakishachapishwa", frappe.PermissionError)

    frappe.local.response.filename = f"Report Card - {student} - {term}.pdf"
    frappe.local.response.filecontent = render_pdf(result.name)
    frappe.local.response.type = "pdf"


@frappe.whitelist()
def get_class_report_cards(class_name, term):
    """Headmaster: the class's term results in merit order (unranked last), for printing all report cards at once."""
    frappe.only_for(PRINTER_ROLES)
    positions, ranked = get_class_positions(class_name, term)
    unranked = frappe.get_all(
        "Student Term Result", filters={"class": class_name, "term": term, "division": INCOMPLETE},
        pluck="student", order_by="average desc",
    )
    order = [r.student for r in ranked] + unranked
    names = dict(frappe.get_all("Student Term Result", filters={"class": class_name, "term": term},
                                fields=["student", "name"], as_list=True))
    return [names[s] for s in order if s in names]


def render_pdf(term_result):
    """PDF of one report card; the caller has already checked who may see it."""
    from frappe.utils.pdf import get_pdf

    frappe.flags.ignore_print_permissions = True
    try:
        html = frappe.get_print("Student Term Result", term_result, PRINT_FORMAT, no_letterhead=1)
    finally:
        frappe.flags.ignore_print_permissions = False
    return get_pdf(html)
