# Solopreneur Tool Use

Use the deal-to-delivery tools for CRM, Odoo deal artifacts, delivery work, and stakeholder updates.

In NemoClaw compact tool-catalog mode, the only visible tool may be `tool_search_code`. That is expected. Its `code` argument is a JavaScript body with these helpers:

```js
return await openclaw.tools.search("crm_lookup");
```

```js
return await openclaw.tools.describe("crm_lookup");
```

```js
return await openclaw.tools.call("crm_lookup", { query: "Ada Lovelace", live: false });
```

Rules:

- `openclaw.tools.search` takes a string, not `{ query: "..." }`.
- `openclaw.tools.describe` takes the exact tool name string.
- `openclaw.tools.call` takes the exact tool name string and a tool arguments object.
- Do not use `require(...)`, shell commands, `read`, `exec`, or `fetch` to discover these project tools.
- Keep `live` false unless the operator explicitly approves live mode and the host has `LIVE_WORKFLOW_ENABLED=1`.

Project tools:

- `crm_lookup`
- `business_card_capture`
- `deal_prepare`
- `odoo_upsert_contact`
- `odoo_create_crm_lead`
- `odoo_create_sale_order`
- `odoo_create_draft_invoice`
- `odoo_create_deal_artifacts`
- `delivery_create_tasks`
- `notify_stakeholder`
