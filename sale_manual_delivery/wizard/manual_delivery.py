# Copyright 2017 Denis Leemann, Camptocamp SA
# Copyright 2021 Iván Todorovich, Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class ManualDelivery(models.TransientModel):
    _name = "manual.delivery"
    _description = "Manual Delivery"
    _order = "create_date desc"

    def _get_active_order_lines(self):
        active_model = self.env.context["active_model"]
        if active_model == "sale.order.line":
            sale_ids = self.env.context["active_ids"] or []
            order_lines = self.env["sale.order.line"].browse(sale_ids)
        elif active_model == "sale.order":
            sale_ids = self.env.context["active_ids"] or []
            order_lines = self.env["sale.order"].browse(sale_ids).mapped("order_line")
        else:
            order_lines = self.env["sale.order.line"]
        return order_lines

    def _get_partner(self, order_lines):
        partner = order_lines.mapped("order_id.partner_shipping_id")
        try:
            partner.ensure_one()
        except ValueError:
            partner = order_lines.mapped("order_id.partner_id")
            try:
                partner.ensure_one()
            except ValueError:
                raise UserError(_("Please select one partner at a time"))
        return partner

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        order_lines = self._get_active_order_lines().pending_delivery()
        if not order_lines:
            return res
        partner = self._get_partner(order_lines)
        res["partner_id"] = partner.id
        if len(carrier := order_lines.order_id.carrier_id) == 1:
            res["carrier_id"] = carrier.id
        # Convert to manual.delivery.lines
        res["line_ids"] = [
            Command.create(
                {
                    "order_line_id": line.id,
                    "quantity": line.qty_to_procure,
                },
            )
            for line in order_lines
        ]
        return res

    commercial_partner_id = fields.Many2one(
        "res.partner", related="partner_id.commercial_partner_id"
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Delivery Address",
        domain="""
            [
                "|",
                ("id", "=", commercial_partner_id),
                ("parent_id", "=", commercial_partner_id),
            ],
        """,
        ondelete="cascade",
    )
    carrier_id = fields.Many2one(
        "delivery.carrier",
        string="Delivery Method",
        ondelete="cascade",
    )
    route_id = fields.Many2one(
        "stock.route",
        string="Use specific Route",
        domain=[("sale_selectable", "=", True)],
        ondelete="cascade",
        help="Leave it blank to use the same route that is in the sale line",
    )
    line_ids = fields.One2many(
        "manual.delivery.line",
        "manual_delivery_id",
        string="Lines to validate",
    )
    date_planned = fields.Datetime()

    def _get_action_launch_stock_rule_context(self):
        return {
            "manual_qty_to_procure": self.line_ids._get_procurement_quantities(),
            "manual_date_planned": self.date_planned,
            "manual_route_id": self.route_id,
            "partner_id": self.partner_id.id,
            "carrier_id": self.carrier_id.id,
        }

    def confirm(self):
        """Creates the manual procurements"""
        self.ensure_one()
        order_lines = self.line_ids.order_line_id
        order_lines.with_context(
            **self._get_action_launch_stock_rule_context()
        )._action_launch_stock_rule()
