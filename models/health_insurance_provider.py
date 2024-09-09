from odoo import models, fields


class HealthInsuranceProvider(models.Model):
    _name = 'health.insurance.provider'
    _description = 'Health Insurance Provider'

    name = fields.Char(string='First Name', required=True)
    code = fields.Char(string='Identifier Code', required=True)
    address = fields.Text(string='Physical Address')
    phone = fields.Char(string='Contact Number')
    email = fields.Char(string='Email Address')
    website = fields.Char(string='Website URL')
    active = fields.Boolean(string='Is Active', default=True)
    company_id = fields.Many2one('res.company',
                                 string='Associated Company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency',
                                  string='Default Currency',
                                  default=lambda self: self.env.company.currency_id)
