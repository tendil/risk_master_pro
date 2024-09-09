from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InsuranceReport(models.Model):
    _name = 'insurance.report'
    _description = 'Insurance Claims Analysis Report'

    name = fields.Char(string='Report Name', required=True, default=lambda self: _('New Report'))
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    insurance_company_id = fields.Many2one('health.insurance.provider', string='Insurance Company')
    employee_id = fields.Many2one('hr.employee', string='Employee')

    report_type = fields.Selection([
        ('group_by_claim_type', 'Group by Claim Type'),
        ('expense_analysis', 'Expense Analysis'),
        ('effectiveness_monitoring', 'Effectiveness Monitoring'),
        ('monthly_expense_analysis', 'Monthly Expense Analysis')
    ], string='Report Type', required=True)

    report_result = fields.Html(string='Report Result', readonly=True)
    summary_result = fields.Char(string='Summary Result', readonly=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError(_("End date must be after start date."))

    @api.model
    def create(self, vals):
        report = super().create(vals)
        report.generate_report()
        return report

    def generate_report(self):
        """ Generate the report based on the selected report type and filters. """
        full_report = ""
        summary = ""

        if self.report_type == 'group_by_claim_type':
            full_report, summary = self._generate_group_by_claim_type_report()
        elif self.report_type == 'expense_analysis':
            full_report, summary = self._generate_expense_analysis_report()
        elif self.report_type == 'effectiveness_monitoring':
            full_report, summary = self._generate_effectiveness_monitoring_report()
        elif self.report_type == 'monthly_expense_analysis':
            full_report, summary = self._generate_monthly_expense_analysis_report()  # Новый отчёт

        self.report_result = full_report
        self.summary_result = summary

    def _generate_group_by_claim_type_report(self):
        """ Generate a report that groups data by claim type (medical, non-medical). """
        claim_lines = self.env['employee.report.line'].search([
            ('service_date_actual', '>=', self.date_from),
            ('service_date_actual', '<=', self.date_to)
        ])

        grouped_data = {}
        total_amount = 0.0

        for line in claim_lines:
            claim_type = line.report_reference_id.claimant_type
            if claim_type not in grouped_data:
                grouped_data[claim_type] = {
                    'total_claims': 0,
                    'total_amount': 0.0,
                }
            grouped_data[claim_type]['total_claims'] += 1
            grouped_data[claim_type]['total_amount'] += line.total_claimed_amount
            total_amount += line.total_claimed_amount

        summary = "Grouped by claim type: " + ', '.join(
            [f"{claim_type}: {data['total_amount']:.2f}" for claim_type, data in grouped_data.items()])

        report_content = '''
        <h3>Report: Group by Claim Type</h3>
        <table class="table table-bordered">
            <thead>
                <tr><th>Claim Type</th><th>Total Claims</th><th>Total Amount</th></tr>
            </thead>
            <tbody>'''

        for claim_type, data in grouped_data.items():
            report_content += f'<tr><td>{claim_type.capitalize()}</td><td>{data["total_claims"]}</td><td>{data["total_amount"]:.2f}</td></tr>'

        report_content += f'''
            </tbody>
            <tfoot>
                <tr><td><strong>Total</strong></td><td colspan="2">{total_amount:.2f}</td></tr>
            </tfoot>
        </table>'''

        return report_content, summary

    def _generate_expense_analysis_report(self):
        """ Generate an expense analysis report based on claims. """
        domain = [('service_date_actual', '>=', self.date_from),
                  ('service_date_actual', '<=', self.date_to)]

        if self.insurance_company_id:
            domain.append(('report_reference_id.insurer_id', '=', self.insurance_company_id.id))
        if self.employee_id:
            domain.append(('insured_person_name', '=', self.employee_id.name))

        claim_lines = self.env['employee.report.line'].search(domain)

        total_expense = sum(line.total_payable for line in claim_lines)
        total_vat = sum(line.vat_amount for line in claim_lines)

        summary = f"Total Expense: {total_expense:.2f}, VAT: {total_vat:.2f}"

        report_content = '''
        <h3>Report: Expense Analysis</h3>
        <table class="table table-bordered">
            <thead>
                <tr><th>Invoice Number</th><th>Date</th><th>Claimed Amount</th><th>VAT Amount</th><th>Total Payable</th></tr>
            </thead>
            <tbody>'''

        for line in claim_lines:
            report_content += f'''
                <tr>
                    <td>{line.invoice_number}</td>
                    <td>{line.service_date_actual}</td>
                    <td>{line.total_claimed_amount:.2f}</td>
                    <td>{line.vat_amount:.2f}</td>
                    <td>{line.total_payable:.2f}</td>
                </tr>'''

        report_content += f'''
            </tbody>
            <tfoot>
                <tr><td colspan="4"><strong>Total Expense:</strong></td><td>{total_expense:.2f}</td></tr>
                <tr><td colspan="4"><strong>Total VAT:</strong></td><td>{total_vat:.2f}</td></tr>
            </tfoot>
        </table>'''

        return report_content, summary

    def _generate_effectiveness_monitoring_report(self):
        """ Generate a report that monitors the effectiveness of insurance programs. """
        claim_lines = self.env['employee.report.line'].search([
            ('service_date_actual', '>=', self.date_from),
            ('service_date_actual', '<=', self.date_to)
        ])

        unique_employees = set(line.insured_person_name for line in claim_lines)
        total_claims = len(claim_lines)
        total_employees = len(unique_employees)

        summary = f"Total Employees: {total_employees}, Total Claims: {total_claims}"

        report_content = '''
        <h3>Report: Effectiveness Monitoring</h3>
        <p><strong>Total Employees Covered:</strong> {total_employees}</p>
        <p><strong>Total Claims Processed:</strong> {total_claims}</p>'''

        return report_content, summary

    def _generate_monthly_expense_analysis_report(self):
        """ Monthly expense analysis report (сравнительный анализ затрат по месяцам). """
        claim_lines = self.env['employee.report.line'].search([
            ('service_date_actual', '>=', self.date_from),
            ('service_date_actual', '<=', self.date_to)
        ])

        monthly_data = {}
        for line in claim_lines:
            month = line.service_date_actual.strftime('%Y-%m')
            if month not in monthly_data:
                monthly_data[month] = 0.0
            monthly_data[month] += line.total_payable

        summary = f"Expense by Month: {', '.join([f'{month}: {total:.2f}' for month, total in monthly_data.items()])}"

        report_content = '''
        <h3>Report: Monthly Expense Analysis</h3>
        <table class="table table-bordered">
            <thead>
                <tr><th>Month</th><th>Total Expense</th></tr>
            </thead>
            <tbody>'''

        for month, total in monthly_data.items():
            report_content += f'<tr><td>{month}</td><td>{total:.2f}</td></tr>'

        report_content += '</tbody></table>'
        return report_content, summary
