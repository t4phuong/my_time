import pytz

from odoo import models
from odoo.tools.intervals import Intervals

import logging
_logger = logging.getLogger(__name__)



class HrVersion(models.Model):
    _inherit = "hr.version"

    def _to_utc_naive(self, dt):
        if dt.tzinfo:
            return dt.astimezone(pytz.utc).replace(tzinfo=None)
        return dt

    def _get_shift_registrations(self, employee, date_start, date_stop):
        date_start = self._to_utc_naive(date_start)
        date_stop = self._to_utc_naive(date_stop)

        registrations = self.env["t4.shift.registration"].search([
            ("employee_id", "in", employee.ids),
            ("shift_id.date_start", "<", date_stop),
            ("shift_id.date_stop", ">", date_start),
            ("state", "=", "approved"),
        ])

        valid_registrations = self.env["t4.shift.registration"]

        for reg in registrations:
            shift = reg.shift_id

            attendance = self.env["hr.attendance"].search([
                ("employee_id", "=", employee.id),
                ("check_in", "<=", shift.date_start),
                ("check_out", ">=", shift.date_stop),
            ], limit=1)

            if attendance:
                valid_registrations |= reg

        return valid_registrations

    def _get_shift_work_entry_values(self, date_start, date_stop):
        """
        Sinh work entry cho ca trực đã được duyệt.

        Quy tắc:
        - Ca trực approved → luôn sinh work entry trực, bất kể trùng attendance hay ngày lễ
        - Conflict với attendance/public holiday sẽ do hr.work.entry resolve
        """
        start_dt = pytz.utc.localize(date_start) if not date_start.tzinfo else date_start
        end_dt = pytz.utc.localize(date_stop) if not date_stop.tzinfo else date_stop

        vals_list = []

        for version in self:
            employee = version.employee_id
            resource = employee.resource_id

            if not employee or not resource:
                continue

            registrations = version._get_shift_registrations(employee, start_dt, end_dt)

            for registration in registrations:
                shift = registration.shift_id
                if not shift.date_start or not shift.date_stop:
                    continue

                shift_start_dt = (
                    pytz.utc.localize(shift.date_start)
                    if not shift.date_start.tzinfo else shift.date_start
                )
                shift_stop_dt = (
                    pytz.utc.localize(shift.date_stop)
                    if not shift.date_stop.tzinfo else shift.date_stop
                )

                shift_interval = Intervals([(shift_start_dt, shift_stop_dt, shift)], keep_distinct=True)

                vals_list += version._get_shift_work_entry_vals(shift_interval)

        return vals_list
    
    def _get_shift_work_entry_vals(self, intervals):
        self.ensure_one()
        vals = []

        employee = self.employee_id
        resource = employee.resource_id

        for interval in intervals:
            work_entry_type = self._get_interval_work_entry_type(interval)
            vals += [dict([
                      ('name', "%s: %s" % (work_entry_type.name, employee.name)),
                      ('date_start', interval[0].astimezone(pytz.utc).replace(tzinfo=None)),
                      ('date_stop', interval[1].astimezone(pytz.utc).replace(tzinfo=None)),
                      ('work_entry_type_id', work_entry_type.id),
                      ('employee_id', employee.id),
                      ('version_id', self.id),
                      ('company_id', self.company_id.id),
                  ] )]
            
        return vals


    def _get_valid_leave_intervals(self, attendances, interval):
        self.ensure_one()

        interval_start, interval_stop, leave = interval

        # Chỉ xử lý global public holiday
        if not hasattr(leave, 'resource_id') or leave.resource_id or getattr(leave, 'holiday_id', False):
            return super()._get_valid_leave_intervals(attendances, interval)

        registrations = self._get_shift_registrations(
            self.employee_id,
            interval_start,
            interval_stop,
        )

        if not registrations:
            return super()._get_valid_leave_intervals(attendances, interval)

        # interval đã ở local tz, shift naive UTC → localize UTC rồi convert sang cùng tz
        tz = interval_start.tzinfo
        shift_interval = Intervals([
            (
                pytz.utc.localize(reg.shift_id.date_start).astimezone(tz),
                pytz.utc.localize(reg.shift_id.date_stop).astimezone(tz),
                reg,
            )
            for reg in registrations
            if reg.shift_id.date_start and reg.shift_id.date_stop
        ])

        remaining = Intervals([(interval_start, interval_stop, leave)]) - shift_interval

        res = []
        for start, stop, leave in remaining:
            res += super()._get_valid_leave_intervals(attendances, (start, stop, leave))

        return res


    def _get_real_attendances(self, attendances, leaves, worked_leaves):
        real_attendances = attendances - leaves - worked_leaves

        if not attendances:
            return real_attendances

        first_attendance = next(iter(attendances), None)
        if not first_attendance:
            return real_attendances

        tz = first_attendance[0].tzinfo

        start_dt = min(a[0] for a in attendances)
        end_dt = max(a[1] for a in attendances)

        registrations = self._get_shift_registrations(
            self.employee_id,
            start_dt,
            end_dt,
        )

        shift_intervals = Intervals([
            (
                pytz.utc.localize(reg.shift_id.date_start).astimezone(tz),
                pytz.utc.localize(reg.shift_id.date_stop).astimezone(tz),
                reg,
            )
            for reg in registrations
            if reg.shift_id.date_start and reg.shift_id.date_stop
        ], keep_distinct=True)

        return real_attendances - shift_intervals



    def _get_version_work_entries_values(self, date_start, date_stop):
        vals = super()._get_version_work_entries_values(date_start, date_stop)
        shift_vals = self._get_shift_work_entry_values(date_start, date_stop)
        vals += shift_vals

        return vals