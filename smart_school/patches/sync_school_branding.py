import frappe

from smart_school.branding import make_logo_public, sync_website_settings


def execute():
	"""The login page and browser tab now show the school name and logo set before this change."""
	settings = frappe.get_single("Smart School Settings")
	if settings.school_logo:
		make_logo_public(settings)
		settings.db_set("school_logo", settings.school_logo)
	sync_website_settings(settings)
