# Copyright 2017 Denis Leemann, Camptocamp SA
# Copyright 2021 Iván Todorovich, Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    qty_procured = fields.Float(
        string="Quantity Procured",
        help="Quantity already planned or shipped (stock movements already created)",
        compute="_compute_qty_procured",
        readonly=True,
        store=True,
        digits="Product Unit of Measure",
    )
    qty_to_procure = fields.Float(
        string="Quantity to Procure",
        help="There is Pending qty to add to a delivery",
        compute="_compute_qty_to_procure",
        store=True,
        readonly=True,
        digits="Product Unit of Measure",
    )

    @api.depends(
        "qty_delivered_method",
        "move_ids.state",
        "move_ids.scrapped",
        "move_ids.product_uom_qty",
        "move_ids.product_uom",
        "move_ids.location_id",
        "move_ids.location_dest_id",
    )
    def _compute_qty_procured(self):
        """
        Computes the already planned quantities for the given sale order lines,
        based on the existing stock.moves
        """
        for line in self:
            qty_procured = 0
            if line.qty_delivered_method == "stock_move":
                qty_procured = line.with_context(
                    manual_qty_to_procure=False
                )._get_qty_procurement(previous_product_uom_qty=False)
            line.qty_procured = qty_procured

    @api.depends("product_uom_qty", "qty_procured")
    def _compute_qty_to_procure(self):
        """Computes the remaining quantity to plan on sale order lines"""
        for line in self:
            line.qty_to_procure = line.product_uom_qty - line.qty_procured

    def _get_procurement_group(self):
        """Overload to get the procurement.group for the right date / partner"""
        if partner_id := self.env.context.get("manual_partner_id"):
            domain = [
                ("sale_id", "=", self.order_id.id),
                ("partner_id", "=", partner_id),
            ]
            if date_planned := self.env.context.get("manual_date_planned"):
                domain += [
                    ("date_planned", "=", date_planned),
                ]
            return self.env["procurement.group"].search(domain, limit=1)
        else:
            return super()._get_procurement_group()

    def _prepare_procurement_group_vals(self):
        """Overload to add manual.delivery fields to procurement.group"""
        res = super()._prepare_procurement_group_vals()
        if partner_id := self.env.context.get("manual_partner_id"):
            res["partner_id"] = partner_id
        if date_planned := self.env.context.get("manual_date_planned"):
            res["date_planned"] = date_planned
        return res

    def _prepare_procurement_values(self, group_id=False):
        """Overload to handle manual delivery date planned and route
        This method ultimately prepares stock.move vals as its result is sent
        to StockRule._get_stock_move_values.
        """
        res = super()._prepare_procurement_values(group_id=group_id)
        if date_planned := self.env.context.get("manual_date_planned"):
            res["date_planned"] = date_planned
        if route_id := self.env.context.get("manual_route_id"):
            res["route_ids"] = route_id
        return res

    def pending_delivery(self):
        """Return sales order lines with quantities still required to procure"""
        return self.filtered(
            lambda x: x.product_id.type in ["consu", "product"] and x.qty_to_procure > 0
        )

    def _get_qty_procurement(self, previous_product_uom_qty=False):
        """When procurement is called from the Create Delivery button on a manual
        delivery, return the quantity specified there"""
        self.ensure_one()
        if manual_qty_to_procure := self.env.context.get("manual_qty_to_procure"):
            qty = manual_qty_to_procure.get(self.id, self.product_uom_qty)
        else:
            qty = super()._get_qty_procurement(
                previous_product_uom_qty=previous_product_uom_qty
            )
        return qty

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """Overload to skip launching stock rules on manual delivery lines
        We only launch them when this is called from the manual delivery wizard
        """
        if "manual_qty_to_procure" in self.env.context:
            lines_to_launch = self
        else:
            manual_delivery_lines = self.filtered("order_id.manual_delivery")
            lines_to_launch = self - manual_delivery_lines
        return super(SaleOrderLine, lines_to_launch)._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty
        )
