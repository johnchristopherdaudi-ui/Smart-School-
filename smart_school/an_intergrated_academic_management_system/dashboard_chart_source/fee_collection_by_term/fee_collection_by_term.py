# Copyright (c) 2026, john daudi and contributors
# For license information, please see license.txt

import frappe

from smart_school import reports


@frappe.whitelist()
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
	refresh=None,
):
	return reports.get_fee_collection_by_term()
