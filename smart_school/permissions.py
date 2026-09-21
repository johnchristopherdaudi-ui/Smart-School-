import frappe


def get_teacher_exam_result_permission_query(user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user):
        return None

    if "Teacher" in frappe.get_roles(user):
        teacher = frappe.get_value("Teacher", {"user": user}, "name")
        if teacher:
            return f"`tabExam Result`.`teacher` = '{teacher}'"
        else:
            return "1=0"

    return None


def get_guardian_student_term_result_permission_query(user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user):
        return None

    if "Parent" in frappe.get_roles(user):
        guardian = frappe.get_value("Guardian", {"user": user}, "name")
        if guardian:
            students = frappe.get_all(
                "Guardian Student Link",
                filters={"parent": guardian},
                pluck="student"
            )
            if students:
                student_list = "', '".join(students)
                return f"`tabStudent Term Result`.`student` in ('{student_list}')"
            else:
                return "1=0"
        else:
            return "1=0"

    return None


def get_guardian_student_permission_query(user):
    if not user:
        user = frappe.session.user

    if "System Manager" in frappe.get_roles(user):
        return None

    if "Parent" in frappe.get_roles(user):
        guardian = frappe.get_value("Guardian", {"user": user}, "name")
        if guardian:
            students = frappe.get_all(
                "Guardian Student Link",
                filters={"parent": guardian},
                pluck="student"
            )
            if students:
                student_list = "', '".join(students)
                return f"`tabStudent`.`name` in ('{student_list}')"
            else:
                return "1=0"
        else:
            return "1=0"

    return None