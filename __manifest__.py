{
    'name': 'My Time',
    'version': '1.1.0',
    'summary': 'Employee calendar, duty shift management and registration',
    'category': 'Human Resources',
    'author': 'Your Company',
    'depends': ['hr', 'mail'],
    'data': [
        'security/ir.model.access.csv',

        'views/shift_template_views.xml',
        'views/shift_registrations_views.xml',
        'views/shift_registrations_management_views.xml',
        'views/shift_management_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            't4_my_time/static/src/scss/calendar.scss',
            "t4_my_time/static/src/js/shift_calendar_badge.js",
            "t4_my_time/static/src/css/shift_calendar_badge.css",
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
