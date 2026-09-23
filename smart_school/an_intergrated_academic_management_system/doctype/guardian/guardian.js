frappe.ui.form.on('Guardian Student Link', {
    filter_class: function(frm, cdt, cdn) {
        frm.fields_dict['students'].grid.get_field('student').get_query = function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            return {
                filters: {
                    current_class: row.filter_class
                }
            };
        };
    }
});
