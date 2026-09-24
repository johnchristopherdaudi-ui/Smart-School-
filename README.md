# Smart School — An Integrated Academic Management System

A [Frappe](https://frappeframework.com) v15 app for Tanzanian O-level secondary schools (Form 1–4). It automates
result processing (exam marks → subject scores → grades, points and divisions), gives staff reports and dashboards
for decision making, and gives parents a Swahili portal with their children's results, fees and announcements.

> The Python module and folder are named `an_intergrated_academic_management_system` (with a historical typo).
> Do not rename them: doctypes, patches and records are bound to that module name.

## Features

**Results**
- Exams per class and term, each with its own maximum marks and an optional weight (weights of a class's exams in
  a term are all set and add up to 100, or all empty).
- A subject's term score is the weighted average of the percentages of the exams the student sat (plain average when
  there are no weights), rounded half up (74.5 → 75), then graded from the **Grading System** table.
- Division from the best 7 subjects via the **Division Grading** table; fewer than 7 subjects gives *Incomplete*.
  Both tables are editable data and reject overlapping ranges.
- Marks import: JSON list, single-subject CSV, and wide CSV/XLSX (subjects by name or code, students by admission
  number or unique full name, Excel BOM handled, errors reported per row). Teachers may only enter the subjects
  and classes they are assigned to.
- Results are **published per exam** by the Headmaster; parents see published exams only, and the term summary once
  every exam of that term is published. One notification per student per published exam.
- **Report card** print format (English) with each exam's marks, term score, grade, remark, points, division,
  *Position X out of Y*, attendance, class teacher's and headmaster's comments and the next term's opening date.
  The Headmaster can print a whole class in one PDF.

**Fees and payments**
- One fee statement per student (`smart_school.fees.get_fee_statement`): every started term priced with the class the
  student was in, submitted payments only, and overpayments paying the oldest debt first ("Salio la ziada").
- Fee Payment is submittable (`RCPT-.YYYY.-.#####`), immutable once submitted, and notifies the guardian once.
- Mobile-money **demo** payments from the portal, behind the *Enable Demo Payments* switch in Smart School Settings.
  `payment_gateway.py` is the base for a real aggregator integration.

**Parent portal** (`/parent-portal`, Swahili, mobile friendly)
- Dashboard per child: latest published results, attendance, fee balance, announcements, trend chart and gentle
  alerts (no risk scores are shown to parents).
- Results with report card PDF download, fees with payment, discipline, announcements and a notification bell.
- Parents are Website Users; they can only reach their own children's data.

**Staff**
- Workspaces: **Headmaster**, **Academics** (teachers), **Finance** (accountant) and **School Settings**
  (system manager), each opened by default after login.
- Script reports: Class Merit List, Subject Performance, Division Summary, Fee Collection and Defaulters,
  Attendance Summary, At-Risk Students, My Classes, Pending Report Card Comments. Teachers only see the classes and
  subjects they are assigned to; accountants only see fee reports.
- Daily jobs: risk score per student (attendance, discipline, low average, failed subjects, decline; weights and
  levels in Smart School Settings), performance insights per class and subject, and academic records for ended years.
- Student Promotion Tool: promote a class to the next level, keep repeaters, graduate Form 4.
- Public admission form at `/apply-online`; the Headmaster approves (certificate attached or verified), which
  creates the student and links or creates the guardian.

## Roles

| Role | Can do |
|---|---|
| System Manager | Everything, including Smart School Settings, grading tables and terms |
| Headmaster | Admissions, students, guardians, teachers, exams (publish), term results and comments, all reports, promotion |
| Teacher | Enter/import marks for assigned subjects, attendance, discipline, class teacher comments, academic reports for own classes |
| Accountant | Fee structures, fee payments (submit/cancel), fee reports |
| Parent | Parent portal only (Website User) |

## Setup

```bash
cd ~/frappe-bench
bench get-app <repository-url> smart_school
bench --site <site> install-app smart_school
bench --site <site> migrate
bench build --app smart_school
```

