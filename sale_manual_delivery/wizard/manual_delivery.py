# Copyright 2017 Denis Leemann, Camptocamp SA
# Copyright 2021 Iván Todorovich, Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ManualDelivery(models.TransientModel):
    _name = "manual.delivery"
    _description = "Manual Delivery"
    _order = "create_date desc"
    _check_company_auto = True

    def _get_active_order_lines(self):
        active_model = self.env.context["active_model"]
        if active_model == "sale.order.line":
            sale_ids = self.env.context["active_ids"] or []
            order_lines = self.env["sale.order.line"].browse(sale_ids)
        elif active_model == "sale.order":
            sale_ids = self.env.context["active_ids"] or []
            order_lines = self.env["sale.order"].browse(sale_ids).order_line
        else:
            order_lines = self.env["sale.order.line"]
        return order_lines

    def _get_partner(self, order):
        shipping_partner = order.partner_shipping_id
        order_partner = order.partner_id
        try:
            shipping_partner.ensure_one()
            partner = shipping_partner
        except ValueError:
            try:
                order_partner.ensure_one()
                partner = order_partner
            except ValueError:
                raise UserError(_("Please select one partner at a time"))
        return partner.id

    def _get_company(self, order):
        company = order.company_id
        try:
            company.ensure_one()
        except ValueError:
            raise UserError(
                _("All orders to manually deliver must be from the same company")
            )
        return company.id

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        order_lines = self._get_active_order_lines().pending_delivery()
        if not order_lines:
            raise UserError(_("There are no Deliverable Lines"))

        res["partner_id"] = self._get_partner(order_lines.order_id)
        res["company_id"] = self._get_company(order_lines.order_id)
        if len(carrier := order_lines.order_id.carrier_id) == 1:
            res["carrier_id"] = carrier.id
        # Convert to manual.delivery.lines
        res["line_ids"] = [
            {
                "order_line_id": line.id,
                "quantity": line.qty_to_procure,
            }
            for line in order_lines
        ]
        return res

    def _get_partner_id_domain(self):
        partner_shipping_field = self.env["sale.order"].fields_get(
            allfields=["partner_shipping_id"]
        )["partner_shipping_id"]
        return partner_shipping_field.get("domain", [])

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        readonly=True,
    )

    commercial_partner_id = fields.Many2one(
        "res.partner", related="partner_id.commercial_partner_id"
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Delivery Address",
        domain=lambda s: s._get_partner_id_domain(),
        ondelete="cascade",
        check_company=True,
    )
    carrier_id = fields.Many2one(
        "delivery.carrier",
        string="Delivery Method",
        ondelete="cascade",
        check_company=True,
    )
    route_id = fields.Many2one(
        "stock.route",
        string="Use specific Route",
        domain=[("sale_selectable", "=", True)],
        ondelete="cascade",
        help="Leave it blank to use the same route that is in the sale line",
        check_company=True,
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
            "manual_partner_id": self.partner_id.id,
            "manual_carrier_id": self.carrier_id.id,
        }

    def confirm(self):
        """Creates the manual procurements"""
        self.ensure_one()
        order_lines = self.line_ids.order_line_id
        context = self._get_action_launch_stock_rule_context()
        if not context.get("manual_qty_to_procure"):
            return {"type": "ir.actions.act_window_close"}
        order_lines.with_context(**context)._action_launch_stock_rule()
