"""School identity from Smart School Settings, shown on the portal navbar, the report card, the login page and browser tab
(through Website Settings) and in notification emails."""

import frappe

DEFAULT_NAME = "Smart School"

# Website Settings field -> Smart School Settings field. The login page reads app_name and app_logo,
# every website page (and so the browser tab) reads favicon, and page titles get title_prefix
# ("<school> - Login"; the portal base template sets its own title, so it is not doubled there).
WEBSITE_FIELDS = {
	"app_name": "school_name",
	"app_logo": "school_logo",
	"favicon": "school_logo",
	"title_prefix": "school_name",
}


def get_school_branding():
	settings = frappe.get_cached_doc("Smart School Settings")
	name = (settings.school_name or "").strip() or DEFAULT_NAME
	return frappe._dict(
		name=name,
		initials="".join(word[0] for word in name.split()[:2]).upper(),
		logo=settings.school_logo,
		motto=settings.school_motto,
		address=settings.school_address,
		phone=settings.school_phone,
		email=settings.school_email,
	)


def make_logo_public(settings):
	"""Guests on the login page, parents and email clients cannot open a private file."""
	if not (settings.school_logo or "").startswith("/private/"):
		return
	file = frappe.db.get_value(
		"File",
		{
			"file_url": settings.school_logo,
			"attached_to_doctype": settings.doctype,
			"attached_to_name": settings.name,
		},
	) or frappe.db.get_value("File", {"file_url": settings.school_logo})
	if not file:
		frappe.throw("The logo file was not found; attach it again")
	file = frappe.get_doc("File", file)
	file.is_private = 0
	file.save(ignore_permissions=True)
	settings.school_logo = file.file_url


def sync_website_settings(settings):
	"""Copy the school name and logo to Website Settings. A school field left empty does not touch
	Website Settings, except to clear the value that this school field had put there."""
	before = settings.get_doc_before_save()
	website = frappe.get_single("Website Settings")
	changed = False
	for website_field, school_field in WEBSITE_FIELDS.items():
		value = settings.get(school_field)
		previous = before.get(school_field) if before else None
		if not value and not (previous and website.get(website_field) == previous):
			continue
		if website.get(website_field) != value:
			website.set(website_field, value)
			changed = True
	if changed:
		website.save(ignore_permissions=True)
