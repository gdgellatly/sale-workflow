# Copyright 2017 Denis Leemann, Camptocamp SA
# Copyright 2021 Iván Todorovich, Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_new_picking_values(self):
        """Overload to set partner_id and carrier_id from
        the manual delivery wizard
        """
        res = super()._get_new_picking_values()
        if partner_id := self.env.context.get("manual_partner_id"):
            res["partner_id"] = partner_id
        if carrier_id := self.env.context.get("manual_carrier_id"):
            res["carrier_id"] = carrier_id
        return res

    def _search_picking_for_assignation_domain(self):
        """Overload to filter partner_id and carrier_id"""
        domain = super()._search_picking_for_assignation_domain()
        if partner_id := self.env.context.get("manual_partner_id"):
            domain += [("partner_id", "=", partner_id)]
        if carrier_id := self.env.context.get("manual_carrier_id"):
            domain += [("carrier_id", "=", carrier_id)]
        return domain
