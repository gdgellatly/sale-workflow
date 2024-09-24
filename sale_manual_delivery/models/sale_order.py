# Copyright 2017 Denis Leemann, Camptocamp SA
# Copyright 2021 Iván Todorovich, Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    manual_delivery = fields.Boolean(
        compute="_compute_team_id",
        store=True,
        readonly=False,
        help="If enabled, the deliveries are not created at SO confirmation. "
        "You need to use the Create Delivery button in order to reserve "
        "and ship the goods.",
    )

    has_pending_delivery = fields.Boolean(
        string="Delivery pending?",
        compute="_compute_delivery_pending",
    )

    @api.depends("team_id")
    def _compute_team_id(self):
        for sale in self:
            sale.manual_delivery = sale.team_id.manual_delivery

    def _compute_delivery_pending(self):
        for sale in self:
            sale.has_pending_delivery = bool(sale.order_line.pending_delivery())

    @api.constrains("manual_delivery")
    def _check_manual_delivery(self):
        if self.filtered_domain(["state", "not in", ["draft", "sent"]]):
            raise ValidationError(
                _(
                    "You can only change to/from manual delivery"
                    " in a quote, not a confirmed order"
                )
            )

    def action_manual_delivery_wizard(self):
        self.ensure_one()
        action = self.env.ref("sale_manual_delivery.action_wizard_manual_delivery")
        [action] = action.read()
        action["context"] = {"default_carrier_id": self.carrier_id.id}
        return action
