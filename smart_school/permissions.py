import frappe


def get_teacher_exam_result_permission_query(user):
	if not user:
		user = frappe.session.user

	if "System Manager" in frappe.get_roles(user):
		return None

	if "Teacher" in frappe.get_roles(user):
		teacher = frappe.get_value("Teacher", {"user": user}, "name")
		if teacher:
			return f"`tabExam Result`.`teacher` = {frappe.db.escape(teacher)}"
		else:
			return "1=0"

	return None
