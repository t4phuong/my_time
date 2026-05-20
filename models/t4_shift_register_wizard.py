from odoo import models, fields, _
from odoo.exceptions import UserError


class T4ShiftRegisterWizard(models.TransientModel):
    _name = "t4.shift.register.wizard"
    _description = "Shift Register Wizard"

    shift_id = fields.Many2one(
        "t4.shift",
        string="Shift",
        required=True,
    )

    note = fields.Text(string="Note")

    def action_confirm(self):
        self.ensure_one()

        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_("Current user is not linked to an employee."))

        existed = self.env["t4.shift.registration"].search([
            ("shift_id", "=", self.shift_id.id),
            ("employee_id", "=", employee.id),
            ("state", "in", ["pending", "approved"]),
        ], limit=1)

        if existed:
            raise UserError(_("You have already registered for this shift."))

        self.env["t4.shift.registration"].create({
            "shift_id": self.shift_id.id,
            "employee_id": employee.id,
            "note": self.note,
            "state": "pending",
        })

        return {"type": "ir.actions.act_window_close"}