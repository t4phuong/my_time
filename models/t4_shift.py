from datetime import timedelta
import pytz

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo import _


class T4Shift(models.Model):
    _name = "t4.shift"
    _description = "Shift"

    name = fields.Char(required=True)

    template_id = fields.Many2one(
        "t4.shift.template",
        string="Shift Template",
        store=False,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    department_id = fields.Many2one(
        "hr.department",
        string="Department",
    )

    job_id = fields.Many2one(
        "hr.job",
        string="Position",
    )

    work_entry_type_id = fields.Many2one(
        "hr.work.entry.type",
        string="Work Entry Type",
        required=True,
    )

    date_start = fields.Datetime(required=True)
    date_stop = fields.Datetime(required=True)

    max_employee = fields.Integer(default=1, required=True)
    active = fields.Boolean(default=True)
    note = fields.Text()

    registration_ids = fields.One2many(
        "t4.shift.registration",
        "shift_id",
        string="Registrations",
    )

    registered_count = fields.Integer(
        compute="_compute_registered_count",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Open"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        required=True,
    )

    is_registered_by_current_user = fields.Boolean(
        string="Registered by Current User",
        compute="_compute_is_registered_by_current_user",
    )
    
    def _compute_is_registered_by_current_user(self):
        employee = self.env.user.employee_id

        for rec in self:
            rec.is_registered_by_current_user = False

            if not employee:
                continue

            existed = self.env["t4.shift.registration"].search_count([
                ("shift_id", "=", rec.id),
                ("employee_id", "=", employee.id),
                ("state", "in", ["pending", "approved"]),
            ])

            rec.is_registered_by_current_user = bool(existed)

    def action_confirm(self):
        for rec in self:
            rec.state = "open"

    def action_set_draft(self):
        for rec in self:
            rec.state = "draft"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancel"

    @api.depends("registration_ids.state")
    def _compute_registered_count(self):
        for rec in self:
            rec.registered_count = len(
                rec.registration_ids.filtered(
                    lambda r: r.state in ("pending", "approved")
                )
            )

    def _float_time_to_hour_minute(self, value):
        hour = int(value)
        minute = int(round((value - hour) * 60))
        return hour, minute
    
    def _get_shift_tz(self):
        return pytz.timezone(
            self.env.user.tz
            or self.env.company.resource_calendar_id.tz
            or "Asia/Ho_Chi_Minh"
        )

    def _apply_local_time_to_datetime(self, base_dt, time_value):
        user_tz = self._get_shift_tz()

        if base_dt.tzinfo is None:
            base_dt = pytz.utc.localize(base_dt)

        local_dt = base_dt.astimezone(user_tz)
        hour, minute = self._float_time_to_hour_minute(time_value)

        local_dt = local_dt.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

        return local_dt.astimezone(pytz.utc).replace(tzinfo=None)

    @api.onchange("template_id")
    def _onchange_template_id(self):
        for rec in self:
            template = rec.template_id
            if not template:
                return

            rec.name = template.name
            rec.company_id = template.company_id
            rec.department_id = template.department_id
            rec.job_id = template.job_id
            rec.work_entry_type_id = template.work_entry_type_id
            rec.max_employee = template.max_employee
            rec.note = template.note

            if rec.date_start and template.start_time is not False:
                rec.date_start = rec._apply_local_time_to_datetime(
                    rec.date_start,
                    template.start_time,
                )

            if rec.date_start and template.end_time is not False:
                rec.date_stop = rec._apply_local_time_to_datetime(
                    rec.date_start,
                    template.end_time,
                )

                if template.end_time <= template.start_time:
                    rec.date_stop += timedelta(days=1)

    
    def _check_employee_match_shift(self, employee):
        self.ensure_one()

        if self.company_id and self.company_id != employee.company_id:
            raise UserError(_("This shift is not available for your company."))

        if self.department_id and self.department_id != employee.department_id:
            raise UserError(_("This shift is not available for your department."))

        if self.job_id and self.job_id != employee.job_id:
            raise UserError(_("This shift is not available for your position."))


    def action_register_shift(self):
        for rec in self:
            employee = self.env.user.employee_id
            if not employee:
                raise UserError(_("Current user is not linked to an employee."))

            if rec.state != "open":
                raise UserError(_("Only open shifts can be registered."))

            rec._check_employee_match_shift(employee)

            approved_or_pending_count = self.env["t4.shift.registration"].search_count([
                ("shift_id", "=", rec.id),
                ("state", "in", ["pending", "approved"]),
            ])

            if approved_or_pending_count >= rec.max_employee:
                raise UserError(_("This shift is already full."))

            existed = self.env["t4.shift.registration"].search([
                ("shift_id", "=", rec.id),
                ("employee_id", "=", employee.id),
                ("state", "in", ["pending", "approved"]),
            ], limit=1)

            if existed:
                raise UserError(_("You have already registered for this shift."))

            self.env["t4.shift.registration"].create({
                "shift_id": rec.id,
                "employee_id": employee.id,
                "state": "pending",
            })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Registered"),
                "message": _("Your registration has been submitted."),
                "type": "success",
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            },
        }

    state_label = fields.Char(
        compute="_compute_state_label"
    )

    def _compute_state_label(self):
        mapping = {
            "draft": "Draft",
            "open": "Open",
            "cancel": "Cancelled",
            "done": "Done",
        }

        for rec in self:
            rec.state_label = mapping.get(rec.state, "")

