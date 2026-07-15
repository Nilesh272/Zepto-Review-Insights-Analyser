# Phase 5 — Rendering (`render_report`) — Edge Cases

> Edge cases for [`implementationPlan.md`](../implementationPlan.md) Phase 5.

| ID | Edge case | Expected handling |
|---|---|---|
| X5.1 | Zero themes (low-signal week) | Render a clear "low-signal / few reviews" section, still dated + anchored |
| X5.2 | Theme with no validated quotes | Render summary + actions without quotes; no empty quote block |
| X5.3 | Very long theme/quote text | Truncate/format to keep one-page discipline; preserve quote verbatim within limit |
| X5.4 | Special chars in text (`<`, `&`, `*`, backticks) | Escaped correctly for HTML email and Docs text |
| X5.5 | Emoji / RTL / unicode in quotes | Rendered without corruption in both Docs + email |
| X5.6 | Product name with spaces/punctuation | Anchor still deterministic + valid (slugified) |
| X5.7 | Duplicate anchor string for different weeks | Impossible by construction (`year+week` in anchor); test guards it |
| X5.8 | Email client strips HTML | Plain-text alternative is self-sufficient w/ link |
| X5.9 | Deep-link placeholder unfilled | Render flags missing link; Phase 6 must fill before send |
| X5.10 | Extremely many themes | Cap to top-N; overflow summarized, not dumped |
| X5.11 | Docs request ordering | Requests ordered so heading/anchor precede body inserts |
| X5.12 | Quote mutated during formatting | Verbatim check guards against accidental edits |
