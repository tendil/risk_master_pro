{
    'name': 'RiskMaster Pro',
    'version': '17.0.1.0',
    'category': 'Human Resources',
    'summary': 'Custom module for managing employee risk reports.',
    'description': """
        The Employee Risk Manager is a custom module designed for managing and reporting
        on employee risk within the HRM framework. It integrates with Odoo's accounting 
        features to provide comprehensive reports and tools for managing employee-related risks.
    """,
    'depends': ['account', 'hr'],
    'author': 'Dmitry Meita, TJHelpers Inc.',
    'website': 'https://www.tjhelpers.com',
    'license': 'OPL-1',
    'data': [
        'security/risk_master_groups.xml',
        'security/ir.model.access.csv',
        'views/employee_report_view.xml',
        'views/risk_master_documentation_view.xml',
        'views/risk_master_documentation_action.xml',
        'views/employee_report_menu.xml',
        'views/insurance_report_view.xml',
    ],
    'demo': [
        'data/health_insurance_provider.xml',
        'data/demo_insurance_report.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
