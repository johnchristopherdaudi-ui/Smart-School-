"""Demo data generator: it refuses the wrong sites, is reproducible from a seed, has realistic links between
attendance, discipline and results, and saves a school the app can work with."""

import hashlib
import json
import statistics
from collections import defaultdict
from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from smart_school import demo_data as dd
from smart_school.fees import get_fee_statement
from smart_school.tests.factory import SchoolTestCase

AS_OF = date(2025, 12, 20)  # a finished year: every exam sat and published


def digest(plan):
	data = [plan.students, plan.guardians, plan.teachers, sorted(plan.results.items()), plan.attendance]
	data += [plan.discipline, plan.payments, plan.plants]
	return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()


def term_outcomes(plan):
	"""{(student, term index): (average, positive)} with positive = Division IV/0 or 3+ subjects with F."""
	exams = {e["key"]: e for e in plan.exams}
	index = {t["name"]: t["index"] for t in plan.terms}
	by = defaultdict(lambda: defaultdict(list))
	for (key, student, subject), (marks, _) in plan.results.items():
		e = exams[key]
		by[(student, index[e["term"]])][subject].append((marks / e["max_marks"] * 100, e["weight"]))

	points = lambda score: 1 if score >= 75 else 2 if score >= 65 else 3 if score >= 45 else 4 if score >= 30 else 5
	outcomes = {}
	for k, subjects in by.items():
		scores = [dd.half_up(sum(p * w for p, w in v) / sum(w for _, w in v)) for v in subjects.values()]
		best = sorted(points(s) for s in scores)[:7]
		fails = sum(1 for s in scores if s < 30)
		outcomes[k] = (statistics.mean(scores), (len(best) == 7 and sum(best) >= 26) or fails >= 3)
	return outcomes


def absence_rates(plan):
	index = {t["name"]: t["index"] for t in plan.terms}
	days = defaultdict(lambda: [0, 0.0])
	for student, _, status, term, _ in plan.attendance:
		d = days[(student, index[term])]
		d[0] += 1
		d[1] += {"Absent": 1, "Late": 0.5}.get(status, 0)
	return {k: missed / n for k, (n, missed) in days.items()}


