import pytz
from datetime import timedelta
from odoo import models


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    def _to_utc_naive(self, dt):
        if not dt:
            return dt

        if dt.tzinfo:
            return dt.astimezone(pytz.UTC).replace(tzinfo=None)

        return dt

    def _to_local_aware(self, dt, tzinfo):
        if not dt:
            return dt

        if dt.tzinfo:
            return dt.astimezone(tzinfo)

        return pytz.UTC.localize(dt).astimezone(tzinfo)

    def _get_shift_intervals(self, day_start, day_end, local_tz):
        day_start_utc = self._to_utc_naive(day_start)
        day_end_utc = self._to_utc_naive(day_end)

        shift_regs = self.env["t4.shift.registration"].sudo().search([
            ("employee_id", "=", self.employee_id.id),
            ("state", "=", "approved"),
            ("shift_id.date_start", "<", day_end_utc),
            ("shift_id.date_stop", ">", day_start_utc),
        ])

        intervals = []

        for reg in shift_regs:
            shift = reg.shift_id

            if shift.date_start and shift.date_stop:
                shift_start = self._to_local_aware(shift.date_start, local_tz)
                shift_stop = self._to_local_aware(shift.date_stop, local_tz)

                intervals.append((shift_start, shift_stop, shift))

        return intervals

    def _get_schedule_intervals(self, localized_dt):
        intervals = list(super()._get_schedule_intervals(localized_dt))

        if not self.employee_id or not localized_dt:
            return intervals

        day_start = localized_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        intervals += self._get_shift_intervals(
            day_start,
            day_end,
            localized_dt.tzinfo,
        )

        return intervals