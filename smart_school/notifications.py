import frappe


def send_notification(student, message, notification_type="General"):
    guardians = get_guardians_for_student(student)

    for guardian in guardians:
        send_email_to_guardian(guardian, message, notification_type)
        send_sms_to_guardian(guardian, message)
        create_in_app_notification(guardian, message, notification_type)


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

    api_url = frappe.conf.get("sms_api_url")
    api_key = frappe.conf.get("sms_api_key")

    if not api_url or not api_key:
        frappe.logger().info(f"[SMS SIMULATION] To: {guardian.phone} - Message: {message}")
        return

    try:
        import requests
        payload = {
            "to": guardian.phone,
            "message": message
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        requests.post(api_url, json=payload, headers=headers, timeout=15)
    except Exception as e:
        frappe.log_error(f"Failed to send SMS to {guardian.phone}: {str(e)}")


def create_in_app_notification(guardian, message, notification_type):
    if not guardian.get("user"):
        return

    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": f"Smart School - {notification_type}",
        "for_user": guardian.get("user"),
        "type": "Alert",
        "email_content": message
    }).insert(ignore_permissions=True)