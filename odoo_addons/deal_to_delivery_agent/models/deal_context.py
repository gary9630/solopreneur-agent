from odoo import fields, models


class DealContext(models.Model):
    _name = "deal.agent.deal.context"
    _description = "Deal-to-Delivery Agent Deal Context"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True)
    run_id = fields.Char(required=True, index=True)
    customer_name = fields.Char(required=True)
    contact_email = fields.Char()
    source_message = fields.Text()
    state = fields.Selection(
        [
            ("received", "Received"),
            ("qualified", "Qualified"),
            ("quoted", "Quoted"),
            ("delivery_planned", "Delivery Planned"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        required=True,
        default="received",
    )
    crm_lead_id = fields.Many2one("crm.lead", string="CRM Lead", ondelete="set null")
    sale_order_id = fields.Many2one("sale.order", string="Quotation", ondelete="set null")
    project_id = fields.Many2one("project.project", string="Delivery Project", ondelete="set null")
    invoice_id = fields.Many2one(
        "account.move",
        string="Draft Invoice",
        domain=[("move_type", "=", "out_invoice")],
        ondelete="set null",
    )
    audit_log_ids = fields.One2many(
        "deal.agent.audit.log",
        "deal_context_id",
        string="Agent Audit Logs",
    )
