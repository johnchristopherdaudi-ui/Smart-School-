"""Test data for smart_school: one small "_Test" school, created on demand and reused.

Everything is get-or-create, so suites stay independent of any real site data and of each other,
even when a code path under test commits."""

from contextlib import contextmanager
from urllib.parse import urlencode
from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate, today

YEAR = "_Test AY"
TERMS = ("_Test T1", "_Test T2", "_Test T3")  # T3 is the term running today
CLASSES = {"_Test FORM 1": 1, "_Test FORM 2": 2, "_Test FORM 3": 3, "_Test FORM 4": 4}
SUBJECTS = (
	"_T MATH",
	"_T ENGLISH",
	"_T KISWAHILI",
	"_T PHYSICS",
	"_T BIOLOGY",
	"_T HISTORY",
	"_T GEOGRAPHY",
	"_T CIVICS",
)
FEES = {"_Test T1": 600000, "_Test T2": 750000, "_Test T3": 800000}

TEACHER_1 = "_test.teacher1@example.com"  # FORM 1: MATH, ENGLISH
TEACHER_2 = "_test.teacher2@example.com"  # FORM 2: all subjects, class teacher of FORM 2
PARENT_1 = "_test.parent1@example.com"  # two FORM 1 children
PARENT_2 = "_test.parent2@example.com"  # one FORM 2 child
HEADMASTER = "_test.hm@example.com"
ACCOUNTANT = "_test.acc@example.com"


def get_or_insert(doctype, name, values):
	if frappe.db.exists(doctype, name):
		return frappe.get_doc(doctype, name)
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True, set_name=name)


def make_user(email, *roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in roles],
			}
		).insert(ignore_permissions=True)
	return email


def make_school():
	"""Build (or reuse) the whole test school and return a dict of useful names."""
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	start = getdate(add_days(today(), -200))
	get_or_insert(
		"Academic Year", YEAR, {"year": YEAR, "start_date": start, "end_date": add_days(today(), 160)}
	)
	for name, (begin, end) in zip(TERMS, [(-180, -100), (-90, -10), (-5, 80)]):
		get_or_insert(
			"Term",
			name,
			{
				"term_name": f"Term {name[-1]}",
				"academic_year": YEAR,
				"start_date": add_days(today(), begin),
				"end_date": add_days(today(), end),
			},
		)
	for name, level in CLASSES.items():
		get_or_insert("Class", name, {"class_name": name, "level": level})
	for i, name in enumerate(SUBJECTS):
		get_or_insert("Subject", name, {"subject_name": name, "subject_code": f"TC{i}"})
	for class_name in ("_Test FORM 1", "_Test FORM 2"):
		for subject in SUBJECTS:
			if not frappe.db.exists("Class Subject Mapping", {"class": class_name, "subject": subject}):
				frappe.get_doc(
					{
						"doctype": "Class Subject Mapping",
						"class": class_name,
						"subject": subject,
						"subject_scope": "All Combinations",
					}
				).insert(ignore_permissions=True)
	for class_name in ("_Test FORM 1", "_Test FORM 2"):
		for term, amount in FEES.items():
			if not frappe.db.exists("Fee Structure", {"class": class_name, "term": term}):
				frappe.get_doc(
					{"doctype": "Fee Structure", "class": class_name, "term": term, "amount": amount}
				).insert(ignore_permissions=True)

	teacher_1 = make_teacher(
		TEACHER_1, "_Test Teacher One", [("_T MATH", "_Test FORM 1"), ("_T ENGLISH", "_Test FORM 1")]
	)
	teacher_2 = make_teacher(TEACHER_2, "_Test Teacher Two", [(s, "_Test FORM 2") for s in SUBJECTS])
	frappe.db.set_value("Class", "_Test FORM 2", "class_teacher", teacher_2)

	students = {
		"a": make_student("_Test Student A", "_Test FORM 1", "Male"),
		"b": make_student("_Test Student B", "_Test FORM 1", "Female"),
		"c": make_student("_Test Student C", "_Test FORM 1", "Male"),
		"d": make_student("_Test Student D", "_Test FORM 1", "Female"),
		"e": make_student("_Test Student E", "_Test FORM 2", "Female"),
	}
	make_guardian("_Test Parent One", PARENT_1, "+255 754 000 101", [students["a"], students["b"]])
	make_guardian("_Test Parent Two", PARENT_2, "+255 754 000 202", [students["e"]])
	make_user(HEADMASTER, "Headmaster")
	make_user(ACCOUNTANT, "Accountant")
	return frappe._dict(students=students, teacher_1=teacher_1, teacher_2=teacher_2)


