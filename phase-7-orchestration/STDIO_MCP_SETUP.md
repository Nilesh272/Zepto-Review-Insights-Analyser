# Writing a real Spotify pulse Doc (stdio MCP setup)

By design the agent **never holds Google credentials** and never calls the Docs/Gmail API
directly — it only speaks **MCP**. To write a real Google Doc you point it at a **Google Docs MCP
server** (and a **Gmail MCP server**) that own the OAuth and do the actual API calls. This guide
gets you from the offline `mock` transport to live delivery.

> The integration is generic: the agent launches your MCP server(s) and calls the tool names you
> declare in `config/settings.yaml`. Any MCP server that exposes Docs/Gmail tools will work.

---

## 1. Create the Spotify pulse Doc

1. In Google Docs, create a doc (e.g. **"Spotify — Weekly Review Pulse"**).
2. Copy its **document ID** from the URL:
   `https://docs.google.com/document/d/`**`<THIS_IS_THE_DOC_ID>`**`/edit`
3. Put it in `config/products.yaml`:

   ```yaml
   products:
     - id: spotify
       name: Spotify
       app_store_id: "324684580"
       play_package: "com.spotify.music"
       doc_id: "<THIS_IS_THE_DOC_ID>"
       recipients:
         - "you@yourcompany.com"
   ```
4. Share the doc with the Google account (or service account) your MCP server authenticates as,
   with **Editor** access.

## 2. Set up Google OAuth (lives in the MCP server, not the agent)

1. Google Cloud Console → create/select a project.
2. **Enable APIs**: *Google Docs API* and *Gmail API*.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID** → *Desktop app*.
   Download the JSON (commonly `credentials.json`).
4. Configure the OAuth consent screen and add your email as a **test user**.
5. Scopes the server will request:
   - Docs: `https://www.googleapis.com/auth/documents`
   - Gmail (draft): `https://www.googleapis.com/auth/gmail.compose`
   - Gmail (send): `https://www.googleapis.com/auth/gmail.send`
6. Keep `credentials.json` **out of this repo** (it belongs to the MCP server). The first run
   triggers a browser consent and caches a token in the server's own storage.

## 3. Provide the MCP server(s)

Use any MCP server that exposes Google Docs + Gmail tools (a community/npm server, or your own).
You need its **launch command** and its **tool names**. Examples of tools the agent needs:

| Agent operation | What it expects |
|---|---|
| `get_document(documentId)` | returns the doc with a `namedRanges` map (for idempotency) |
| `batch_update(documentId, requests)` | applies native Docs API `batchUpdate` requests |
| `delete_named_range(documentId, name)` *(optional)* | only needed for `--force` replace |
| `create_draft(to, subject, html, text)` | creates a Gmail draft |
| `send_message(to, subject, html, text)` | sends a Gmail message |

## 4. Wire it in `config/settings.yaml`

Set the transport and fill in the server launch + tool mapping (a template is in the file):

```yaml
mcp:
  transport: stdio
  docs_server:
    command: npx
    args: ["-y", "@your-org/google-docs-mcp"]
    env:
      GOOGLE_OAUTH_CREDENTIALS: /abs/path/to/credentials.json
  gmail_server:
    command: npx
    args: ["-y", "@your-org/gmail-mcp"]
    env:
      GOOGLE_OAUTH_CREDENTIALS: /abs/path/to/credentials.json
  docs_tools:           # rename to match YOUR server's tool names if different
    get_document: get_document
    batch_update: batch_update
    delete_named_range: null
    document_id_arg: documentId
    requests_arg: requests
    named_ranges_key: namedRanges
    heading_id_key: headingId
  gmail_tools:
    create_draft: create_draft
    send_message: send_message
    to_arg: to
    subject_arg: subject
    html_arg: html
    text_arg: text
    message_id_key: messageId
```

## 5. Install the MCP SDK and run

```bash
pip install mcp                # only needed for transport: stdio

# Draft-only first (safe). Dry-run validates the loop without any MCP writes:
python -m pulse.cli run --product spotify --week 2026-W26 --dry-run

# Real draft into Gmail + section appended to the Doc:
python -m pulse.cli run --product spotify --week 2026-W26

# When you're confident, send for real (explicit opt-in; everything else stays draft):
EMAIL_MODE=send python -m pulse.cli run --product spotify --week 2026-W26
```

Re-running the same `(product, week)` is **idempotent**: no duplicate section is appended and no
duplicate email is sent (ledger + Doc-anchor checks).

---

## Notes & limitations
- **Heading deep links:** the Docs API doesn't reliably expose a stable `#heading=…` id. The
  adapter uses the server's `headingId` if returned, otherwise falls back to the named-range id /
  section anchor, so the email always has a working doc link (it may land at the doc top rather
  than the exact heading, depending on your server).
- **`--force` replace** needs `docs_tools.delete_named_range` set to your server's tool; otherwise
  force is rejected with a clear error (re-running without force is still idempotent).
- **Errors** are normalized: not-found/auth failures fail fast (no REST fallback), transient
  failures retry with backoff, then mark the run `FAILED` (safe to re-run).
- Switching transports touches **only** `config` — no agent code changes, and still **no Google
  SDK** anywhere in the agent (`tests/test_mcp_boundary.py` enforces this).
