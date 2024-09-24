# Copyright 2017 Denis Leemann, Camptocamp SA
# Copyright 2021 Iván Todorovich, Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ManualDeliveryLine(models.TransientModel):
    _name = "manual.delivery.line"
    _description = "Manual Delivery Line"

    manual_delivery_id = fields.Many2one(
        "manual.delivery",
        string="Wizard",
        ondelete="cascade",
        required=True,
        readonly=True,
    )
    order_line_id = fields.Many2one(
        "sale.order.line",
        string="Sale Order Line",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(related="order_line_id.product_id")
    name = fields.Text(related="order_line_id.name")
    qty_ordered = fields.Float(
        string="Ordered",
        related="order_line_id.product_uom_qty",
        help="Quantity ordered in the related Sale Order",
        readonly=True,
        digits="Product Unit of Measure",
    )
    qty_procured = fields.Float(
        related="order_line_id.qty_procured",
        digits="Product Unit of Measure",
    )
    quantity = fields.Float(
        digits="Product Unit of Measure",
    )

    @api.constrains("quantity")
    def _check_quantity(self):
        """Prevent delivering more than the ordered quantity"""
        if any(
            fields.Float.compare(
                line.quantity,
                line.qty_ordered - line.qty_procured,
                precision_rounding=line.product_id.uom_id.rounding,
            )
            > 0.00
            for line in self
        ):
            raise ValidationError(
                _(
                    "You can not deliver more than the remaining quantity. "
                    "If you need to do so, please edit the sale order first."
                )
            )
        if any(q < 0.0 for q in self.mapped("quantity")):
            raise ValidationError(_("You can not deliver a negative amount."))

    def _get_procurement_quantities(self):
        """Due to the mix of imperative style and business logic of
        _action_launch_stock_rule the qty to procure is calculated inside
        the function. Therefore we need the procurement quantities to be
        the order lines product_uom_qty - qty_to_procure = procurement_qty.
        Then within _action_launch_stock_rule it will reverse this logic.
        """
        return {
            mdl.order_line_id.id: mdl.order_line_id.product_uom_qty - mdl.quantity
            for mdl in self
            if mdl.quantity
        }
