"""School name and logo from Smart School Settings: portal navbar, Website Settings (login page, browser tab)
and notification emails."""

from pathlib import Path
from unittest.mock import patch

import frappe

from smart_school.notifications import send_email_to_guardian
from smart_school.tests.factory import PARENT_1, SchoolTestCase, as_user, render

SCHOOL = {
	"school_name": "Shule ya Mary & Joseph",  # stored as typed; "<" and ">" would be sanitized on save
	"school_phone": "0755 000 111",
	"school_email": "info@example.com",
}


def clean_up_after_rollback():
	"""Website Settings and File rollbacks happen after the tests: clear what the database cannot roll back."""
	frappe.clear_cache()
	for folder in ("public", "private"):
		for path in Path(frappe.get_site_path(folder, "files")).glob("_test_logo_*"):
			path.unlink()


class TestBranding(SchoolTestCase):
	@classmethod
	def setUpClass(cls):
		# Registered first so it runs last, after the rollback (which moves a logo made public back to private/files)
		cls.addClassCleanup(clean_up_after_rollback)
		super().setUpClass()

	def setUp(self):
		super().setUp()
		self.settings = frappe.get_single("Smart School Settings")
		original = {f: self.settings.get(f) for f in (*SCHOOL, "school_logo")}
		# The cached settings outlive the rollback: save the original values back
		self.addCleanup(self.save_settings, **original)

	def save_settings(self, **values):
		settings = frappe.get_single("Smart School Settings")
		settings.update(values)
		settings.save(ignore_permissions=True)
		return settings

	def make_logo(self, is_private):
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"_test_logo_{frappe.generate_hash(length=6)}.png",
				"content": b"not really a png",
				"is_private": is_private,
				"attached_to_doctype": "Smart School Settings",
				"attached_to_name": "Smart School Settings",
				"attached_to_field": "school_logo",
			}
		).insert(ignore_permissions=True)
		return file

	def navbar(self):
		with as_user(PARENT_1):
			status, body, _ = render("parent-portal")
		self.assertEqual(status, 200)
		start = body.index('class="sp-brand"')
		return body[start : body.index("</a>", start)], body

	def test_portal_navbar_defaults_to_smart_school(self):
		self.save_settings(school_name=None, school_logo=None)
		brand, body = self.navbar()
		self.assertIn('<span class="sp-logo">SS</span> Smart School', brand)
		self.assertIn("<title>Smart School</title>", body)

	def test_portal_navbar_and_tab_show_school(self):
		logo = self.make_logo(is_private=0).file_url
		self.save_settings(**SCHOOL, school_logo=logo)
		brand, body = self.navbar()
		self.assertIn(f'<img src="{logo}" class="sp-logo"', brand)
		self.assertIn("Shule ya Mary &amp; Joseph", brand)
		# title_prefix is set too, but the portal title is not doubled
		self.assertIn("<title>Shule ya Mary &amp; Joseph</title>", body)
		self.assertRegex(body, rf'rel="shortcut icon"\s+href="{logo}"')  # favicon

	def test_login_page_and_tab(self):
		logo = self.make_logo(is_private=0).file_url
		self.save_settings(**SCHOOL, school_logo=logo)
		with as_user("Guest"):
			status, body, _ = render("login")
		self.assertEqual(status, 200)
		# Frappe's login page prints the title and app name unescaped
		self.assertIn("<title>Shule ya Mary & Joseph - Login</title>", body)
		self.assertIn("Login to Shule ya Mary & Joseph", body)
		self.assertIn(f'<img class="app-logo" src="{logo}"', body)
		self.assertRegex(body, rf'rel="shortcut icon"\s+href="{logo}"')

	def test_website_settings_follow_school(self):
		self.save_settings(school_name=None, school_logo=None)
		frappe.db.set_single_value("Website Settings", "app_name", "Set By Hand")
		self.save_settings(school_name=None)
		self.assertEqual(frappe.db.get_single_value("Website Settings", "app_name"), "Set By Hand")

		logo = self.make_logo(is_private=0).file_url
		self.save_settings(school_name="Shule Ya Majaribio", school_logo=logo)
		website = frappe.get_single("Website Settings")
		self.assertEqual(
			(website.app_name, website.app_logo, website.favicon, website.title_prefix),
			("Shule Ya Majaribio", logo, logo, "Shule Ya Majaribio"),
		)

		# Clearing the school fields clears what they had put in Website Settings
		self.save_settings(school_name=None, school_logo=None)
		website = frappe.get_single("Website Settings")
		self.assertEqual(
			(website.app_name, website.app_logo, website.favicon, website.title_prefix),
			(None, None, None, None),
		)

	def test_private_logo_is_made_public(self):
		file = self.make_logo(is_private=1)
		self.assertTrue(file.file_url.startswith("/private/files/"))
		settings = self.save_settings(school_logo=file.file_url)
		self.assertEqual(settings.school_logo, f"/files/{file.file_name}")
		self.assertEqual(frappe.db.get_value("File", file.name, "is_private"), 0)
		self.assertEqual(frappe.db.get_single_value("Website Settings", "favicon"), settings.school_logo)

	def test_email_subject_header_and_signature(self):
		self.save_settings(**SCHOOL)
		guardian = frappe._dict(email="_test.parent1@example.com")
		with (
			patch("smart_school.notifications.has_outgoing_email_account", return_value=True),
			patch("frappe.sendmail") as sendmail,
		):
			send_email_to_guardian(guardian, "Malipo ya 1,000 TZS <yamepokelewa>.", "Fee Payment")
		kwargs = sendmail.call_args.kwargs
		self.assertEqual(kwargs["subject"], "Shule ya Mary & Joseph - Fee Payment")
		self.assertEqual(kwargs["header"], ["Shule ya Mary &amp; Joseph", "blue"])
		self.assertEqual(
			kwargs["message"],
			"<p>Malipo ya 1,000 TZS &lt;yamepokelewa&gt;.</p>"
			"<p>Wasalaam,<br>Shule ya Mary &amp; Joseph<br>0755 000 111 · info@example.com</p>",
		)
