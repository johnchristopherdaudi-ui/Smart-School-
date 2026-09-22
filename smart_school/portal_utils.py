import frappe
from frappe.utils import add_days, nowdate, now_datetime, get_datetime


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
        children.append(student)
    return children


def get_notifications(guardian, children):
    """Rudisha list ya notifications zote (kwa dropdown) + idadi ya 'unseen' (kwa badge)."""
    notifications = []
    unseen_count = 0

    if not children:
        return {"items": notifications, "unseen_count": 0}

    student_names = [c.name for c in children]
    student_map = {c.name: c.full_name for c in children}
    last_seen = get_datetime(guardian.last_announcement_seen) if guardian.last_announcement_seen else None

    # Fee debts - daima zinahesabika kwenye badge mpaka zilipwe
    unpaid = frappe.get_all(
        "Fee Payment",
        filters={"student": ["in", student_names], "balance": [">", 0]},
        fields=["student", "term", "balance"]
    )
    for u in unpaid:
        term_name = frappe.get_cached_value("Term", u.term, "term_name") or u.term
        notifications.append({
            "type": "fee",
            "message": f"{student_map.get(u.student, u.student)}: Deni la {u.balance:,.0f} TZS ({term_name})",
            "link": f"/parent-portal/fees?student={u.student}"
        })
        unseen_count += 1  # fee daima ni "unseen" mpaka ilipwe

    # Announcements - zinahesabika kwenye badge tu kama ni mpya kuliko last_seen
    class_names = list({c.current_class for c in children if c.current_class})
    if class_names:
        recent_announcements = frappe.get_all(
            "Announcement",
            filters={"class": ["in", class_names], "date": [">=", add_days(nowdate(), -30)]},
            fields=["name", "tittle", "class", "creation"],
            order_by="creation desc"
        )
        for a in recent_announcements:
            notifications.append({
                "type": "announcement",
                "message": f"Tangazo jipya: {a.tittle}",
                "link": "/parent-portal/announcements"
            })
            if not last_seen or get_datetime(a.creation) > last_seen:
                unseen_count += 1

    return {"items": notifications, "unseen_count": unseen_count}


@frappe.whitelist()
def mark_announcements_seen():
    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if guardian_name:
        frappe.db.set_value("Guardian", guardian_name, "last_announcement_seen", now_datetime())
        frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def create_payment_request(student, term, amount, provider, phone_number):
    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw("No guardian profile linked to this account")

    guardian = frappe.get_doc("Guardian", guardian_name)
    allowed_students = [row.student for row in guardian.students]
    if student not in allowed_students:
        frappe.throw("Huna ruhusa ya kulipia mwanafunzi huyu")

    log = frappe.new_doc("Payment Gateway Log")
    log.student = student
    log.amount = amount
    log.phone_number = phone_number
    log.provider = provider
    log.status = "Pending"
    log.transaction_reference = frappe.generate_hash(length=10).upper()
    log.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"reference": log.transaction_reference, "term": term}


@frappe.whitelist()
def confirm_demo_payment(reference, term, success):
    log = frappe.get_doc("Payment Gateway Log", {"transaction_reference": reference})

    success = frappe.utils.cint(success)

    if success:
        log.status = "Success"
        log.response_message = "Demo payment completed successfully"
        log.save(ignore_permissions=True)

        fee_payment = frappe.new_doc("Fee Payment")
        fee_payment.student = log.student
        fee_payment.term = term
        fee_payment.amount_paid = log.amount
        fee_payment.payment_date = frappe.utils.today()
        fee_payment.payment_method = log.provider
        fee_payment.insert(ignore_permissions=True)

        log.fee_payment = fee_payment.name
        log.save(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "fee_payment": fee_payment.name}
    else:
        log.status = "Failed"
        log.response_message = "Demo payment failed"
        log.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": False}
