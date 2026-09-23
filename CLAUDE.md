# SMART SCHOOL — project context for Claude Code

## What this app is
`smart_school` is a Frappe v15 custom app: "An Integrated Academic Management System" for Tanzanian
secondary schools (O-level / CSEE and A-level / ACSEE with subject combinations).

Project objectives (keep every change aligned with these):
1. Automate student result processing (Exam Result → Student Term Result → grade, points, division)
   and provide analytics that support decision making.
2. A parent portal (`/parent-portal`) giving guardians real-time access to their children's academic
   performance, fee status and school announcements.

Parent-facing UI text is in Swahili. Keep it in Swahili unless asked otherwise.

## Layout
- Module folder: `smart_school/an_intergrated_academic_management_system/doctype/` (27 doctypes).
  The module name contains a typo ("INTERGRATED"). Do NOT rename the module or folder.
- `smart_school/api.py`: teacher marks import (JSON list, CSV, wide CSV/XLSX).
- `smart_school/permissions.py`: `permission_query_conditions` functions.
- `smart_school/portal_utils.py`: portal helpers + whitelisted payment / notification endpoints.
- `smart_school/www/parent-portal/`: portal pages (`index.py` + `index.html` per page).
- `smart_school/tasks.py`: daily scheduler jobs (risk score, performance insights, academic records).
- `smart_school/notifications.py`: email / SMS / in-app notifications to guardians.
- `smart_school/payment_gateway.py`: currently unused.

Roles: System Manager, Headmaster, Teacher, Accountant, Parent.
Parents are Website Users linked through `Guardian.user`; children through the `Guardian Student Link` child table.

## Working rules
- Only edit files inside `apps/smart_school`. Never modify frappe or any other app.
- Change doctype schemas by editing the doctype `.json` (bump its `modified` timestamp), not through
  Customize Form / Custom Fields. If a Custom Field with the same fieldname exists on the site,
  it must be deleted before migrating.
- Data changes needed by a schema change go in a patch under `smart_school/patches/` registered in `patches.txt`.
- After schema changes: `bench --site <site> migrate`.
  After JS or hooks changes: `bench build --app smart_school` and `bench --site <site> clear-cache`.
- Never run destructive commands (drop/truncate tables, delete records, reinstall the site, `git reset --hard`)
  without asking first.
- Never build SQL with f-strings from values. Use `frappe.db.escape`, filters dicts, or query builder.
- Every `@frappe.whitelist()` method must explicitly check role and/or ownership before doing work.
  Only use `ignore_permissions=True` right after such a check.
- Jinja in `www/` templates does NOT auto-escape: use `| e` in HTML, `| tojson` inside `<script>`
  (without extra quotes), `| urlencode` inside URLs. Never trust `frappe.form_dict` values.
- Work through REVIEW.md batch by batch: one git branch per batch, commit when the batch checklist passes,
  then stop and report before starting the next batch.
- When a fix depends on an open decision listed in REVIEW.md, ask instead of guessing.
