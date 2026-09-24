import frappe
from frappe.utils import escape_html

from smart_school.branding import get_school_branding


def send_notification(student, message, notification_type="General"):
	guardians = get_guardians_for_student(student)

	for guardian in guardians:
		send_email_to_guardian(guardian, message, notification_type)
		send_sms_to_guardian(guardian, message)
	# Parents are Website Users, so desk Notification Logs are useless to them: the portal bell is the in-app channel


def get_guardians_for_student(student):
	guardian_links = frappe.get_all("Guardian Student Link", filters={"student": student}, fields=["parent"])

	guardian_names = [g.parent for g in guardian_links]

	guardians = frappe.get_all(
		"Guardian", filters={"name": ["in", guardian_names]}, fields=["name", "email", "phone", "user"]
	)

	return guardians


def send_email_to_guardian(guardian, message, notification_type):
	if not guardian.email:
		return

	if not has_outgoing_email_account():
		frappe.logger().info(f"[EMAIL SIMULATION] To: {guardian.email} - Message: {message}")
		return

	school = get_school_branding()
	try:
		frappe.sendmail(
			recipients=[guardian.email],
			subject=f"{school.name} - {notification_type}",
			message=get_email_body(message, school),
			header=[escape_html(school.name), "blue"],  # the header template does not escape
		)
	except Exception as e:
		frappe.log_error(f"Failed to send email to {guardian.email}: {str(e)}")


def has_outgoing_email_account():
	return bool(frappe.get_all("Email Account", filters={"default_outgoing": 1}))


def get_email_body(message, school):
	"""The notification text, signed with the school's name and contacts."""
	signature = [escape_html(school.name)]
	contacts = " · ".join(escape_html(c) for c in (school.phone, school.email) if c)
	if contacts:
		signature.append(contacts)
	return f"<p>{escape_html(message)}</p><p>Wasalaam,<br>{'<br>'.join(signature)}</p>"


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
