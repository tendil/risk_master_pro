from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from xlwt import Workbook, easyxf
import base64
import io


class EmployeeReport(models.Model):
    _name = 'employee.report'
    _description = 'Employee Report'

    claimant_code = fields.Char(string='Reference Code')
    name = fields.Char(string='Reporting Period', readonly=True)
    insurer_id = fields.Many2one('health.insurance.provider', string='Insurance Company', required=True)
    claimant_type = fields.Selection([
        ('medico', 'Medical Claim'),
        ('no_medico', 'Non-Medical Claim'),
    ], string='Claim Type')
    line_ids = fields.One2many('employee.report.line', 'report_reference_id', string='Report Entries')
    date_from = fields.Date(string='Coverage Start Date', required=True)
    date_to = fields.Date(string='Coverage End Date', required=True)
    partner_id = fields.Many2one('res.partner', string='Contact', required=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError(_("End date must be after start date."))
            record._generate_reporting_period_name()

    def _generate_reporting_period_name(self):
        """Generate the reporting period name based on date_from and date_to."""
        for record in self:
            date_from = fields.Date.from_string(record.date_from)
            date_to = fields.Date.from_string(record.date_to)

            record.name = '{:02d}/{:04d}-{:02d}/{:04d}'.format(
                date_from.month, date_from.year, date_to.month, date_to.year
            )

    @api.model
    def create(self, vals):
        if not self.env.context.get('install_mode', False):
            if not self.env.user.has_group('risk_master_pro.group_risk_master_admin'):
                raise AccessError(_("You do not have the rights to create reports."))
        report = super().create(vals)
        report.generate_report(report.id)
        return report

    def write(self, vals):
        if not self.env.user.has_group('risk_master_pro.group_risk_master_admin'):
            raise AccessError(_("You do not have the rights to modify this report."))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('risk_master_pro.group_risk_master_admin'):
            raise AccessError(_("You do not have the rights to delete reports."))
        return super().unlink()

    def open_bar_chart(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bar Chart',
            'view_mode': 'graph',
            'res_model': 'employee.report.line',
            'view_id': self.env.ref('risk_master_pro.view_employee_report_graph').id,
            'target': 'new',
        }

    def open_line_chart(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Line Chart',
            'view_mode': 'graph',
            'res_model': 'employee.report.line',
            'view_id': self.env.ref('risk_master_pro.view_employee_report_line_chart').id,
            'target': 'new',
        }

    def open_pie_chart(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pie Chart',
            'view_mode': 'graph',
            'res_model': 'employee.report.line',
            'view_id': self.env.ref('risk_master_pro.view_employee_report_pie_chart').id,
            'target': 'new',
        }

    @api.model
    def generate_report(self, report_reference_id):
        report = self.browse(report_reference_id)

        history_moves = self.env['account.move'].search([
            ('state', '=', 'posted'),
            ('invoice_date', '>=', report.date_from),
            ('invoice_date', '<=', report.date_to),
        ])

        line_ids = []
        for move in history_moves:
            values = {
                'report_reference_id': report.id,
                'auth_code': move.name,
                'service_date_actual': move.invoice_date,
                'affiliate_name': move.partner_id.name,
                'insured_person_name': move.partner_id.name,
                'identity_number': move.partner_id.vat,
                'total_claimed_amount': move.amount_total,
                'service_charge': move.amount_total,
                'goods_charge': move.amount_total,
                'total_payable': move.amount_total + move.amount_tax,
                'affiliate_discrepancy': move.amount_total,
                'invoice_number': move.name,
                'invoice_date_actual': move.invoice_date,
                'service_type': move.move_type,
                'sub_service_type': move.move_type,
                'ncf_issued_date': move.invoice_date,
                'ncf_reference': move.ref,
                'doc_category': 'F' if move.move_type == 'out_invoice' else
                'C' if move.move_type == 'in_invoice' else '',
                'ncf_expiry_date': move.invoice_date,
                'amended_ncf_ref': move.name,
                'nc_or_db_amount_value': move.amount_total,
                'vat_amount': move.amount_tax,
                'isc_charge': move.amount_tax,
                'additional_taxes': move.amount_tax,
                'contact_phone': move.partner_id.phone,
                'mobile_contact': move.partner_id.mobile,
                'email_address': move.partner_id.email,
            }

            created_line = self.env['employee.report.line'].create(values)
            line_ids.append(created_line.id)

        report.write({'line_ids': [(6, 0, line_ids)]})

        return report

    def action_open_lines(self):
        self.ensure_one()
        if not self.env.user.has_group('risk_master_pro.group_risk_master_user'):
            raise AccessError(_("You do not have the rights to view report lines."))
        return {
            'name': 'Entry Details',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'res_model': 'employee.report.line',
            'domain': [('report_reference_id', '=', self.id)],
        }

    def export_to_xlsx(self):
        headers, title = self._get_headers_and_title()
        workbook = self._create_and_populate_xlsx(headers, title)
        workbook_data = io.BytesIO()
        workbook.save(workbook_data)
        workbook_data.seek(0)

        report_file = base64.b64encode(workbook_data.getvalue())
        filename = title + '.xls'

        return self._download_report_file(report_file, filename)

    def _get_headers_and_title(self):
        title = 'Insurance Claim Report'
        headers = [
            'Authorization Code',
            'Date of Service',
            'Affiliate Name',
            'Insured Person',
            'ID Number',
            'Total Claimed Amount',
            'Service Charges',
            'Goods Charges',
            'Total Payable',
            'Affiliate Discrepancy',
            'Invoice Number',
            'Invoice Date',
            'Service Types',
            'Sub-Service Types',
            'NCF Issue Date',
            'NCF Reference',
            'Document Category',
            'NCF Expiry Date',
            'Amended NCF',
            'NC/DB Amount',
            'VAT Amount',
            'ISC Amount',
            'Additional Taxes',
            'Contact Number',
            'Mobile Contact',
            'Email Contact'
        ]
        return [headers, title]

    def _create_and_populate_xlsx(self, headers, title):
        workbook = Workbook()
        worksheet = workbook.add_sheet(title)
        excel_units = 256
        column_width = 30 * excel_units
        header_style = easyxf(
            'pattern: pattern solid, fore_colour blue; font: colour white, bold True;')

        for col_num, header in enumerate(headers):
            worksheet.col(col_num).width = column_width
            worksheet.write(0, col_num, header, header_style)

        for col_num, line in enumerate(self.line_ids, start=1):
            values = self._map_line_values(line)

            for row_num, (key, value) in enumerate(values.items()):
                worksheet.write(col_num, row_num, value or '')

        return workbook

    def _download_report_file(self, report_file, filename):
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': report_file,
            'mimetype': 'application/vnd.ms-excel' if filename.endswith('.xls') else 'text/plain',
            'res_model': self._name,
            'res_id': self.id,
        })

        return {
            'name': 'Download',
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def export_to_txt(self):
        txt_lines = ''
        for col_num, line in enumerate(self.line_ids, start=1):
            values = self._map_line_values(line)
            txt_lines += self._create_txt_line(values)

        txt_file = io.BytesIO()
        txt_file.write(txt_lines.encode('utf-8'))
        txt_file.seek(0)
        txt_file_base64 = base64.b64encode(txt_file.read()).decode('utf-8')

        return self._download_report_file(txt_file_base64, 'Insurance Claims Report.txt')

    def _create_txt_line(self, values):
        txt_line = ''
        for key, value in values.items():
            chunk = str(value or '') + '   '
            if value == '':
                chunk = '      '
            txt_line += chunk
        return txt_line[:-1] + '\n'

    def _map_line_values(self, line):
        values = {
            'auth_code': line.auth_code,
            'service_date_actual': line.service_date_actual,
            'affiliate_name': line.affiliate_name,
            'insured_person_name': line.insured_person_name,
            'identity_number': line.identity_number,
            'total_claimed_amount': line.total_claimed_amount,
            'service_charge': line.service_charge,
            'goods_charge': line.goods_charge,
            'total_payable': line.total_payable,
            'affiliate_discrepancy': line.affiliate_discrepancy,
            'invoice_number': line.invoice_number,
            'invoice_date_actual': line.invoice_date_actual,
            'service_type': line.service_type,
            'sub_service_type': line.sub_service_type,
            'ncf_issued_date': line.ncf_issued_date,
            'ncf_reference': line.ncf_reference,
            'doc_category': line.doc_category,
            'ncf_expiry_date': line.ncf_expiry_date,
            'amended_ncf_ref': line.amended_ncf_ref,
            'nc_or_db_amount_value': line.nc_or_db_amount_value,
            'vat_amount': line.vat_amount,
            'isc_charge': line.isc_charge,
            'additional_taxes': line.additional_taxes,
            'contact_phone': line.contact_phone,
            'mobile_contact': line.mobile_contact,
            'email_address': line.email_address,
        }
        return values


class EmployeeReportLine(models.Model):
    _name = 'employee.report.line'
    _description = 'Employee Report Entry'

    report_reference_id = fields.Many2one('employee.report', string='Report Reference',
                                          index=True, required=True, readonly=True, auto_join=True, ondelete="cascade",
                                          help="The report this entry is associated with.")
    auth_code = fields.Char('Authorization Code')
    service_date_actual = fields.Date('Date of Service')
    affiliate_name = fields.Char('Affiliate Name')
    insured_person_name = fields.Char('Name of Insured')
    identity_number = fields.Char('ID Number')
    total_claimed_amount = fields.Float('Total Claimed Amount')
    service_charge = fields.Float('Service Charges')
    goods_charge = fields.Float('Goods Charges')
    total_payable = fields.Float('Total Payable')
    affiliate_discrepancy = fields.Float('Difference with Affiliate')
    invoice_number = fields.Char('Invoice Number')
    invoice_date_actual = fields.Date('Invoice Date')
    service_type = fields.Char('Type of Service')
    sub_service_type = fields.Char('Sub-Service Type')
    ncf_issued_date = fields.Date('NCF Issued Date')
    ncf_reference = fields.Char('NCF Reference')
    doc_category = fields.Selection([
        ('F', 'Invoice'),
        ('D', 'Debit Note'),
        ('C', 'Credit Note'),
        ('', 'None')
    ], 'Document Category')
    ncf_expiry_date = fields.Date('NCF Expiry Date')
    amended_ncf_ref = fields.Char('Amended NCF Reference')
    nc_or_db_amount_value = fields.Float('NC/DB Amount')
    vat_amount = fields.Float('VAT Amount')
    isc_charge = fields.Float('ISC Charge')
    additional_taxes = fields.Float('Other Taxes')
    contact_phone = fields.Char('Contact Phone')
    mobile_contact = fields.Char('Mobile Contact')
    email_address = fields.Char('Email Address')

    claimant_type = fields.Selection(related='report_reference_id.claimant_type', string='Claim Type', store=True)
    insurer_id = fields.Many2one(related='report_reference_id.insurer_id', string='Insurance Company', store=True)

    def write(self, vals):
        if not self.env.user.has_group('risk_master_pro.group_risk_master_admin'):
            raise AccessError(_("Only administrators can modify report entries."))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group('risk_master_pro.group_risk_master_admin'):
            raise AccessError(_("Only administrators can delete report entries."))
        return super().unlink()
