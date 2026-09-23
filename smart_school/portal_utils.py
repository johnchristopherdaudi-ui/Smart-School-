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


def get_remaining_balances(children):
    """Hesabu deni la KWELI la sasa kwa kila (student, term) kwa kujumlisha
    malipo yote na kulinganisha na Fee Structure - si kutegemea record moja."""
    results = []
    for student in children:
        payments = frappe.get_all(
            "Fee Payment",
            filters={"student": student.name},
            fields=["term", "amount_paid"]
        )
        totals = {}
        for p in payments:
            totals[p.term] = totals.get(p.term, 0) + (p.amount_paid or 0)

        for term, total_paid in totals.items():
            fee_structure = frappe.get_all(
                "Fee Structure",
                filters={"class": student.current_class, "term": term},
                fields=["amount"]
            )
            amount_due = fee_structure[0].amount if fee_structure else 0
            remaining = max(amount_due - total_paid, 0)
            if remaining > 0:
                results.append({
                    "student": student.name,
                    "student_name": student.full_name,
                    "term": term,
                    "remaining": remaining
                })
    return results


def get_notifications(guardian, children):
    notifications = []
    unseen_count = 0

    if not children:
        return {"items": notifications, "unseen_count": 0}

    last_seen = get_datetime(guardian.last_announcement_seen) if guardian.last_announcement_seen else None

    for u in get_remaining_balances(children):
        term_name = frappe.get_cached_value("Term", u["term"], "term_name") or u["term"]
        notifications.append({
            "type": "fee",
            "message": f"{u['student_name']}: Deni la {u['remaining']:,.0f} TZS ({term_name})",
            "link": f"/parent-portal/fees?student={u['student']}"
        })
        unseen_count += 1

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


def get_remaining_balance(student, term):
    """Deni la KWELI la sasa kwa (student, term), hesabiwa server-side - si kutegemea input ya mteja."""
    current_class = frappe.get_value("Student", student, "current_class")

    total_paid = sum(
        p or 0
        for p in frappe.get_all(
            "Fee Payment",
            filters={"student": student, "term": term},
            pluck="amount_paid"
        )
    )

    fee_structure = frappe.get_all(
        "Fee Structure",
        filters={"class": current_class, "term": term},
        fields=["amount"]
    )
    amount_due = fee_structure[0].amount if fee_structure else 0

    return max(amount_due - total_paid, 0)


@frappe.whitelist()
def create_payment_request(student, term, provider, phone_number):
    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw("No guardian profile linked to this account")

    guardian = frappe.get_doc("Guardian", guardian_name)
    allowed_students = [row.student for row in guardian.students]
    if student not in allowed_students:
        frappe.throw("Huna ruhusa ya kulipia mwanafunzi huyu")

    remaining = get_remaining_balance(student, term)
    if remaining <= 0:
        frappe.throw("Hakuna deni lililobaki kwa muhula huu")

    log = frappe.new_doc("Payment Gateway Log")
    log.student = student
    log.amount = remaining
    log.phone_number = phone_number
    log.provider = provider
    log.status = "Pending"
    log.transaction_reference = frappe.generate_hash(length=10).upper()
    log.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"reference": log.transaction_reference, "term": term}


@frappe.whitelist()
def confirm_demo_payment(reference, term, success):
    guardian_name = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw("No guardian profile linked to this account", frappe.PermissionError)

    log = frappe.get_doc("Payment Gateway Log", {"transaction_reference": reference})

    guardian = frappe.get_doc("Guardian", guardian_name)
    allowed_students = [row.student for row in guardian.students]
    if log.student not in allowed_students:
        frappe.throw("Huna ruhusa ya kufikia malipo haya", frappe.PermissionError)

    if log.status != "Pending":
        frappe.throw("Muamala huu tayari umeshakamilika")

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
        fee_payment.payment_method = "Mobile Money"
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
