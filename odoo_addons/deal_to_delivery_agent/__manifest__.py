{
    "name": "Deal-to-Delivery Agent Bridge",
    "version": "0.1.0",
    "category": "Productivity",
    "summary": "Agent bridge for SME deal-to-delivery automation",
    "depends": ["base", "crm", "sale", "project", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/demo_products.xml",
        "views/agent_audit_log_views.xml",
        "views/deal_context_views.xml",
        "views/deal_agent_menus.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
