frappe.listview_settings['Exam Result'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Upload Wide CSV'), function() {
            let d = new frappe.ui.Dialog({
                title: 'Import Wide Format Results',
                fields: [
                    {
                        label: 'Exam',
                        fieldname: 'exam',
                        fieldtype: 'Link',
                        options: 'Exam',
                        reqd: 1
                    },
                    {
                        fieldname: 'info',
                        fieldtype: 'HTML',
                        options: '<p>CSV / XLSX format: first column = Admission Number (or Full Name if unique in the class), remaining columns = Subject name or code, values = Marks.</p>'
                    },
                    {
                        label: 'CSV File',
                        fieldname: 'file_url',
                        fieldtype: 'Attach',
                        reqd: 1
                    }
                ],
                primary_action_label: 'Upload',
                primary_action(values) {
                    frappe.show_progress('Importing...', 50, 100, 'Processing CSV');

                    frappe.call({
                        method: 'smart_school.api.import_wide_format_csv',
                        args: {
                            file_url: values.file_url,
                            exam: values.exam
                        },
                        callback: function(res) {
                            let msg = `Created: ${res.message.created}, Skipped (already entered): ${res.message.skipped}`;
                            if (res.message.errors.length > 0) {
                                let errors = res.message.errors.map(e => frappe.utils.escape_html(e));
                                msg += `<br><br>Errors (${errors.length}):<br>${errors.join('<br>')}`;
                            }
                            frappe.msgprint(msg);
                            listview.refresh();
                            d.hide();
                        },
                        always: function() {
                            frappe.hide_progress();
                        }
                    });
                }
            });
            d.show();
        });
    }
};