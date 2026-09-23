import frappe
from frappe.utils import flt, getdate, today


def get_fee_statement(student):
    """Single source of truth for a student's fees: the fees page, student page, notifications
    and payment validation all use it.

    Each term is priced with the Fee Structure of the class the student was in that term:
    the class recorded on that term's Fee Payments, else the Student Academic Record of that
    academic year, else the current class (current academic year and upcoming terms only).
    Only terms that have started count as debt; upcoming terms are listed so parents can pay early."""
    student_doc = frappe.get_cached_doc("Student", student)
    today_date = getdate(today())

    terms = frappe.get_all(
        "Term", fields=["name", "term_name", "academic_year", "start_date"], order_by="start_date asc"
    )
    for t in terms:
        t.is_due = bool(t.start_date) and getdate(t.start_date) <= today_date
    started = [t for t in terms if t.is_due]
    current_year = started[-1].academic_year if started else None

    fee_amounts = {
        (fs["class"], fs.term): flt(fs.amount)
        for fs in frappe.get_all("Fee Structure", fields=["class", "term", "amount"])
    }
    record_classes = dict(
        frappe.get_all(
            "Student Academic Record", filters={"student": student}, fields=["academic_year", "class"], as_list=True
        )
    )

    paid, paid_classes = {}, {}
    for p in frappe.get_all("Fee Payment", filters={"student": student}, fields=["term", "amount_paid", "class"]):
        paid[p.term] = paid.get(p.term, 0) + flt(p.amount_paid)
        if p["class"]:
            paid_classes.setdefault(p.term, p["class"])

    rows = []
    for term in terms:
        is_due = term.is_due
        student_class = paid_classes.get(term.name) or record_classes.get(term.academic_year)
        if not student_class and (term.academic_year == current_year or not is_due):
            student_class = student_doc.current_class

        amount_due = fee_amounts.get((student_class, term.name))
        total_paid = paid.get(term.name, 0)
        if amount_due is None and not total_paid:
            continue

        amount_due = amount_due or 0
        rows.append(frappe._dict(
            term=term.name,
            term_name=term.term_name,
            academic_year=term.academic_year,
            student_class=student_class,
            is_due=is_due,
            amount_due=amount_due,
            total_paid=total_paid,
            remaining=max(amount_due - total_paid, 0),
            overpaid=max(total_paid - amount_due, 0) if amount_due else 0,
        ))

    return frappe._dict(
        student=student,
        student_name=student_doc.full_name,
        rows=rows,
        balance=sum(r.remaining for r in rows if r.is_due),
    )


def get_term_outstanding(student, term):
    """Amount still payable for one term, including an upcoming term paid early."""
    row = next((r for r in get_fee_statement(student).rows if r.term == term), None)
    return row.remaining if row else 0


def get_class_for_term(student, term):
    row = next((r for r in get_fee_statement(student).rows if r.term == term), None)
    return row.student_class if row else frappe.get_cached_value("Student", student, "current_class")
