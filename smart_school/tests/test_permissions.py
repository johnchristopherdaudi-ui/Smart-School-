"""Batch 1 (#2, #3, #6) and later permission rules: Guest, Parent and Teacher reach only what they may."""

import frappe
import frappe.client

from smart_school.tests.factory import (
	PARENT_1,
	PARENT_2,
	TEACHER_1,
	TEACHER_2,
	SchoolTestCase,
	add_result,
	as_user,
	call,
	make_exam,
)


class TestGuestAndParentPermissions(SchoolTestCase):
	def test_guest_cannot_read_or_approve_admissions(self):
		frappe.set_user("Administrator")
		admission = frappe.get_doc(
			{
				"doctype": "Student Admission",
				"full_name": "_Test Applicant",
				"date_of_birth": "2012-01-01",
				"parent_name": "_Test Parent",
				"phone_number": "+255 754 000 303",
				"class_applying": "_Test FORM 1",
			}
		).insert(ignore_permissions=True)
		with as_user("Guest"):
			self.assertRaises(frappe.PermissionError, frappe.client.get_list, "Student Admission")
			self.assertRaises(frappe.PermissionError, frappe.client.get, "Student Admission", admission.name)
			doc = frappe.get_doc("Student Admission", admission.name)
			doc.status = "Approved"
			# even with permissions bypassed, only Headmaster / System Manager may change the status
			self.assertRaises(frappe.PermissionError, doc.save, ignore_permissions=True)

	def test_approval_needs_a_certificate_or_verification(self):
		frappe.set_user("Administrator")
		doc = frappe.get_doc(
			{
				"doctype": "Student Admission",
				"full_name": "_Test Applicant Two",
				"date_of_birth": "2012-01-01",
				"parent_name": "_Test Parent",
				"phone_number": "+255 754 000 101",
				"class_applying": "_Test FORM 1",
			}
		).insert(ignore_permissions=True)
		doc.status = "Approved"
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()
		doc.birth_certificate_verified = 1
		doc.status = "Approved"
		doc.save()
		# the applicant's phone matches Parent One, so the new student joins that guardian
		guardian = frappe.get_doc("Guardian", {"email": PARENT_1})
		self.assertIn(doc.student, [row.student for row in guardian.students])

	def test_parent_has_no_doctype_access(self):
		with as_user(PARENT_1):
			for doctype in (
				"Guardian",
				"Fee Payment",
				"Attendance",
				"Student",
				"Student Term Result",
				"Exam Result",
				"Announcement",
				"Fee Structure",
				"Class",
				"Subject",
			):
				self.assertRaises(frappe.PermissionError, frappe.client.get_list, doctype)
			self.assertRaises(frappe.PermissionError, frappe.client.get, "Student", self.s["e"])

	def test_parent_is_website_user(self):
		self.assertEqual(frappe.db.get_value("User", PARENT_1, "user_type"), "Website User")

	def test_student_photo_only_for_own_children(self):
		with as_user(PARENT_2):
			self.assertRaises(
				frappe.PermissionError,
				call,
				"smart_school.portal_utils.get_student_photo",
				student=self.s["a"],
			)


class TestTeacherPermissions(SchoolTestCase):
	def test_teacher_sees_only_own_exam_results(self):
		exam = make_exam("_Test Perm Exam", "_Test T2", "_Test FORM 1")
		add_result(self.s["a"], exam, "_T MATH", 50)  # teacher 1's subject
		frappe.set_user("Administrator")
		exam_2 = make_exam("_Test Perm Exam 2", "_Test T2", "_Test FORM 2")
		add_result(self.s["e"], exam_2, "_T MATH", 60)  # teacher 2's subject
		with as_user(TEACHER_1):
			teachers = {
				r.teacher for r in frappe.get_list("Exam Result", fields=["teacher"], limit_page_length=0)
			}
		self.assertEqual(teachers, {self.school.teacher_1})

	def test_teacher_cannot_set_teacher_field(self):
		exam = make_exam("_Test Perm Exam", "_Test T2", "_Test FORM 1")
		with as_user(TEACHER_1):
			doc = frappe.get_doc(
				{
					"doctype": "Exam Result",
					"student": self.s["b"],
					"exam": exam,
					"subject": "_T ENGLISH",
					"marks": 40,
					"teacher": self.school.teacher_2,
				}
			).insert()
		self.assertEqual(doc.teacher, self.school.teacher_1)

	def test_comments_by_their_owners_only(self):
		exam = make_exam("_Test Comment Exam", "_Test T2", "_Test FORM 2")
		add_result(self.s["e"], exam, "_T MATH", 70)
		name = frappe.db.get_value(
			"Student Term Result", {"student": self.s["e"], "term": "_Test T2"}, "name"
		)

		def write(user, field, value):
			with as_user(user):
				doc = frappe.get_doc("Student Term Result", name)
				doc.set(field, value)
				doc.save()

		write(TEACHER_2, "class_teacher_comment", "Good progress")  # class teacher of FORM 2
		self.assertRaises(frappe.PermissionError, write, TEACHER_1, "class_teacher_comment", "Not my class")
		self.assertRaises(
			frappe.PermissionError, write, TEACHER_2, "headmaster_comment", "Not the headmaster"
		)
		self.assertRaises(frappe.ValidationError, write, TEACHER_2, "average", 99)
