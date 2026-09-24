import mimetypes
import re
from urllib.parse import urlencode

import frappe
from frappe.utils import add_days, flt, nowdate, now_datetime, get_datetime

from smart_school.an_intergrated_academic_management_system.doctype.smart_school_settings.smart_school_settings import (
    demo_payments_enabled,
)
from smart_school.fees import get_fee_statement, get_term_outstanding


def get_logged_in_guardian():
    if frappe.session.user == "Guest":
        frappe.throw("Please login to view this page", frappe.PermissionError)

    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw("No guardian profile linked to this account")

    return frappe.get_doc("Guardian", guardian_name)


def get_children(guardian):
    children = []
    for row in guardian.students:
        student = frappe.get_doc("Student", row.student)
        parts = (student.full_name or "").split()
        student.initials = "".join([p[0].upper() for p in parts[:2]]) if parts else "?"
        student.photo_url = get_student_photo_url(student)
        children.append(student)
    return children


def get_student_photo_url(student):
    """Parents have no Student permission, so private photos are served through get_student_photo."""
    if not student.photo or not student.photo.startswith("/private/"):
        return student.photo
    return "/api/method/smart_school.portal_utils.get_student_photo?" + urlencode({"student": student.name})


@frappe.whitelist()
def get_student_photo(student):
    guardian = get_logged_in_guardian()
    if student not in [row.student for row in guardian.students]:
        frappe.throw("Huna ruhusa ya kuona picha hii", frappe.PermissionError)

    photo = frappe.db.get_value("Student", student, "photo")
    file_name = photo and frappe.db.get_value(
        "File", {"file_url": photo, "attached_to_doctype": "Student", "attached_to_name": student}, "name"
    )
    if not file_name:
        raise frappe.DoesNotExistError

    file_doc = frappe.get_doc("File", file_name)
    if not (mimetypes.guess_type(file_doc.file_name)[0] or "").startswith("image/"):
        raise frappe.DoesNotExistError

    frappe.local.response.filename = file_doc.file_name
    frappe.local.response.filecontent = file_doc.get_content()
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"


def get_performance_insight(class_name):
    """Pata Performance Insight ya karibuni zaidi kwa class hii."""
    if not class_name:
        return None

    insight = frappe.get_all(
        "Performance Insight",
        filters={"class": class_name},
        fields=["message", "change_percentage", "date_generated"],
        order_by="date_generated desc",
        limit=1
    )
    return insight[0] if insight else None


def get_notifications(guardian, children):
    notifications = []
    unseen_count = 0

    if not children:
        return {"items": notifications, "unseen_count": 0}

    last_seen = get_datetime(guardian.last_announcement_seen) if guardian.last_announcement_seen else None

    for child in children:
        statement = get_fee_statement(child.name)
        for row in statement.rows:
            if row.is_due and row.remaining > 0:
                notifications.append({
                    "type": "fee",
                    "message": f"{statement.student_name}: Deni la {row.remaining:,.0f} TZS ({row.term_name})",
                    "link": "/parent-portal/fees?" + urlencode({"student": child.name})
                })
                unseen_count += 1

    class_names = list({c.current_class for c in children if c.current_class})
    for a in get_announcements(class_names, since=add_days(nowdate(), -30)):
        notifications.append({
            "type": "announcement",
            "message": f"Tangazo jipya: {a.title}",
            "link": "/parent-portal/announcements"
        })
        if not last_seen or get_datetime(a.creation) > last_seen:
            unseen_count += 1

    # Matokeo mapya: Exams zilizochapishwa ndani ya siku 30 ambazo watoto wana matokeo
    child_names = {c.name: c.full_name for c in children}
    for exam in frappe.get_all(
        "Exam",
        filters={"results_published": 1, "published_on": [">=", add_days(nowdate(), -30)]},
        fields=["name", "exam_name", "published_on"],
        order_by="published_on desc",
    ):
        students = frappe.get_all(
            "Exam Result",
            filters={"exam": exam.name, "student": ["in", list(child_names)], "docstatus": 1},
            pluck="student",
            distinct=True,
        )
        for student in students:
            notifications.append({
                "type": "result",
                "message": f"Matokeo mapya ya {exam.exam_name}: {child_names[student]}",
                "link": "/parent-portal/results?" + urlencode({"student": student})
            })
            if not last_seen or get_datetime(exam.published_on) > last_seen:
                unseen_count += 1

    return {"items": notifications, "unseen_count": unseen_count}


def get_announcements(class_names, since=None, fields=("name", "title", "creation")):
    """Announcements for the whole school plus those addressed to any of these classes, newest first."""
    names = set(frappe.get_all("Announcement", filters={"audience": "All School"}, pluck="name"))
    if class_names:
        names.update(frappe.get_all(
            "Announcement Class", filters={"parenttype": "Announcement", "class": ["in", class_names]}, pluck="parent"
        ))
    if not names:
        return []

    filters = {"name": ["in", list(names)]}
    if since:
        filters["date"] = [">=", since]
    return frappe.get_all("Announcement", filters=filters, fields=list(fields), order_by="date desc, creation desc")


