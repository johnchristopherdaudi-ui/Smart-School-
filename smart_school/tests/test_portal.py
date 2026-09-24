"""#25/#27: portal pages on the shared base template, guest redirects, parent home page, dashboard and workspaces."""

import json

import frappe

from smart_school.fees import get_term_outstanding
from smart_school.parent_dashboard import get_dashboard
from smart_school.tests.factory import (
	ACCOUNTANT,
	HEADMASTER,
	PARENT_1,
	TEACHER_1,
	SchoolTestCase,
	as_user,
	make_user,
	render,
)
from smart_school.users import set_default_workspace


class TestPortalPages(SchoolTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("Smart School Settings", "enable_demo_payments", 1)

	def test_guest_is_sent_to_login_and_back(self):
		with as_user("Guest"):
			status, _, location = render("parent-portal/results", student=self.s["a"])
		self.assertIn(status, (301, 302))
		self.assertEqual(location, f"/login?redirect-to=%2Fparent-portal%2Fresults%3Fstudent%3D{self.s['a']}")

	def test_parent_home_page(self):
		from frappe.website.utils import get_home_page

		with as_user(PARENT_1):
			frappe.local.flags.home_page = None
			self.assertEqual(get_home_page(), "parent-portal")

	def test_every_page_renders_on_the_base_template(self):
		pages = [
			("parent-portal", {}),
			("parent-portal/student", {"student": self.s["a"]}),
			("parent-portal/results", {"student": self.s["a"]}),
			("parent-portal/fees", {"student": self.s["a"]}),
			("parent-portal/discipline", {"student": self.s["a"]}),
			("parent-portal/announcements", {}),
			("parent-portal/pay", {"student": self.s["a"], "term": "_Test T3"}),
		]
		self.assertGreater(get_term_outstanding(self.s["a"], "_Test T3"), 0)
		with as_user(PARENT_1):
			for path, args in pages:
				with self.subTest(path=path):
					status, body, _ = render(path, **args)
					self.assertEqual(status, 200)
					self.assertEqual(body.count('class="sp-navbar"'), 1)
					self.assertNotIn("navbar-expand", body)  # Frappe's website navbar is not rendered
					is_pay = path.endswith("pay")
					self.assertEqual('class="sp-bell"' in body, not is_pay)
					self.assertEqual(body.count("function toggleNotifDropdown"), 0 if is_pay else 1)
					self.assertNotIn("{{", body)

	def test_dashboard_uses_gentle_alerts_not_risk_scores(self):
		with as_user(PARENT_1):
			dashboard = get_dashboard(frappe.get_doc("Student", self.s["a"]))
			status, body, _ = render("parent-portal", student=self.s["a"])
		self.assertIn("fees", [a.kind for a in dashboard.alerts])
		self.assertEqual(status, 200)
		self.assertNotIn("risk", body.lower())
		self.assertIn("Taarifa kwa mzazi", body)


class TestWorkspaces(SchoolTestCase):
	def sidebar(self, user):
		from frappe.desk.desktop import get_workspace_sidebar_items

		ours = {"Headmaster", "Academics", "Finance", "School Settings"}
		with as_user(user):
			return {p["name"] for p in get_workspace_sidebar_items()["pages"] if p["name"] in ours}

	def test_workspaces_by_role(self):
		self.assertEqual(self.sidebar(TEACHER_1), {"Academics"})
		self.assertEqual(self.sidebar(ACCOUNTANT), {"Finance"})
		self.assertEqual(self.sidebar(HEADMASTER), {"Headmaster", "Academics", "Finance"})

	def test_workspace_pages_load(self):
		from frappe.desk.desktop import get_desktop_page

		with as_user(ACCOUNTANT):
			page = get_desktop_page(json.dumps({"name": "Finance", "title": "Finance", "public": 1}))
		cards = [
			c.get("number_card_name") if hasattr(c, "get") else c.number_card_name
			for c in page["number_cards"]["items"]
		]
		self.assertEqual(set(cards), {"Fees Collected This Term", "Outstanding Fees"})

	def test_default_workspace_per_role(self):
		make_user("_test.own@example.com", "Teacher")
		frappe.db.set_value("User", "_test.own@example.com", "default_workspace", "Tools")
		expected = {
			HEADMASTER: "Headmaster",
			ACCOUNTANT: "Finance",
			TEACHER_1: "Academics",
			"_test.own@example.com": "Tools",
		}
		for user, workspace in expected.items():
			set_default_workspace(user=user)
			self.assertEqual(frappe.db.get_value("User", user, "default_workspace"), workspace, user)
