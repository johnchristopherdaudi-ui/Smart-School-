frappe.ui.form.on('Guardian Student Link', {
    filter_class: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        console.log("Filter class selected:", row.filter_class);

        frm.fields_dict['students'].grid.get_field('student').get_query = function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            console.log("get_query running, filter_class:", row.filter_class);
            return {
                filters: {
                    current_class: row.filter_class
                }
            };
        };
    }
});