class TestDemoPlan(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.plan = dd.build_plan(seed=42, as_of=AS_OF)

	def test_same_seed_same_school(self):
		small = dict(as_of=AS_OF, students_per_form=10)
		self.assertEqual(digest(dd.build_plan(seed=3, **small)), digest(dd.build_plan(seed=3, **small)))
		self.assertNotEqual(digest(dd.build_plan(seed=3, **small)), digest(dd.build_plan(seed=4, **small)))

	def test_size_and_calendar(self):
		plan = self.plan
		self.assertEqual(plan.years, [2023, 2024, 2025])
		self.assertEqual(len(plan.terms), 9)
		active = sum(1 for s in plan.students if (s["key"], 2025) in plan.enrolments and s["status"] == "Active")
		self.assertTrue(260 <= active <= 320, active)
		self.assertTrue(all(e["sat"] and e["published_on"] for e in plan.exams))
		self.assertEqual({s["status"] for s in plan.students}, {"Active", "Graduated", "Dropped", "Transferred"})
		# class teachers teach in their own class
		for form, key in plan.class_teachers.items():
			teacher = next(t for t in plan.teachers if t["key"] == key)
			self.assertIn(form, [f for _, f in teacher["assignments"]])

	def test_attendance_is_linked_to_results_now_and_next_term(self):
		outcomes, rates = term_outcomes(self.plan), absence_rates(self.plan)
		same = [(rates[k], avg) for k, (avg, _) in outcomes.items() if k in rates]
		xs, ys = zip(*same)
		self.assertLess(statistics.correlation(xs, ys), -0.3)

		# Among students not yet at risk, the most absent quarter becomes at risk next term far more often
		pairs = sorted(
			(rates[(s, t)], outcomes[(s, t + 1)][1])
			for (s, t), (_, positive) in outcomes.items()
			if not positive and (s, t + 1) in outcomes and (s, t) in rates
		)
		quarter = len(pairs) // 4
		least = statistics.mean(p for _, p in pairs[:quarter])
		most = statistics.mean(p for _, p in pairs[-quarter:])
		self.assertGreater(most, least + 0.08)

		positives = statistics.mean(p for _, p in outcomes.values())
		self.assertTrue(0.2 <= positives <= 0.45, positives)

	def test_gender_has_no_effect(self):
		gender = {s["key"]: s["gender"] for s in self.plan.students}
		by_gender = defaultdict(list)
		for (student, _), (_, positive) in term_outcomes(self.plan).items():
			by_gender[gender[student]].append(positive)
		self.assertLess(abs(statistics.mean(by_gender["Male"]) - statistics.mean(by_gender["Female"])), 0.08)

	def test_plants_depend_on_the_date(self):
		self.assertTrue(all(p["done"] for p in self.plan.plants))
		swapped = next(p for p in self.plan.plants if p["alert_type"] == "Unusual Student Change")
		self.assertEqual(len(set(swapped["students"])), 4)
		early = dd.build_plan(seed=42, as_of=date(2025, 9, 1), students_per_form=10)
		not_done = sorted(p["alert_type"] for p in early.plants if not p["done"])
		self.assertEqual(not_done, ["Many Zero Marks", "Unusual Student Change"])  # Term 3 mid-term not sat yet


class TestDemoGuard(SchoolTestCase):
	def assert_refused(self, site, conf=None):
		with patch.object(frappe.local, "site", site), patch.dict(frappe.conf, conf or {}):
			self.assertRaises(frappe.ValidationError, dd.assert_demo_site)
			self.assertRaises(frappe.ValidationError, dd.generate, seed=1)

	def test_refuses_jonbale_other_sites_and_a_site_with_data(self):
		self.assert_refused("jonbale")
		self.assert_refused("jonbale", {"allow_demo_data": 1})  # never, whatever the config says
		self.assert_refused("test.localhost")
		self.assert_refused("demo.localhost")  # this site already has students
		self.assertEqual(frappe.db.count("Academic Year", {"name": "2024"}), 0)

	def test_refuses_a_site_that_is_not_migrated(self):
		self.assertEqual(dd.pending_patches(), [])  # the test site is migrated
		with (
			patch.object(frappe.local, "site", "demo.localhost"),
			patch.object(frappe.db, "count", return_value=0),  # as if the site were empty
			patch("smart_school.demo_data.pending_patches", return_value=["smart_school.patches.x"]),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "migrate"):
				dd.assert_demo_site()


	def test_many_users_are_not_throttled(self):
		from smart_school.users import ensure_user_with_role

		with patch.dict(frappe.local.conf, {"throttle_user_limit": 0}):
			user = dd.make_user("_test.not.throttled@example.com", "Not Throttled", "Parent")
			# one user created this hour is already over the limit for the normal path
			self.assertRaises(
				frappe.ValidationError, ensure_user_with_role, "_test.throttled@example.com", "T", "Parent", False
			)
		self.assertIn("Parent", frappe.get_roles(user))
		self.assertFalse(frappe.flags.in_import)


class TestDemoWrite(SchoolTestCase):
	"""A small school saved through the app (the test site's own data stays untouched and is rolled back)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.flags.mute_emails = True
		cls.plan = dd.build_plan(seed=11, as_of=AS_OF, students_per_form=8)
		cls.manifest = dd.write_plan(cls.plan)
		names = [s["full_name"] for s in cls.plan.students]
		cls.students = frappe.get_all("Student", filters={"full_name": ["in", names]}, pluck="name")

	def test_counts_match_the_plan(self):
		plan, students = self.plan, self.students
		self.assertEqual(len(students), len(plan.students))
		self.assertEqual(
			frappe.db.count("Exam Result", {"docstatus": 1, "student": ["in", students]}), len(plan.results)
		)
		self.assertEqual(frappe.db.count("Attendance", {"student": ["in", students]}), len(plan.attendance))
		self.assertEqual(
			frappe.db.count("Discipline Record", {"student": ["in", students]}), len(plan.discipline)
		)
		self.assertEqual(
			frappe.db.count("Fee Payment", {"docstatus": 1, "student": ["in", students]}), len(plan.payments)
		)
		pairs = {(s, e["term"]) for (k, s, _) in plan.results for e in plan.exams if e["key"] == k}
		self.assertEqual(frappe.db.count("Student Term Result", {"student": ["in", students]}), len(pairs))
		# Academic records for the two finished years, none yet for the last one
		records = frappe.get_all("Student Academic Record", filters={"student": ["in", students]}, pluck="academic_year")
		self.assertEqual(set(records), {"2023", "2024"})

	def test_people_get_the_right_users(self):
		teacher = frappe.get_value("Teacher", {"email": f"teacher01@{dd.DOMAIN}"}, "user")
		self.assertIn("Teacher", frappe.get_roles(teacher))
		self.assertIn("Headmaster", frappe.get_roles(self.manifest["headmaster"]))
		parent = frappe.get_all("Guardian", filters={"user": ["like", f"%@{dd.DOMAIN}"]}, pluck="user", limit=1)[0]
		self.assertEqual(frappe.db.get_value("User", parent, "user_type"), "Website User")

	def test_integrity_plants_went_through_the_app(self):
		plants = {p["alert_type"]: p for p in self.manifest["plants"]}
		for alert_type in ("Changed After Publish", "Results Unpublished", "Entered By Unassigned User"):
			self.assertTrue(plants[alert_type]["detected"], alert_type)

		unpublished = plants["Results Unpublished"]["exam"]
		self.assertEqual(frappe.db.get_value("Exam", unpublished, "results_published"), 0)
		self.assertTrue(frappe.db.get_value("Exam", unpublished, "first_published_on"))
		changed = frappe.get_all(
			"Marks Alert", filters={"alert_type": "Changed After Publish"}, pluck="related_user"
		)
		self.assertIn(self.manifest["headmaster"], changed)  # the Headmaster's own change is flagged too

	def test_students_who_left_have_an_exit_date_and_no_later_fees(self):
		left = frappe.get_all(
			"Student",
			filters={"name": ["in", self.students], "status": ["!=", "Active"]},
			fields=["name", "exit_date"],
		)
		self.assertTrue(left)
		self.assertTrue(all(s.exit_date and s.exit_date.month == 11 for s in left))  # end of Term 3
		for s in left:
			rows = get_fee_statement(s.name).rows
			self.assertTrue(all(frappe.db.get_value("Term", r.term, "start_date") < s.exit_date for r in rows))
		self.assertFalse(
			frappe.db.count("Student", {"name": ["in", self.students], "status": "Active", "exit_date": ["is", "set"]})
		)

	def test_demo_parent_has_more_than_one_active_child(self):
		parent = self.manifest["demo_parent"]
		self.assertTrue(parent)
		active = frappe.db.count("Student", {"name": ["in", parent["children"]], "status": "Active"})
		self.assertGreater(active, 1)
		self.assertIn("Parent", frappe.get_roles(parent["user"]))

	def test_fee_payments_follow_the_app_rules(self):
		payment = frappe.get_all(
			"Fee Payment",
			filters={"docstatus": 1, "student": ["in", self.students]},
			fields=["name", "receipt_number", "class", "status", "payment_date"],
			order_by="payment_date asc",
			limit=1,
		)[0]
		self.assertEqual(payment.receipt_number, payment.name)
		self.assertTrue(payment.name.startswith(f"RCPT-{payment.payment_date.year}-"))
		self.assertTrue(payment["class"].startswith("FORM "))
		self.assertIn(payment.status, ("Paid", "Partial"))
