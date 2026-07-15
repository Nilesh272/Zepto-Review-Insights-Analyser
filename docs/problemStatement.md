# AI-Powered User Feedback Analysis at Scale — Problem Statement

> Shareable overview for product, research, ops, and leadership.
> Companion docs: [`architecture.md`](./architecture.md), [`implementationPlan.md`](./implementationPlan.md).

---

## Summary

We are building an **AI-powered system that analyzes user feedback at scale**.

The system is an **AI agent** that ingests public App Store and Google Play reviews plus
**community feedback** (Reddit discussions, forum/social/product/quick-commerce drops),
runs embedding-based clustering and **research-question intelligence**, and publishes a
grounded insight briefing stakeholders can trust.

Current focus product: **Zepto** (quick commerce). Delivery today is a living HTML report
(local + Vercel); Google Docs / Gmail via **MCP** remain the architecture target for Workspace.

---

## Objective

Answer hard product-research questions from noisy store feedback — automatically, weekly,
idempotently — so teams do not manually read thousands of reviews.

For Zepto, the weekly pulse answers:

1. Why do users repeatedly buy from the same categories?
2. What prevents users from exploring new categories?
3. How do users discover products today?
4. What role do habits play in shopping behavior?
5. What information do users need before trying a new category?
6. What frustrations emerge repeatedly?
7. Which user segments are more likely to experiment?
8. What unmet needs emerge consistently across discussions?

---

## What “AI-powered at scale” means here

| Capability | Implementation |
|---|---|
| Ingest at scale | App Store + Google Play + Reddit search + community file drops; rolling window; thousands of items/run |
| Structure noise | Embeddings + density clustering (UMAP/HDBSCAN) with rating-stratified paths |
| Answer research Qs | AI insight engine maps reviews → fixed questionnaire (`insights_zepto.yaml`) |
| Generative upgrade | Optional `openai` backend synthesizes answers; default extractive AI analyst is offline-safe |
| Grounding | Quotes must appear **verbatim** in real reviews (`validate_quotes`) |
| Safety | PII scrubbing; reviews fenced as untrusted data for LLM prompts; per-run budget caps |
| Delivery | Append-only weekly section (HTML today; Google Docs MCP + Gmail MCP in architecture) |
| Scale ops | Weekly schedule (Monday), audit ledger, Vercel publish, idempotent re-runs |

---

## How it works (high level)

An **agent core** plans a tool chain for `(product, ISO week)`:

`fetch_reviews → scrub_pii → cluster_reviews → summarize/insights → validate_quotes → render_report → docs_append → gmail_draft_or_send`

Google Workspace interactions are MCP-only (credentials stay in MCP servers). Local/Vercel
HTML is the zero-setup transport used for Zepto demos.

---

## Key requirements

- **AI answers, not word clouds:** each research question gets a synthesized answer + evidence.
- **Grounded evidence:** every published quote is validated against real review text.
- **Scale:** ingest, analyze, and publish weekly without manual triage.
- **Idempotent:** same product+week never duplicates sections/sends.
- **Auditable:** ledger answers *what was sent when, for which week?*
- **Safe:** PII redaction; prompt-injection defense; cost/token budgets.

---

## Non-goals

- Real-time BI dashboards (weekly pulse briefing is the artifact).
- Social sources (Twitter/Reddit) in initial scope.
- Storing Google OAuth in the agent (belongs in MCP servers).

---

## Who this helps

| Audience | Value |
|---|---|
| Product / research | Category discovery & habit insights from real voice-of-customer |
| Ops / support | Recurring frustration themes ranked by volume |
| Leadership | Weekly AI briefing of customer health |

---

## Success criteria

- End-to-end run answers the configured research questionnaire with grounded quotes.
- Hundreds of reviews processed per product/week without manual copy-paste.
- Idempotent deliverable (HTML / Doc) updated weekly and redeployable.
- Optional LLM path available when `insights.backend` is `openai` or `groq`
  (set `OPENAI_API_KEY` or `GROQ_API_KEY` in `phase-7-orchestration/.env`;
  see `.env.example`).
