import datetime
from multiprocessing import dummy
from multiprocessing import dummy
from time import time

from odoo import api, models, fields, exceptions, _

import pytz
from odoo.tools.intervals import Intervals

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

    ############### DATETIME HELPER FUNCTIONS ###############
    @api.model
    def _to_utc_naive(self, dt):
        """
        Convert aware datetime -> UTC naive datetime.
        Odoo Datetime fields thường dùng UTC naive.
        """
        if not dt:
            return dt

        if dt.tzinfo:
            return dt.astimezone(pytz.utc).replace(tzinfo=None)

        return dt
    
    @api.model  
    def _localize_datetime(self, dt):
        tz = self.env.user.tz or self.env.company.resource_calendar_id.tz or 'Asia/Ho_Chi_Minh'
        local_tz = pytz.timezone(tz)
        if dt.tzinfo is None:
            return pytz.utc.localize(dt).astimezone(local_tz)
        else:
            return dt.astimezone(local_tz)
        
    ###########################################################

    @api.model
    def _get_employee_version_by_date(self, target_date):
        self.ensure_one()

        if isinstance(target_date, datetime.datetime):
            target_date = target_date.date()

        versions = self.env["hr.version"].search([
            ("employee_id", "=", self.employee_id.id),
            ("date_start", "<=", target_date),
            "|",
                ("date_end", "=", False),
                ("date_end", ">=", target_date),
        ])

        if len(versions) > 1:
            raise exceptions.UserError(
                _("Multiple HR versions found for employee %s on %s.")
                % (self.employee_id.name, target_date)
            )

        if not versions:
            raise exceptions.UserError(
                _("No HR version found for employee %s on %s.")
                % (self.employee_id.name, target_date)
            )

        return versions

    @api.model
    def _get_employee_attendance_intervals_from_version(self, version, start_dt, end_dt):
        """
        Lấy attendance của employee dựa trên hr.version để check khi approve ca trực.
        """
        if not version:
            raise exceptions.UserError(_("Employee %s does not have a valid HR version." % self.employee_id.name))
        
        version.ensure_one()
        
        attendances_by_resource = version._get_attendance_intervals(
            start_dt,
            end_dt,
        )

        return attendances_by_resource.get(
            version.employee_id.resource_id.id,
            Intervals()
        )


    
    @api.model
    def _get_employee_public_holidays_intervals_from_version(self, version, start_dt, end_dt):
        """
        Lấy public holiday của employee dựa trên hr.version để check khi approve ca trực.
        """
        if not version:
            raise exceptions.UserError(_("Employee %s does not have a valid HR version." % self.employee_id.name))
        
        version.ensure_one()
        
        leaves = version._get_resource_calendar_leaves(
            start_dt,
            end_dt,
        )

        public_holidays = leaves.filtered(lambda l: not l.resource_id)

        res = []
        for leave in public_holidays:
            leave_date_start = self._localize_datetime(leave.date_from)
            leave_date_stop = self._localize_datetime(leave.date_to)

            res.append((leave_date_start, leave_date_stop, leave))
        return Intervals(res)
    

    @api.model
    def _get_real_work_schedule(self, date_start, date_stop):
        """
         - Lấy ca trực đã được approved trong khoảng thời gian để sinh work entry trực tiếp
         - Khi approve ca trực sẽ check conflict với attendance và public holiday của employee dựa trên hr.version
         - Nếu có conflict thì vẫn approve bình thường nhưng sẽ cảnh báo cho người duyệt biết
         - Việc conflict với attendance và public holiday sẽ do hr.work.entry resolve khi sinh work entry, nếu trùng thì sẽ không sinh work entry cho ca trực đó
        """
        start_dt = pytz.utc.localize(date_start)
        end_dt = pytz.utc.localize(date_stop)

        version = self._get_employee_version_by_date(date_start)
        attendances = self._get_employee_attendance_intervals_from_version(version, start_dt, end_dt)
        public_holidays = self._get_employee_public_holidays_intervals_from_version(version, start_dt, end_dt)      

        real_attendances = attendances - public_holidays

        return real_attendances
    

    @api.constrains('shift_id', 'employee_id', 'state')
    def _check_shift_conflict(self):
        for rec in self:
            real_work_schedule = rec._get_real_work_schedule(rec.shift_id.date_start, rec.shift_id.date_stop)

            if real_work_schedule and len(real_work_schedule) > 0:
                raise exceptions.ValidationError(_("Employee %s has attendance or public holiday that conflicts with the shift time." % rec.employee_id.name))

            overlapping_regs = self.search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'approved'),
                ('shift_id.date_start', '<', rec.shift_id.date_stop),
                ('shift_id.date_stop', '>', rec.shift_id.date_start),
            ])

            if overlapping_regs:
                raise exceptions.ValidationError(_("Employee %s has overlapping approved shifts." % rec.employee_id.name))


            
    @api.constrains('shift_id', 'employee_id', 'state')
    def _check_attendance_conflict(self):
        for rec in self:
            from datetime import datetime, time

            day_start = datetime.combine(
                rec.shift_id.date_start.date(),
                time.min
            )

            day_stop = datetime.combine(
                rec.shift_id.date_stop.date(),
                time.max
            )

            attendances = rec._get_real_work_schedule(
                day_start, 
                day_stop
            )

            for date_start, date_stop, att in attendances:
                date_start_naive = self._to_utc_naive(date_start)
                date_stop_naive = self._to_utc_naive(date_stop)

                if date_start_naive < rec.shift_id.date_stop and date_stop_naive > rec.shift_id.date_start:
                    raise exceptions.ValidationError(_("Employee %s has attendance that conflicts with the shift time." % rec.employee_id.name))