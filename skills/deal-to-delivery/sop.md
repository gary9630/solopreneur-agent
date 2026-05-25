# Deal-to-Delivery SOP

This SOP keeps the hackathon demo repeatable and safe inside a NemoClaw sandbox.

## Inputs

- Customer request text.
- Operator confirmation for deal acceptance or invoice finalization.
- Environment variables and secrets supplied outside the repository.

## Steps

1. Parse the request into customer, contact, scope, urgency, budget, and delivery expectations.
2. Summarize uncertainty instead of inventing missing commercial terms.
3. Check safety boundaries:
   - Do not finalize invoices.
   - Do not mark a deal won without explicit acceptance.
   - Do not skip audit logs for external side effects.
4. Use the tool gateway for Odoo lead, quote, and draft invoice creation.
5. Use Linear for engineering execution tasks, each with owner intent and acceptance criteria.
6. Use GitHub for a delivery tracking issue that links back to Linear and Odoo.
7. Use Telegram for a concise stakeholder update after all references are available.
8. Return a compact run summary with final state, created references, and follow-up questions.

## Failure Handling

- If a side effect fails before a reference is returned, mark the step retryable.
- If a side effect succeeds but the confirmation response is unclear, ask the operator to inspect the external system before retrying.
- If a safety rule blocks the run, stop before the side effect and explain the exact missing approval.
