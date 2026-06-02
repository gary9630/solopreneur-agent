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
        live: booleanField("Set true when the operator approved full live workflow; this tool has no external side effects."),
      }, ["run_id", "message"]),
      execute: ({ run_id, message, live = false }, config, context) => postGateway(
        "/tools/deal/prepare",
        { run_id, message, live },
        config,
        context,
      ),
    }),
    tool({
      name: "odoo_upsert_contact",
      label: "Odoo Upsert Contact",
      description: "Create or update an Odoo contact before CRM, sales, or invoice artifacts are created.",
      parameters: strictObject({
        run_id: stringField("Stable deal run id."),
        customer_name: stringField("Customer or company name."),
        contact_name: stringField("Person name."),
        contact_email: stringField("Person email address."),
        phone: stringField("Optional phone number."),
        live: booleanField("Set true only after operator approval and LIVE_WORKFLOW_ENABLED=1."),
      }, ["run_id"]),
      execute: ({
        run_id,
        customer_name = null,
        contact_name = null,
        contact_email = null,
        phone = null,
        live = false,
      }, config, context) => postGateway(
        "/tools/odoo/contact",
        { run_id, customer_name, contact_name, contact_email, phone, live },
        config,
        context,
      ),
    }),
    tool({
      name: "odoo_create_crm_lead",
      label: "Odoo Create CRM Lead",
      description: "Create an Odoo CRM lead for an existing Odoo contact/partner id.",
      parameters: strictObject({
        run_id: stringField("Stable deal run id."),
        partner_id: stringField("Odoo res.partner id returned by odoo_upsert_contact."),
        customer_name: stringField("Customer or company name."),
        contact_name: stringField("Person name."),
        contact_email: stringField("Person email address."),
        phone: stringField("Optional phone number."),
        problem_statement: stringField("Short description of the customer need."),
        live: booleanField("Set true only after operator approval and LIVE_WORKFLOW_ENABLED=1."),
      }, ["run_id", "partner_id"]),
      execute: ({
        run_id,
        partner_id,
        customer_name = null,
        contact_name = null,
        contact_email = null,
        phone = null,
        problem_statement = null,
        live = false,
      }, config, context) => postGateway(
        "/tools/odoo/crm-lead",
        { run_id, partner_id, customer_name, contact_name, contact_email, phone, problem_statement, live },
        config,
        context,
      ),
    }),
    tool({
      name: "odoo_create_sale_order",
      label: "Odoo Create Sale Order",
      description: "Create an Odoo sale.order quotation for an existing Odoo contact/partner id.",
      parameters: strictObject({
        run_id: stringField("Stable deal run id."),
        partner_id: stringField("Odoo res.partner id returned by odoo_upsert_contact."),
        quote_draft: objectField("Prepared quote draft from deal_prepare."),
        live: booleanField("Set true only after operator approval and LIVE_WORKFLOW_ENABLED=1."),
      }, ["run_id", "partner_id", "quote_draft"]),
      execute: ({ run_id, partner_id, quote_draft, live = false }, config, context) => postGateway(
        "/tools/odoo/sale-order",
        { run_id, partner_id, quote_draft, live },
        config,
        context,
      ),
    }),
    tool({
      name: "odoo_create_draft_invoice",
      label: "Odoo Create Draft Invoice",
      description: "Create a draft Odoo customer invoice for an existing Odoo contact/partner id. Never finalizes invoices.",
      parameters: strictObject({
        run_id: stringField("Stable deal run id."),
        partner_id: stringField("Odoo res.partner id returned by odoo_upsert_contact."),
        quote_draft: objectField("Prepared quote draft from deal_prepare."),
        live: booleanField("Set true only after operator approval and LIVE_WORKFLOW_ENABLED=1."),
      }, ["run_id", "partner_id", "quote_draft"]),
      execute: ({ run_id, partner_id, quote_draft, live = false }, config, context) => postGateway(
        "/tools/odoo/draft-invoice",
        { run_id, partner_id, quote_draft, live },
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
    tool({
      name: "meeting_audio_process",
      label: "Meeting Audio",
      description: "Transcribe meeting audio and generate meeting minutes from Telegram or operator-provided audio.",
      parameters: strictObject({
        run_id: stringField("Stable id for this meeting audio run."),
        audio_base64: stringField("Base64-encoded audio bytes."),
        mime_type: stringField("Audio MIME type such as audio/wav, audio/mpeg, or audio/ogg."),
        filename: stringField("Optional filename from Telegram or upload source."),
        source: stringField("voice, audio, or document."),
        language_hint: stringField("Optional language hint such as zh-TW or en."),
        live: booleanField("Set true only after operator approval and LIVE_WORKFLOW_ENABLED=1."),
      }, ["run_id", "audio_base64", "mime_type"]),
      execute: ({
        run_id,
        audio_base64,
        mime_type,
        filename = null,
        source = "audio",
        language_hint = null,
        live = false,
      }, config, context) => postGateway(
        "/tools/meeting/audio",
        { run_id, audio_base64, mime_type, filename, source, language_hint, live },
        config,
        context,
      ),
    }),
  ],
});