@frappe.whitelist()
def mark_announcements_seen():
    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if guardian_name:
        frappe.db.set_value("Guardian", guardian_name, "last_announcement_seen", now_datetime())
        frappe.db.commit()
    return {"success": True}


def get_payment_providers():
    """Provider options come from the doctype, so the portal dropdown cannot drift from it."""
    return frappe.get_meta("Payment Gateway Log").get_field("provider").options.split("\n")


def normalize_tz_mobile(phone):
    """Return the number as 2556XXXXXXXX / 2557XXXXXXXX, or None if it is not a Tanzanian mobile number."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10 and digits.startswith("0"):
        digits = "255" + digits[1:]
    elif len(digits) == 9:
        digits = "255" + digits
    return digits if re.fullmatch(r"255[67]\d{8}", digits) else None


def assert_demo_payments_enabled():
    if not demo_payments_enabled():
        frappe.throw("Malipo kwa simu hayajawezeshwa kwa sasa. Wasiliana na shule.", frappe.PermissionError)


@frappe.whitelist()
def create_payment_request(student, term, provider, phone_number, amount=None):
    assert_demo_payments_enabled()

    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw("No guardian profile linked to this account")

    guardian = frappe.get_doc("Guardian", guardian_name)
    allowed_students = [row.student for row in guardian.students]
    if student not in allowed_students:
        frappe.throw("Huna ruhusa ya kulipia mwanafunzi huyu")

    if not term or not frappe.db.exists("Term", term):
        frappe.throw("Muhula (term) haupo")

    if provider not in get_payment_providers():
        frappe.throw("Mtoa huduma wa malipo si sahihi")

    phone = normalize_tz_mobile(phone_number)
    if not phone:
        frappe.throw("Namba ya simu si sahihi. Tumia mfano 07XXXXXXXX au 2557XXXXXXXX")

    remaining = get_term_outstanding(student, term)
    if remaining <= 0:
        frappe.throw("Hakuna deni lililobaki kwa muhula huu")

    # Whole shillings: Fee Payment.amount_paid is an Int field
    amount = flt(amount, 0) if amount not in (None, "") else remaining
    if not 0 < amount <= remaining:
        frappe.throw(f"Kiasi lazima kiwe zaidi ya 0 na kisizidi deni la {remaining:,.0f} TZS")

    log = frappe.new_doc("Payment Gateway Log")
    log.student = student
    log.term = term
    log.amount = amount
    log.phone_number = phone
    log.provider = provider
    log.status = "Pending"
    log.transaction_reference = frappe.generate_hash(length=10).upper()
    log.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"reference": log.transaction_reference}


@frappe.whitelist()
def confirm_demo_payment(reference, success):
    assert_demo_payments_enabled()

    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw("No guardian profile linked to this account", frappe.PermissionError)

    log_name = frappe.db.get_value("Payment Gateway Log", {"transaction_reference": reference}, "name")
    if not log_name:
        frappe.throw("Muamala haupo", frappe.DoesNotExistError)

    # Lock the row so a double click or refresh cannot confirm the same request twice
    log = frappe.get_doc("Payment Gateway Log", log_name, for_update=True)

    guardian = frappe.get_doc("Guardian", guardian_name)
    allowed_students = [row.student for row in guardian.students]
    if log.student not in allowed_students:
        frappe.throw("Huna ruhusa ya kufikia malipo haya", frappe.PermissionError)

    if log.status != "Pending":
        frappe.throw("Muamala huu tayari umeshakamilika")

    success = frappe.utils.cint(success)

    # Another request may have paid this term since this one was created
    if success and log.amount > get_term_outstanding(log.student, log.term):
        success = 0
        log.response_message = "Kiasi kinazidi deni lililobaki kwa muhula huu"

    if success:
        log.status = "Success"
        log.response_message = "Demo payment completed successfully"
        log.save(ignore_permissions=True)

        fee_payment = frappe.new_doc("Fee Payment")
        fee_payment.student = log.student
        fee_payment.term = log.term
        fee_payment.amount_paid = log.amount
        fee_payment.payment_date = frappe.utils.today()
        fee_payment.payment_method = "Mobile Money"
        fee_payment.receipt_number = log.transaction_reference
        fee_payment.insert(ignore_permissions=True)

        log.fee_payment = fee_payment.name
        log.save(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "fee_payment": fee_payment.name}
    else:
        log.status = "Failed"
        log.response_message = log.response_message or "Demo payment failed"
        log.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": False, "message": log.response_message}
