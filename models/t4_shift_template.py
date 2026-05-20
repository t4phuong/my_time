from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class T4ShiftTemplate(models.Model):
    _name = "t4.shift.template"
    _description = "Shift Template"

    name = fields.Char(required=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        domain="[('company_id', 'in', [False, company_id])]",
    )

    job_id = fields.Many2one(
        "hr.job",
        string="Position",
        domain="[('company_id', 'in', [False, company_id]), '|', ('department_id', '=', False), ('department_id', '=', department_id)]",
    )

    work_entry_type_id = fields.Many2one(
        "hr.work.entry.type",
        string="Work Entry Type",
        required=True,
    )

    start_time = fields.Float(string="Start Time", required=True)
    end_time = fields.Float(string="End Time", required=True)

    max_employee = fields.Integer(
        string="Max Employees",
        default=1,
        required=True,
    )

    active = fields.Boolean(default=True)
    note = fields.Text(string="Note")

    @api.constrains("start_time", "end_time")
    def _check_time_range(self):
        for rec in self:
            if rec.start_time < 0 or rec.start_time >= 24:
                raise ValidationError(_("Start Time must be between 0 and 24."))

            if rec.end_time <= 0 or rec.end_time > 24:
                raise ValidationError(_("End Time must be between 0 and 24."))

            if rec.start_time >= rec.end_time:
                raise ValidationError(_("End Time must be greater than Start Time."))