def make_teacher(email, full_name, assignments):
	name = frappe.db.get_value("Teacher", {"email": email}, "name")
	if not name:
		doc = frappe.get_doc(
			{
				"doctype": "Teacher",
				"full_name": full_name,
				"email": email,
				"subjects_taught": [{"subject": s, "class": c} for s, c in assignments],
			}
		)
		doc.insert(ignore_permissions=True)
		name = doc.name
	return name


def make_student(full_name, class_name, gender):
	name = frappe.db.get_value("Student", {"full_name": full_name}, "name")
	if not name:
		name = (
			frappe.get_doc(
				{
					"doctype": "Student",
					"full_name": full_name,
					"current_class": class_name,
					"gender": gender,
					"status": "Active",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	return name


def make_guardian(full_name, email, phone, students):
	name = frappe.db.get_value("Guardian", {"email": email}, "name")
	if not name:
		doc = frappe.get_doc(
			{
				"doctype": "Guardian",
				"full_name": full_name,
				"email": email,
				"phone": phone,
				"students": [{"student": s, "relationship": "Guardian"} for s in students],
			}
		)
		doc.insert(ignore_permissions=True)
		name = doc.name
	return name


def make_exam(exam_name, term, class_name, max_marks=100, weight=None, published=0):
	name = frappe.db.get_value("Exam", {"exam_name": exam_name, "term": term, "class": class_name}, "name")
	if not name:
		name = (
			frappe.get_doc(
				{
					"doctype": "Exam",
					"exam_name": exam_name,
					"term": term,
					"class": class_name,
					"max_marks": max_marks,
					"weight": weight,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	frappe.db.set_value("Exam", name, "results_published", published)
	return name


def add_result(student, exam, subject, marks):
	doc = frappe.get_doc(
		{"doctype": "Exam Result", "student": student, "exam": exam, "subject": subject, "marks": marks}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def pay(student, term, amount):
	doc = frappe.get_doc(
		{
			"doctype": "Fee Payment",
			"student": student,
			"term": term,
			"amount_paid": amount,
			"payment_date": today(),
			"payment_method": "Cash",
			"status": "Partial",
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


@contextmanager
def no_commit():
	"""Some endpoints commit; keep everything inside the test transaction."""
	with patch.object(frappe.db, "commit"):
		yield


@contextmanager
def enforce_roles():
	"""frappe.only_for() skips its check while tests run (flags.in_test); turn it back on."""
	previous = frappe.local.flags.in_test
	frappe.local.flags.in_test = False
	try:
		yield
	finally:
		frappe.local.flags.in_test = previous


@contextmanager
def as_user(user):
	previous = frappe.session.user
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user(previous)


def render(path, **args):
	"""Render a website page like a browser request and return (status, body, location)."""
	from frappe.utils import set_request
	from frappe.website.serve import get_response

	set_request(method="GET", path="/" + path, query_string=urlencode(args))
	frappe.local.form_dict = frappe._dict(args)
	response = get_response(path)
	return response.status_code, response.get_data(as_text=True), response.headers.get("Location")


def call(method, **kwargs):
	frappe.local.form_dict = frappe._dict()
	return frappe.call(method, **kwargs)


from frappe.tests.utils import FrappeTestCase  # noqa: E402


class SchoolTestCase(FrappeTestCase):
	"""Base class: builds the "_Test" school once per suite; the suite's changes are rolled back.

	Commits are disabled for the whole suite: under tests Frappe sends emails immediately and the
	email queue commits (frappe.email.doctype.email_queue), which would otherwise persist test data."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		commit_patch = patch.object(frappe.db, "commit")
		commit_patch.start()
		cls.addClassCleanup(commit_patch.stop)
		cls.school = make_school()
		cls.s = cls.school.students

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.flags.mute_emails = True
