import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";

const DEFAULT_GATEWAY_BASE_URL = "http://host.openshell.internal:8088";

const strictObject = (properties, required = []) => ({
  type: "object",
  additionalProperties: false,
  properties,
  required,
});

const stringField = (description) => ({ type: "string", description });
const booleanField = (description) => ({ type: "boolean", description });
const objectField = (description) => ({
  type: "object",
  additionalProperties: true,
  description,
});
const arrayField = (description) => ({
  type: "array",
  items: { type: "object", additionalProperties: true },
  description,
});

function gatewayBaseUrl(config) {
  const configured = typeof config.gatewayBaseUrl === "string" ? config.gatewayBaseUrl.trim() : "";
  return (configured || DEFAULT_GATEWAY_BASE_URL).replace(/\/+$/, "");
}

async function postGateway(path, body, config, context) {
  context.signal?.throwIfAborted?.();
  const response = await fetch(`${gatewayBaseUrl(config)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: context.signal,
  });

  const text = await response.text();
  const payload = text ? parseJson(text) : {};
  if (!response.ok) {
    return {
      status: "error",
      status_code: response.status,
      detail: payload,
    };
  }
  return payload;
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return { raw_text: text };
  }
}

const configSchema = strictObject({
  gatewayBaseUrl: {
    ...stringField("Base URL for the host-side agent_app tool gateway."),
    default: DEFAULT_GATEWAY_BASE_URL,
  },
});

export default defineToolPlugin({
  id: "solopreneur-tools",
  name: "Solopreneur Tools",
  description: "Composable Odoo, delivery, and stakeholder tools for the solopreneur agent demo.",
  configSchema,
  tools: (tool) => [
    tool({
      name: "crm_lookup",
      label: "CRM Lookup",
      description: "Search Odoo contacts and CRM leads for a person, company, email, or deal keyword.",
      parameters: strictObject({
        query: stringField("Search text such as customer name, company, email, or lead title."),
        live: booleanField("Set true only when the operator wants to query live Odoo."),
      }, ["query"]),
      execute: ({ query, live = false }, config, context) => postGateway(
        "/tools/crm/lookup",
        { query, live },
        config,
        context,
      ),
    }),
    tool({
      name: "business_card_capture",
      label: "Business Card Capture",
      description: "Extract a business-card image and create or update the Odoo contact plus CRM lead.",
      parameters: strictObject({
        run_id: stringField("Stable id for this capture, for example telegram_card_123."),
        image_base64: stringField("Base64-encoded business-card image bytes."),
        mime_type: stringField("Image MIME type such as image/jpeg, image/png, or image/webp."),
        live: booleanField("Set true only when the operator wants to write live Odoo records."),
      }, ["run_id", "image_base64", "mime_type"]),
      execute: ({ run_id, image_base64, mime_type, live = false }, config, context) => postGateway(
        "/tools/crm/business-card",
        { run_id, image_base64, mime_type, live },
        config,
        context,
      ),
    }),
    tool({
      name: "deal_prepare",
      label: "Deal Prepare",
      description: "Turn a natural-language customer request into a deal brief, assumptions, quote draft, and delivery task plan without external side effects.",
      parameters: strictObject({
        run_id: stringField("Stable id for the deal preparation run."),
        message: stringField("Original customer or operator message."),
        live: booleanField("Keep false for preparation. Included for a consistent gateway contract."),
      }, ["run_id", "message"]),
      execute: ({ run_id, message, live = false }, config, context) => postGateway(
        "/tools/deal/prepare",
        { run_id, message, live },
        config,
        context,
      ),
    }),
    tool({
      name: "odoo_create_deal_artifacts",
      label: "Odoo Deal Artifacts",
      description: "Create Odoo CRM lead, quotation, draft invoice, deal context, and audit log after operator approval.",
      parameters: strictObject({
        run_id: stringField("Stable deal run id."),
        message: stringField("Original customer or operator message."),
        deal_brief: objectField("Prepared deal brief or intake summary from deal_prepare."),
        quote_draft: objectField("Prepared quote draft from deal_prepare."),
        live: booleanField("Set true only after operator approval and LIVE_WORKFLOW_ENABLED=1."),
      }, ["run_id", "message"]),
      execute: ({ run_id, message, deal_brief = {}, quote_draft = {}, live = false }, config, context) => postGateway(
        "/tools/odoo/deal-artifacts",
        { run_id, message, deal_brief, quote_draft, live },
        config,
        context,
      ),
    }),
    tool({
      name: "delivery_create_tasks",
      label: "Delivery Tasks",
      description: "Create Linear execution tasks and GitHub delivery tracking for an approved deal.",
      parameters: strictObject({
        run_id: stringField("Stable deal run id."),
        message: stringField("Original customer or operator message."),
        deal_brief: objectField("Prepared deal brief or intake summary from deal_prepare."),
        delivery_issues: arrayField("Prepared delivery issue list from deal_prepare."),
        live: booleanField("Set true only after operator approval and LIVE_WORKFLOW_ENABLED=1."),
      }, ["run_id", "message"]),
      execute: ({ run_id, message, deal_brief = {}, delivery_issues = [], live = false }, config, context) => postGateway(
        "/tools/delivery/tasks",
        { run_id, message, deal_brief, delivery_issues, live },
        config,
        context,
      ),
    }),
    tool({
      name: "notify_stakeholder",
      label: "Notify Stakeholder",
      description: "Send a concise Telegram stakeholder update after relevant Odoo, Linear, or GitHub refs exist.",
      parameters: strictObject({
        run_id: stringField("Stable deal or CRM run id."),
        message: stringField("Notification text to send."),
        external_refs: arrayField("External references already created and safe to mention."),
        live: booleanField("Set true only after operator approval and LIVE_WORKFLOW_ENABLED=1."),
      }, ["run_id", "message"]),
      execute: ({ run_id, message, external_refs = [], live = false }, config, context) => postGateway(
        "/tools/notify/stakeholder",
        { run_id, message, external_refs, live },
        config,
        context,
      ),
    }),
  ],
});
