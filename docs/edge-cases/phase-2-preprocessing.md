# Phase 2 — Preprocessing & Safety (`scrub_pii`) — Edge Cases

> Edge cases for [`implementationPlan.md`](../implementationPlan.md) Phase 2.

| ID | Edge case | Expected handling |
|---|---|---|
| X2.1 | Obfuscated email (`name [at] domain dot com`) | Detect common obfuscations; redact |
| X2.2 | International phone formats (+91, spaces, dashes) | Redact across formats; avoid matching plain years/amounts |
| X2.3 | Name that is also a product/feature word | Bias toward not over-redacting domain terms; tune NER |
| X2.4 | Account/card-like digits vs version numbers (`v12.4.1`) | Redact PANs/accounts; leave version numbers intact |
| X2.5 | PII embedded inside a would-be quote | Redacted before validation so published quotes are PII-free |
| X2.6 | Mixed-language review | Language detected per-review; scrub still applied |
| X2.7 | Code-switched text (Hinglish) | Classify per policy; don't drop valid signal silently |
| X2.8 | Empty / whitespace-only body after scrub | Drop or mark low-content; never emit empty quote |
| X2.9 | Over-redaction destroys meaning | Monitored via semantic-preservation eval; threshold tuning |
| X2.10 | Unicode homoglyph PII evasion | Normalize unicode before matching |
| X2.11 | Very high PII density review | Fully redacted; flagged, may be excluded from quoting |
| X2.12 | Language detector low confidence | Conservative default (keep + flag) rather than wrong drop |