`after_install` creates the roles, the provisional grading and division tables with grade remarks, the risk score
defaults and the unique index on term results. Then, as System Manager:

1. **Smart School Settings**: school name, motto, logo, address; risk score weights; turn *Enable Demo Payments* on
   only for demonstrations.
2. **Academic Year** and **Terms** (terms must lie inside their year and must not overlap), **Classes** (with a level
   1–4 and a class teacher), **Subjects**, **Combinations** and **Class Subject Mapping**.
3. **Fee Structure** per class and term, **Teachers** (a user with the Teacher role is created from the email) and
   their subject assignments, **Students** and **Guardians** (a portal user is created from the email).
4. Check the provisional **Grading System** / **Division Grading** values with the academic master.
5. Outgoing email: an Email Account set as default outgoing; SMS: Frappe's SMS Settings.
   Set `host_name` in the site config so links in emails point to the real address.

The app cannot share a site with ERPNext, Education or HRMS: doctype names clash (Student, Guardian, Attendance,
Fee Structure, Academic Year, Student Admission).

## Running the tests

Tests build their own "_Test" school and never need real data, but run them on a separate site:

```bash
bench new-site test.localhost --db-root-username root --admin-password <password>
bench --site test.localhost set-config allow_tests true
bench --site test.localhost install-app smart_school
bench --site test.localhost run-tests --app smart_school
```

A single suite: `bench --site test.localhost run-tests --module smart_school.tests.test_payments`.

| Suite | Covers |
|---|---|
| `test_install` | Fresh install: grading/division tables, remarks, risk defaults, roles, synced reports and workspaces |
| `test_permissions` | Guest, parent and teacher access; admission approval; comments by their owners |
| `test_imports` | Marks import roles and assignments, CSV/BOM, wide CSV, per-row errors |
| `test_payments` | Payment validation, double confirmation, demo switch, XSS, fee statement credit, Fee Payment lifecycle |
| `test_results` | Weights, 74.5 → A, Incomplete, amend after cancel, grading and weight validation |
| `test_publish` | Who publishes, what parents see, one notification per student |
| `test_reports` | Merit ranking, subject statistics, defaulters, report permissions |
| `test_report_card` | Report card data, PDF, class printing, parent download ownership and publishing |
| `test_portal` | Base template on every page, guest redirects, parent home page, dashboard, workspaces |
| `test_tasks` | Risk score, insights, promotion tool, academic records |

## Demo accounts (site `jonbale`)

Passwords are set by the system owner and are not stored here.

| Role | User | Notes |
|---|---|---|
| System Manager | Administrator | |
| Headmaster | jacksonandrea2002+hm@gmail.com | Demo Headmaster |
| Accountant | jacksonandrea2002+acc@gmail.com | Demo Accountant |
| Teacher | jacksonandrea2002+mwalimu1@gmail.com | Inncoent Rungu |
| Teacher | alotaconstand+mwalimu2@gmail.com | Wayne Rooney (Form 1) |
| Teacher | balejunior0502+mwalimu3@gmail.com | Pretta Emmanuel |
| Teacher | jacksonandrea2002+mwalimu4@gmail.com | Bageni Mtaka (Form 2) |
| Teacher | alotaconstand+mwalimu5@gmail.com | Fransis Matata |
| Teacher | balejunior0502+mwalimu6@gmail.com | Xavier Thomas |
| Teacher | jacksonandrea2002+mwalimu7@gmail.com | Maria Db |
| Teacher | alotaconstand+mwalimu8@gmail.com | Luka Modric |
| Teacher | balejunior0502+mwalimu9@gmail.com | Ibrahim Ibrahim |
| Parent | raymondgoesberty2023@gmail.com | Jenifer Robert, four children |
| Parent | balejunior0502+mzazi1@gmail.com | Noel Bale Junior, two children |

## License

MIT
