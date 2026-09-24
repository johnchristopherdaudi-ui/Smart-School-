import frappe


def send_notification(student, message, notification_type="General"):
    guardians = get_guardians_for_student(student)

    for guardian in guardians:
        send_email_to_guardian(guardian, message, notification_type)
        send_sms_to_guardian(guardian, message)
    # Parents are Website Users, so desk Notification Logs are useless to them: the portal bell is the in-app channel


def get_guardians_for_student(student):
    guardian_links = frappe.get_all(
        "Guardian Student Link",
        filters={"student": student},
        fields=["parent"]
    )

    guardian_names = [g.parent for g in guardian_links]

    guardians = frappe.get_all(
        "Guardian",
        filters={"name": ["in", guardian_names]},
        fields=["name", "email", "phone", "user"]
    )

    return guardians


def send_email_to_guardian(guardian, message, notification_type):
    if not guardian.email:
        return

    default_email_account = frappe.get_all("Email Account", filters={"default_outgoing": 1})

    if not default_email_account:
        frappe.logger().info(f"[EMAIL SIMULATION] To: {guardian.email} - Message: {message}")
        return

    try:
        frappe.sendmail(
            recipients=[guardian.email],
            subject=f"Smart School - {notification_type}",
            message=message
        )
    except Exception as e:
        frappe.log_error(f"Failed to send email to {guardian.email}: {str(e)}")


def send_sms_to_guardian(guardian, message):
    if not guardian.phone:
        return

    if not frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
        frappe.logger().info(f"[SMS SIMULATION] To: {guardian.phone} - Message: {message}")
        return

    from frappe.core.doctype.sms_settings.sms_settings import send_sms

    try:
        send_sms([guardian.phone], message)
    except Exception:
        frappe.log_error(title=f"Smart School SMS to {guardian.phone} failed")
