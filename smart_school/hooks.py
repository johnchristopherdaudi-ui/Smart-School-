app_name = "smart_school"
app_title = "Smart School - An Integrated Academic Management System"
app_publisher = "John Christopher Daudi"
app_description = "Integrated academic management system for Tanzanian secondary schools"
app_email = "johnchristopherdaudi@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "smart_school",
# 		"logo": "/assets/smart_school/logo.png",
# 		"title": "Smart School",
# 		"route": "/smart_school",
# 		"has_permission": "smart_school.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/smart_school/css/smart_school.css"
# app_include_js = "/assets/smart_school/js/smart_school.js"

# include js, css files in header of web template
# web_include_css = "/assets/smart_school/css/smart_school.css"
# web_include_js = "/assets/smart_school/js/smart_school.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "smart_school/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_list_js = {
	"Exam Result": "an_intergrated_academic_management_system/doctype/exam_result/exam_result_list.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "smart_school/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
role_home_page = {
	"Parent": "parent-portal",
}

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"smart_school.report_card.get_report_card_data",
		"smart_school.branding.get_school_branding",
	],
}

# Staff land on their role's workspace after login
on_session_creation = ["smart_school.users.set_default_workspace"]

# Installation
# ------------

# before_install = "smart_school.install.before_install"
after_install = "smart_school.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "smart_school.uninstall.before_uninstall"
# after_uninstall = "smart_school.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "smart_school.utils.before_app_install"
# after_app_install = "smart_school.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "smart_school.utils.before_app_uninstall"
# after_app_uninstall = "smart_school.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "smart_school.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["smart_school.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Exam Result": "smart_school.permissions.get_teacher_exam_result_permission_query",
}
# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"smart_school.tasks.calculate_all_risk_scores",
		"smart_school.tasks.generate_performance_insights",
		"smart_school.tasks.create_academic_records_for_ended_years",
		"smart_school.marks_alerts.run_nightly_checks",
		"smart_school.risk_model.refresh_predictions",
	],
	"weekly": [
		"smart_school.risk_model.train_model",
	],
}

# 	"daily": [
# 		"smart_school.tasks.daily"
# 	],
# 	"hourly": [
# 		"smart_school.tasks.hourly"
# 	],
# 	"weekly": [
# 		"smart_school.tasks.weekly"
# 	],
# 	"monthly": [
# 		"smart_school.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "smart_school.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "smart_school.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "smart_school.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["smart_school.utils.before_request"]
# after_request = ["smart_school.utils.after_request"]

# Job Events
# ----------
# before_job = ["smart_school.utils.before_job"]
# after_job = ["smart_school.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"smart_school.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# Fixtures
# --------
# Parent is portal-only: desk_access = 0 keeps guardians as Website Users
fixtures = [{"dt": "Role", "filters": [["name", "=", "Parent"]]}]
