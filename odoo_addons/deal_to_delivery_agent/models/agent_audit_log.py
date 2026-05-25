from odoo import fields, models


class AgentAuditLog(models.Model):
    _name = "deal.agent.audit.log"
    _description = "Deal-to-Delivery Agent Audit Log"
    _order = "created_at desc, id desc"

    name = fields.Char(required=True)
    run_id = fields.Char(required=True, index=True)
    step_name = fields.Char(required=True)
    state_before = fields.Char()
    state_after = fields.Char()
    service = fields.Selection(
        [
            ("nim", "NIM"),
            ("nemoclaw", "NemoClaw"),
            ("odoo", "Odoo"),
            ("linear", "Linear"),
            ("github", "GitHub"),
            ("telegram", "Telegram"),
            ("agent", "Agent"),
        ],
        required=True,
        default="agent",
    )
    external_ref = fields.Char()
    payload_summary = fields.Text()
    created_at = fields.Datetime(required=True, default=fields.Datetime.now)
    deal_context_id = fields.Many2one(
        "deal.agent.deal.context",
        string="Deal Context",
        ondelete="cascade",
        index=True,
    )
