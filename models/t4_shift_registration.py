from odoo import models, fields, exceptions, _

class T4ShiftRegistration(models.Model):
    _name = 't4.shift.registration'
    _description = 'Shift Registration'

    shift_id = fields.Many2one('t4.shift', string='Shift', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ], string='Status', default='pending', tracking=True)

    def action_approve(self):
        for rec in self:
            if rec.state != 'pending':
                raise exceptions.UserError(_("Only pending registrations can be approved."))
            rec.state = 'approved'

    def action_deny(self):
        for rec in self:
            if rec.state == 'denied':
                raise exceptions.UserError(_("Registration is already denied."))
            rec.state = 'denied'

    date_start = fields.Datetime(related='shift_id.date_start')
    date_stop = fields.Datetime(related='shift_id.date_stop')