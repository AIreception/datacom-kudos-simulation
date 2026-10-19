# Kudos System — Technical Design

- **Status:** DRAFT v0.1 — awaiting review and explicit approval
- **Date:** 2026-10-18
- **Project:** Datacom Forage Task 2 — standalone Kudos demo
- **Related document:** [REQUIREMENTS.md](REQUIREMENTS.md)

> **This is a proposal, not an approved design.** No application code has been written. Assumptions are labelled and must not be read as approved requirements. Content moderation is deliberately **not designed** in this draft; see REQUIREMENTS.md OQ-01 and Task 2 Step 2.

---

## 1. Design Goals and Constraints

| Goal | Consequence |
|---|---|
| Small and locally runnable | One Python web process and one SQLite file. No containers or external services. |
| Persistent storage | Data lives in `data/kudos.db` and survives restarts. |
| Minimal dependencies | Flask only at runtime; pytest only for development. No ORM, no frontend framework, no build step. |
| Beginner-readable | Plain SQL, small modules, request flow traceable from browser to database. |
| Secure by construction within demo limits | Server-side validation, parameterised SQL, safe DOM rendering, signed session cookie, security headers. |
| Honest demo identity | A visible picker and an explicit "demo only" label; never presented as real authentication. |
| Production-extensible | Clear seams for SSO, moderation, roles, and a different database. |

**Verified environment (2026-10-18):**

- Python **3.9.6** is installed at `/usr/bin/python3`.
- SQLite **3.54.0** is available both as a CLI and via Python's standard library.
- Node.js and npm are **not** installed.
- Flask is not installed yet; it will be installed into a virtual environment during implementation.

Because Node.js is unavailable and Python 3.9 with SQLite is already present, the design uses Python + Flask + the standard-library `sqlite3` module. Installing Node would add setup work without improving the demo.

---

## 2. Proposed Stack and Rationale

### 2.1 Chosen Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.9+ | Already installed; readable for beginners. |
| Web framework | Flask 3.1.x | One small dependency; simple routing; built-in test client; no build step. |
| Database | SQLite via stdlib `sqlite3` | File-based persistence, real SQL schema, zero server setup, no extra dependency. |
| DB access | Plain SQL + `sqlite3.Row` | Transparent; teaches what the ORM would hide. |
| Templates | Jinja2 (bundled with Flask) | One HTML shell; no client-side routing needed. |
| Frontend | Vanilla HTML, CSS, ES modules | No install/build; easy to inspect and debug. |
| Tests | pytest + Flask test client | Standard, readable; no running server or HTTP library needed. |

**Runtime dependencies:** `Flask` (which brings Werkzeug, Jinja2, itsdangerous, click, MarkupSafe).
**Development dependencies:** `pytest`.
**No** database driver package, ORM, migration library, frontend framework, bundler, or CSS framework.

### 2.2 Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Node.js + Express + better-sqlite3 | Node is not installed. Would add a runtime install and a native module build step. |
| Django | Much larger than needed; its admin, ORM, and project layout obscure the simple request flow. |
| FastAPI + Uvicorn | Adds async concepts and Pydantic; more moving parts for a beginner. |
| React/Vue + build tooling | Adds npm, a bundler, and a separate dev server for a one-page demo. |
| JSON file storage | Simpler, but loses relational integrity, SQL querying, and a credible schema for the specification. |
| PostgreSQL | Requires a server, credentials, and operations; unnecessary at demo scale. |

If the reviewer prefers Node, the architecture and API contract remain valid; only the implementation stack changes.

### 2.3 Version Pinning

`requirements.txt` will pin compatible major/minor ranges rather than exact patch versions:

```text
Flask>=3.1,<3.2
```

`requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8.3,<9
```

Python 3.9 is end-of-life upstream; the demo works, but production should use a supported Python version (3.11+ proposed).

---

## 3. System Architecture

### 3.1 Overview

```text
┌─────────────────────────────────────────────────────────────┐
│ Browser                                                     │
│  index.html + styles.css + app.js/api.js (ES modules)       │
│  - identity picker                                          │
│  - kudos composer                                           │
│  - feed + "Load more"                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ same-origin HTTP, JSON + signed cookie
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Flask application (single process)                          │
│                                                             │
│  app.py      app factory, config, page route, error handlers│
│  api.py      /api blueprint: demo identity, users, kudos    │
│  validation.py  input parsing and product rules             │
│  db.py       SQLite connection, schema init, seed data      │
│  schema.sql  tables, constraints, indexes                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ parameterised SQL
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ data/kudos.db  (SQLite file, WAL mode, foreign keys ON)     │
└─────────────────────────────────────────────────────────────┘
```

There is one origin and no CORS. Flask serves both the HTML shell and the JSON API. The browser never talks to SQLite directly.

### 3.2 Key Flows

**First visit / demo sign-in**

1. Browser loads `GET /` → HTML shell.
2. `app.js` calls `GET /api/me` → `401`.
3. `app.js` calls the demo-only `GET /api/demo/users` and renders the identity picker.
4. The user chooses a seeded employee → `POST /api/demo/session`.
5. The server validates the user, clears any old session, sets `session["user_id"]`, and returns the user.
6. The browser loads the colleague list and first feed page.

**Submitting kudos**

1. User selects a recipient and writes a message.
2. `POST /api/kudos` with JSON `{ "recipientId": 2, "message": "..." }`.
3. Flask's `login_required` decorator resolves the giver from the signed session cookie.
4. `validation.py` validates and trims the input; `db.py` inserts one row in a transaction.
5. The server returns `201` with the created kudos (joined with names).
6. The UI clears the composer, shows a success message, and refreshes the first feed page so the new item appears at the top.

**Feed read**

1. `GET /api/kudos?limit=20&offset=0`.
2. The server reads the session, validates pagination parameters, and runs one indexed `JOIN` query for `limit + 1` rows.
3. The extra row determines `hasMore` without a separate `COUNT`.
4. The server returns items and pagination metadata.

### 3.3 Request Lifecycle

```text
Request
  → before_request: assign request_id, start timer
  → session/auth guard (protected routes)
  → route handler
      → validation.py
      → db.py (connection from flask.g)
  → after_request: security headers, X-Request-Id, access log
  → teardown_appcontext: close DB connection
```

---

## 4. Application Structure

```text
kudos-app/
├── app.py                  # create_app(), config, page route, CLI entry point
├── api.py                  # Flask blueprint for /api routes
├── db.py                   # get_db(), close_db(), init_db(), seed_db()
├── validation.py           # ValidationError, validate_message(), parse_ids()
├── schema.sql              # CREATE TABLE / INDEX statements
├── seed.sql                # 8 fictional demo users (INSERT OR IGNORE)
├── requirements.txt        # Flask
├── requirements-dev.txt    # -r requirements.txt + pytest
├── README.md               # setup, run, demo identity caveat, test commands
├── .gitignore              # .venv/, data/, __pycache__/, .pytest_cache/
├── templates/
│   └── index.html          # single page shell + <template> for a kudos card
├── static/
│   ├── css/
│   │   └── styles.css      # tokens, layout, components, responsive rules
│   └── js/
│       ├── api.js          # fetch wrapper, ApiError, endpoint helpers
│       └── app.js          # state, rendering, events
├── data/                   # created at runtime; gitignored
│   └── kudos.db            # SQLite database
└── tests/
    ├── conftest.py         # app/client/db fixtures with temp database
    ├── test_validation.py  # unit tests for product rules
    ├── test_api_auth.py    # demo session and 401 behaviour
    ├── test_api_users.py   # colleague list
    ├── test_api_kudos.py   # create + validation + authorisation
    └── test_api_feed.py    # order, pagination, hasMore
```

**Why this layout:** each file has one responsibility and can be read in one sitting. `app.py` stays small because API routes live in `api.py`. There is no `__init__.py` package, which keeps imports and the run command simple.

---

## 5. Data Design

### 5.1 Design Principles

- Normalised: giver and recipient reference a single `users` table.
- IDs are integer primary keys.
- Timestamps are ISO 8601 UTC strings (`YYYY-MM-DDTHH:MM:SS.sssZ`), which sort correctly and are readable.
- Foreign keys are enforced.
- Messages are stored as plain text, exactly as submitted after trimming; rendering is responsible for safety.
- Moderation columns are **not** added in this draft. They will be specified in Task 2 Step 2.

### 5.2 Entity Relationship

```text
users 1 ─────< kudos (as giver_id)
users 1 ─────< kudos (as recipient_id)

kudos
  id            PK
  giver_id      FK → users.id
  recipient_id  FK → users.id
  message       TEXT
  created_at    TEXT (UTC ISO 8601)
```

### 5.3 Schema (`schema.sql`)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    department  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS kudos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    giver_id      INTEGER NOT NULL REFERENCES users(id),
    recipient_id  INTEGER NOT NULL REFERENCES users(id),
    message       TEXT    NOT NULL
                  CHECK (length(trim(message)) BETWEEN 1 AND 500),
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (giver_id <> recipient_id)
);

CREATE INDEX IF NOT EXISTS idx_kudos_created_at
    ON kudos (created_at DESC, id DESC);
```

### 5.4 Field Rationale

| Field | Rationale |
|---|---|
| `users.id` | Stable internal identifier. Not an email, so a person's email can change. |
| `users.email` | Unique directory key for seed data and future SSO mapping. Not exposed by the colleague API. |
| `users.department` | Helps users distinguish colleagues with similar names and is useful seed context. |
| `users.is_active` | Allows leavers or hidden demo users without deleting historical kudos. |
| `kudos.giver_id` | Who gave recognition. Always derived from the session. |
| `kudos.recipient_id` | Who received it. |
| `kudos.message` | Plain text, 1–500 code points after trimming. |
| `kudos.created_at` | UTC timestamp used for ordering and display. |
| `idx_kudos_created_at` | Serves the feed's `ORDER BY created_at DESC, id DESC` with `LIMIT`/`OFFSET`. |

### 5.5 Constraints and Assumptions

- `CHECK (giver_id <> recipient_id)` encodes proposed rule **A-07**. If self-kudos are approved later, this constraint and application validation must change.
- The message `CHECK` encodes proposed rule **A-08**. SQLite's `length()` on `TEXT` counts Unicode code points, matching Python's `len()`.
- The app trims whitespace before insert. SQLite's `trim()` only removes ASCII spaces, so the application remains authoritative for whitespace-only rejection.
- Foreign keys prevent orphaned kudos but do not define delete behaviour. Users should be deactivated rather than deleted. A production delete policy is an open question.
- SQLite cannot easily drop a `CHECK` constraint; changing A-07/A-08 after data exists may require a table rebuild. Confirm these rules before implementation.

### 5.6 Seed Data (`seed.sql`)

Eight fictional employees, inserted idempotently with `INSERT OR IGNORE` on the unique email:

| Name | Department | Email |
|---|---|---|
| Alice Ng | Engineering | alice.ng@example.internal |
| Ben Okafor | Product | ben.okafor@example.internal |
| Carla Mendes | Design | carla.mendes@example.internal |
| Daniel Kim | Engineering | daniel.kim@example.internal |
| Elif Yilmaz | People & Culture | elif.yilmaz@example.internal |
| Farhan Ali | Finance | farhan.ali@example.internal |
| Grace Chen | Customer Success | grace.chen@example.internal |
| Hemi Walker | Security | hemi.walker@example.internal |

All data is fictional. No real Datacom employee data, names, or email addresses are used.

No admin user or role is seeded in this draft. Moderation roles belong to Task 2 Step 2.

### 5.7 Database Access

`db.py` provides:

- `get_db()` — opens one connection per request, stores it on `flask.g`, sets `row_factory = sqlite3.Row`, enables `PRAGMA foreign_keys = ON` and `PRAGMA busy_timeout = 5000`.
- `close_db(exception)` — registered with `app.teardown_appcontext`.
- `init_db()` — creates the data directory and executes `schema.sql`.
- `seed_db()` — executes `seed.sql`; safe to run repeatedly.
- `init_app(app)` — registers teardown and runs schema + seed at startup.
- `transaction()` — context manager that commits on success and rolls back on error.

The database is opened in WAL mode once during initialisation (`PRAGMA journal_mode = WAL`) for better read/write concurrency. All queries use `?` placeholders; no SQL string interpolation of user input.

### 5.8 Migrations

- **Demo:** `schema.sql` uses `CREATE TABLE IF NOT EXISTS`, and seed data uses `INSERT OR IGNORE`. There is no migration framework.
- **Adding moderation later:** SQLite supports `ALTER TABLE kudos ADD COLUMN ...`. Task 2 Step 2 will update `schema.sql` and DESIGN.md. If existing databases must be upgraded, `PRAGMA user_version` with a small ordered migration list is the proposed next step.
- **Production:** numbered, reviewed migrations (for example, Alembic if the team adopts SQLAlchemy, or plain ordered `.sql` files with `user_version`) and backups before migration.

### 5.9 Expected Scale

The demo targets tens of users and low thousands of kudos. SQLite with WAL and one indexed feed query is comfortably sufficient. SQLite allows one writer at a time; that is acceptable for a local demo and a low-write internal tool. Production should reassess if concurrency or multi-instance deployment is required.

---

## 6. Demo Identity and Production Path

### 6.1 Demo Identity (Proposed)

**Mechanism:** Flask's built-in signed session cookie.

1. The page loads and calls `GET /api/me`.
2. If unauthenticated, the UI shows `GET /api/demo/users` — all active seeded users, exposing only `id`, `name`, and `department`.
3. Choosing a user calls `POST /api/demo/session` with `{ "userId": 1 }`.
4. The server verifies the user exists and is active, calls `session.clear()`, sets `session.permanent = True`, and stores `session["user_id"]`.
5. Flask signs the cookie with `SECRET_KEY`. The cookie is `HttpOnly` and `SameSite=Lax`.
6. Every protected route reads the user from the session. The browser never supplies the giver identity.

**What this demonstrates:** the production-shaped pattern where the server, not the request body, determines the actor.

**What this does not provide:**

- Proof of identity. Anyone who can reach the app can choose any seeded user.
- Password, MFA, account recovery, or session revocation.
- Protection against someone with the signing secret forging a cookie.

**Mitigations and honesty requirements:**

- The UI displays a visible banner: "Demo mode — identity is simulated."
- The README and spec state that the demo is local-only and must not be deployed.
- The app binds to `127.0.0.1` by default.
- Demo routes are controlled by `ALLOW_DEMO_LOGIN`, which defaults to `True` for the demo and must be `False` in production (routes then return 404).
- If `SECRET_KEY` is not set, the app generates an ephemeral secret and logs a warning; sessions reset on restart.
- `SESSION_COOKIE_SECURE` defaults to `False` for local HTTP and must be `True` behind HTTPS.

### 6.2 Production Identity (Not Implemented)

Proposed production path:

1. Integrate with Datacom's SSO using OIDC (authorization code + PKCE) or SAML.
2. Map the verified token's stable subject and email to the `users` table; sync names and departments from the directory.
3. Use a server-side session (or short-lived signed token) with secure, HttpOnly, `SameSite=Lax` cookies over HTTPS.
4. Derive roles (employee, administrator) from directory groups; never trust a client-supplied role.
5. Remove or disable the demo endpoints.
6. Enforce CSRF tokens on state-changing requests.
7. Add rate limiting and audit logging.

This path preserves the API contract: handlers still ask the session for the current user. Only the authentication layer changes.

---

## 7. API Specification

### 7.1 Conventions

- Base path: `/api`.
- Requests and responses are JSON unless stated otherwise.
- Successful responses use top-level objects (`{"user": ...}`), not bare arrays, so fields can be added later.
- Errors use one envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Please correct the highlighted fields.",
    "fields": {
      "message": "Message must be between 1 and 500 characters."
    },
    "requestId": "6f1c2a7e-..."
  }
}
```

- `fields` is present only for validation errors.
- `requestId` is also returned in the `X-Request-Id` response header.
- Unknown JSON properties are ignored. A client-supplied `giverId` is ignored for security.
- All protected endpoints require a valid demo session.

### 7.2 Endpoint Summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | No | HTML application shell |
| GET | `/api/health` | No | Liveness check |
| GET | `/api/demo/users` | No (demo only) | List users for the identity picker |
| POST | `/api/demo/session` | No (demo only) | Choose a demo identity |
| DELETE | `/api/demo/session` | No | Clear the demo session |
| GET | `/api/me` | Yes | Current demo user |
| GET | `/api/users` | Yes | Active colleague list |
| GET | `/api/kudos` | Yes | Paginated feed |
| POST | `/api/kudos` | Yes | Create kudos |

Moderation endpoints are **not defined** in this draft. They will be added in Task 2 Step 2.

### 7.3 Endpoint Details

#### `GET /api/health`

- **Response:** `200 {"status":"ok"}`.
- May optionally execute `SELECT 1` against the database; no detail is exposed.

#### `GET /api/demo/users` (Demo Only)

- **Purpose:** Populate the identity picker before a session exists.
- **Response:** `200`

```json
{
  "users": [
    {"id": 1, "name": "Alice Ng", "department": "Engineering"},
    {"id": 2, "name": "Ben Okafor", "department": "Product"}
  ]
}
```

- Active users only, sorted by name.
- No emails or timestamps.
- Returns `404` when `ALLOW_DEMO_LOGIN` is false.

#### `POST /api/demo/session` (Demo Only)

- **Request:**

```json
{"userId": 1}
```

- **Behaviour:** validates the user, clears the old session, sets `user_id`, marks the session permanent.
- **Success:** `200`

```json
{"user": {"id": 1, "name": "Alice Ng", "department": "Engineering"}}
```

- **Errors:** `400 VALIDATION_ERROR` (missing/non-integer/bool), `404 USER_NOT_FOUND` (unknown or inactive).
- Returns `404` when demo login is disabled.

#### `DELETE /api/demo/session`

- Clears the session.
- **Response:** `204 No Content` (idempotent; succeeds even with no session).

#### `GET /api/me`

- **Success:** `200 {"user": {...}}`.
- **Failure:** `401 UNAUTHENTICATED`.

#### `GET /api/users`

- **Purpose:** Colleague list for the composer.
- Active users only; includes the current user (the UI excludes self) so the endpoint stays generally useful.
- Sorted by `name COLLATE NOCASE ASC`.
- **Response:** `200`

```json
{
  "users": [
    {"id": 1, "name": "Alice Ng", "department": "Engineering"},
    {"id": 2, "name": "Ben Okafor", "department": "Product"}
  ]
}
```

- No email addresses are returned.

#### `GET /api/kudos`

- **Query parameters:**

| Name | Type | Default | Rules |
|---|---|---|---|
| `limit` | integer | 20 | 1–50 |
| `offset` | integer | 0 | ≥ 0 |

- **Response:** `200`

```json
{
  "items": [
    {
      "id": 12,
      "message": "Thank you for staying late to help with the release!",
      "createdAt": "2026-10-18T09:12:34.567Z",
      "giver": {"id": 1, "name": "Alice Ng"},
      "recipient": {"id": 2, "name": "Ben Okafor"}
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "hasMore": false,
    "nextOffset": null
  }
}
```

- Ordering: `created_at DESC, id DESC`.
- The server queries `limit + 1` rows to compute `hasMore` without `COUNT(*)`.
- `nextOffset` is `offset + len(items)` when `hasMore`, otherwise `null`.
- **Errors:** `400 VALIDATION_ERROR` with `fields.limit` or `fields.offset`; `401 UNAUTHENTICATED`.

#### `POST /api/kudos`

- **Request:**

```json
{"recipientId": 2, "message": "Thank you for your help!"}
```

- **Behaviour:** giver = session user; trim message; validate; insert; return the joined row.
- **Success:** `201`

```json
{
  "kudos": {
    "id": 13,
    "message": "Thank you for your help!",
    "createdAt": "2026-10-18T10:00:00.001Z",
    "giver": {"id": 1, "name": "Alice Ng"},
    "recipient": {"id": 2, "name": "Ben Okafor"}
  }
}
```

- **Errors:**

| Status | Code | Condition |
|---|---|---|
| 400 | `INVALID_JSON` | Body is not valid JSON |
| 400 | `VALIDATION_ERROR` | Missing/invalid field, empty message, > 500 characters, control characters |
| 400 | `SELF_KUDOS` | Recipient equals session user (proposed rule A-07) |
| 401 | `UNAUTHENTICATED` | No valid session |
| 404 | `RECIPIENT_NOT_FOUND` | Recipient missing or inactive |
| 413 | `PAYLOAD_TOO_LARGE` | Body exceeds 16 KB |
| 500 | `INTERNAL_ERROR` | Unexpected failure; log with request ID |

- The server ignores any `giverId`, `createdAt`, or `id` sent by the client.

### 7.4 Query Used by the Feed

```sql
SELECT
    k.id,
    k.message,
    k.created_at,
    g.id   AS giver_id,
    g.name AS giver_name,
    r.id   AS recipient_id,
    r.name AS recipient_name
FROM kudos AS k
JOIN users AS g ON g.id = k.giver_id
JOIN users AS r ON r.id = k.recipient_id
ORDER BY k.created_at DESC, k.id DESC
LIMIT ? OFFSET ?;
```

- One query, no N+1.
- Uses `idx_kudos_created_at`.
- The `id DESC` tiebreaker makes ordering deterministic.

### 7.5 Status Codes

| Code | Meaning in this API |
|---|---|
| 200 | Successful read or demo login |
| 201 | Kudos created |
| 204 | Session cleared |
| 400 | Malformed JSON, invalid parameters, validation failure, self-kudos |
| 401 | No valid session |
| 404 | Unknown route, user, or recipient; demo routes disabled |
| 405 | Wrong HTTP method |
| 413 | Request body too large |
| 500 | Unexpected server error |

---

## 8. Frontend Design

### 8.1 Approach

A single server-rendered HTML shell with a small vanilla JavaScript application. No framework, router, state library, or build step. ES modules are loaded with `<script type="module" src="/static/js/app.js">`.

### 8.2 Page Structure

```text
<body>
  <header class="app-header">
    <h1>Kudos</h1>
    <div id="user-menu" hidden>
      <span>Signed in as <strong id="current-user-name"></strong></span>
      <span class="demo-badge">Demo mode — identity is simulated</span>
      <button id="switch-user">Switch user</button>
    </div>
  </header>

  <main>
    <section id="identity-picker" hidden aria-labelledby="identity-title">
      <h2>Choose a demo user</h2>
      <p>This is not a real login.</p>
      <ul id="identity-list"></ul>
    </section>

    <div id="app-content" hidden>
      <section aria-labelledby="composer-title">
        <h2>Give kudos</h2>
        <form id="kudos-form" novalidate>
          <label for="recipient">Colleague</label>
          <select id="recipient" required></select>

          <label for="message">Message</label>
          <textarea id="message" rows="4" required
                    aria-describedby="char-count message-error"></textarea>
          <div id="char-count" aria-live="polite">0 / 500</div>
          <p id="message-error" class="field-error" hidden></p>

          <button type="submit">Send kudos</button>
        </form>
        <p id="form-status" role="status" aria-live="polite"></p>
      </section>

      <section aria-labelledby="feed-title">
        <h2>Recent kudos</h2>
        <p id="feed-status" role="status" aria-live="polite"></p>
        <ol id="feed-list"></ol>
        <p id="feed-empty" hidden>No kudos yet. Be the first to recognise a colleague.</p>
        <button id="load-more" hidden>Load more</button>
      </section>
    </div>
  </main>

  <div id="toast-region" aria-live="polite" aria-atomic="true"></div>

  <template id="kudos-card-template">
    <li class="kudos-card">
      <p class="kudos-card__meta">
        <span class="kudos-card__giver"></span> → <span class="kudos-card__recipient"></span>
      </p>
      <p class="kudos-card__message"></p>
      <time class="kudos-card__time"></time>
    </li>
  </template>
</body>
```

The exact markup may change during implementation, but these behaviours and accessible relationships are required.

### 8.3 Component Responsibilities

| Component | Responsibility |
|---|---|
| **App shell** | Header, main region, identity picker, composer, feed, toast region. |
| **Identity picker** | Fetches demo users, presents an accessible button list, signs in, shows errors. |
| **User menu** | Shows current user and the demo-mode warning; clears the session on "Switch user". |
| **Composer** | Loads colleagues, excludes self, enforces the counter, submits, reports field errors, prevents double submission. |
| **Feed** | Loads the first page, renders cards, appends subsequent pages, deduplicates by ID, shows empty/error states. |
| **Kudos card** | Clones the `<template>` and fills text nodes; renders message with `textContent`. |
| **Toast/status** | Announces success and non-field errors with `aria-live`. |

### 8.4 Client State

```js
const state = {
  me: null,                 // current demo user
  users: [],                // active colleagues
  kudos: [],                // loaded feed items, newest first
  offset: 0,                // server offset for the next page
  hasMore: false,
  loadingFeed: false,
  submitting: false,
};
```

State is in memory only. No `localStorage`, because the server session is the source of truth and sensitive data should not be persisted by the client.

### 8.5 Interaction Details

**Initial load**

1. `GET /api/me`.
2. If 401: fetch `/api/demo/users`, render the picker, leave the app content hidden.
3. If 200: show the header, load `/api/users` and `/api/kudos?limit=20&offset=0` in parallel.

**Identity selection**

- Buttons show name and department.
- During the request, disable all identity buttons and set `aria-busy="true"`.
- On success, hide the picker, show the app, load data.
- On failure, show an inline error and keep the picker visible.

**Composer**

- Populate `<select>` with active users other than `state.me`.
- Sort by name (the server already sorts; the client filters self and preserves order).
- If no colleagues remain, disable the select and submit, and show an explanation.
- Counter: `Array.from(message).length` (Unicode code points) to match Python's `len()`. Do not rely on `maxlength`, which counts UTF-16 code units and would treat emoji differently.
- Client-side validation is a convenience; the server repeats every rule.
- On submit:
  - If already submitting, return immediately.
  - Disable the button, set its text to "Sending…", and set `aria-busy`.
  - POST the request.
  - On 201: clear the message, reset the counter, show a success toast, and reload the first feed page so the new kudos appears at the top. Reloading (rather than prepending) avoids offset drift for "Load more".
  - On 400: show the field error, move focus to the field or error summary.
  - On 401: clear client state and return to the identity picker with a notice.
  - On network/500: show a retryable error and keep the message so the user does not lose it.
  - Always re-enable the button in `finally`.

**Feed**

- Render each item with the template; set giver, recipient, message, and time via `textContent`.
- Relative time: `Intl.RelativeTimeFormat` for recent items, with an absolute timestamp in the `title` attribute and a `<time datetime="...">` element.
- Long text: `overflow-wrap: anywhere` and `white-space: pre-wrap` for line breaks, so unbroken strings and newlines do not break the layout.
- "Load more": fetch with `offset = pagination.nextOffset`; append only IDs not already present; hide the button when `hasMore` is false.
- Empty feed: show the empty state, not an error.
- Feed error: show a retry control; keep already-loaded items visible.

**Session expiry**

- Any 401 from a protected endpoint triggers a single transition back to the picker, with a "Your demo session ended" notice. Avoid showing repeated errors for parallel requests.

### 8.6 Rendering Safety

- **Never** use `innerHTML` with kudos text, names, departments, or error messages.
- Create elements and assign `.textContent`.
- The Jinja template autoescapes any server-rendered values; in this design the shell contains no user data.
- The Content-Security-Policy forbids inline scripts and styles, so all JS and CSS live in external files.
- URLs are never constructed from user input.

### 8.7 Responsive Design

- Mobile-first CSS; base styles target 320 px and up.
- Content column: `max-width: 760px`, centred, with 16 px side padding.
- Header wraps on narrow screens; the user menu stacks below the title if needed.
- The composer is a single column; on screens ≥ 640 px the counter and submit button sit in a row.
- Feed cards use full width and 12–16 px padding.
- Primary controls are at least 44 × 44 CSS pixels.
- Form controls use `font-size: 16px` or larger to prevent iOS zoom.
- Breakpoints: base (mobile), `@media (min-width: 640px)`, `@media (min-width: 1024px)` where useful.
- No horizontal scrolling at 320 px; test with long messages and long names.
- Respect `prefers-reduced-motion` for toast transitions.

### 8.8 Accessibility

- One `<h1>`, sections with `<h2>` and `aria-labelledby`.
- Native `<label for>`, `<select>`, `<textarea>`, `<button>`.
- Visible `:focus-visible` outline with sufficient contrast.
- Character counter and error text connected through `aria-describedby`.
- `role="status"` / `aria-live="polite"` for success, loading, and feed counts; `role="alert"` for blocking errors.
- After a failed submit, focus the error summary or the first invalid field.
- Keyboard-only path: choose identity → select recipient → type → submit → load more.
- Colour contrast at least 4.5:1 for body text; do not rely on colour alone.
- Test with VoiceOver on macOS as a manual check.

### 8.9 Progressive Enhancement

The app requires JavaScript to display data because the API is client-fetched. The HTML shell remains readable if JavaScript fails, and the UI shows a message if `fetch` is unavailable. A server-rendered fallback is out of scope.

---

## 9. Security Considerations

### 9.1 Demo Posture

The demo is explicitly **not secure for real use**:

- Anyone who can reach the port can impersonate any seeded user.
- There are no passwords, MFA, roles, or account recovery.
- The app binds to `127.0.0.1` by default.
- The UI and README state this limitation.
- Only fictional data is used.

These are acceptable **only** because the app is local and is a learning exercise. They must not be carried into production.

### 9.2 Implemented Controls

| Threat | Control |
|---|---|
| **SQL injection** | Every query uses `?` placeholders; no string interpolation. |
| **XSS** | Messages stored as plain text; rendered with `textContent`; no `innerHTML`; Jinja autoescape; strict CSP; `X-Content-Type-Options: nosniff`. |
| **Session tampering** | Flask signs the cookie with `SECRET_KEY`; `HttpOnly`; `SameSite=Lax`; session ID is not exposed to JS. |
| **Session fixation** | `session.clear()` before setting the demo user. |
| **CSRF (basic)** | `SameSite=Lax` blocks cookies on cross-site POSTs; the API accepts JSON, which is not a simple cross-site form submission. |
| **Oversized requests** | `MAX_CONTENT_LENGTH = 16 KB`; `413` response. |
| **Mass assignment** | Only `recipientId` and `message` are read; `giverId`, `id`, and `createdAt` are ignored. |
| **Identity spoofing via body** | Giver always comes from the server session. |
| **Error leakage** | Generic 500 message; details only in server logs; `DEBUG` off by default. |
| **Clickjacking** | `frame-ancestors 'none'` in CSP and `X-Frame-Options: DENY`. |
| **Referrer leakage** | `Referrer-Policy: no-referrer`. |
| **MIME sniffing** | `X-Content-Type-Options: nosniff`. |
| **Dependency risk** | Few dependencies, pinned ranges, `pip-audit` recommended in CI. |

**Proposed response headers:**

```text
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self';
  img-src 'self' data:; connect-src 'self'; base-uri 'none';
  form-action 'self'; frame-ancestors 'none'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
```

### 9.3 Production Requirements (Not Implemented)

- SSO/OIDC/SAML with verified identity and MFA.
- Server-side sessions with expiry, rotation, and revocation.
- Role-based authorisation for moderation.
- CSRF tokens for all state-changing requests.
- HTTPS only, `Secure` cookies, HSTS.
- Rate limiting per user and IP (for example, kudos creation and login attempts).
- Duplicate/spam detection and abuse reporting.
- Secrets in a managed store; no development secret in production.
- Centralised audit logs for moderation actions.
- Privacy impact assessment; retention and deletion rules.
- Dependency scanning, SAST, and security review.
- Database backups and encryption at rest.

---

## 10. Performance Considerations

| Concern | Design |
|---|---|
| Feed query | Indexed `(created_at DESC, id DESC)`; one JOIN query; `LIMIT`/`OFFSET`. |
| Pagination | `limit + 1` rows determines `hasMore` without a `COUNT(*)`; maximum page size 50. |
| N+1 queries | Avoided by joining both users in the feed query. |
| Write cost | One INSERT plus one SELECT of the created row; acceptable at demo scale. |
| SQLite concurrency | WAL mode; `busy_timeout` 5 s; one connection per request. |
| Static assets | Served by Flask in development; production should use a reverse proxy or CDN with cache headers. |
| Caching | No application-level cache in the demo. The feed is small and read-heavy; SQLite is fast enough. Production could add HTTP `ETag`/`Cache-Control` for the first page or a short-lived cache if volume grows. |
| Pagination trade-off | Offset pagination is simple for beginners but can skip or duplicate items when new rows arrive. The UI deduplicates by ID. A cursor based on `(created_at, id)` is the recommended production upgrade. |
| Client work | Small DOM, no framework, template cloning; no full-page reloads. |
| Performance target | First feed page under 500 ms locally with 1,000 kudos. |

---

## 11. Error Handling and Logging

### 11.1 Error Handling Strategy

- Validation errors are raised as a custom `ValidationError` carrying a field map and converted to `400 VALIDATION_ERROR`.
- Domain errors use explicit codes (`SELF_KUDOS`, `RECIPIENT_NOT_FOUND`, `USER_NOT_FOUND`, `UNAUTHENTICATED`).
- Flask HTTP errors on `/api/*` are converted to the JSON envelope; page routes return a small HTML error page.
- Unexpected exceptions are logged with the request ID and return `500 INTERNAL_ERROR` without stack traces or database details.
- Database writes occur inside a transaction; any failure rolls back, so partial rows are impossible.
- The client distinguishes field errors, session expiry, network errors, and server errors, and preserves the user's message where possible.

### 11.2 Error Codes

| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHENTICATED` | 401 | No valid demo session |
| `VALIDATION_ERROR` | 400 | Field-level validation failure |
| `INVALID_JSON` | 400 | Malformed request body |
| `SELF_KUDOS` | 400 | Recipient is the giver (proposed rule) |
| `RECIPIENT_NOT_FOUND` | 404 | Recipient missing or inactive |
| `USER_NOT_FOUND` | 404 | Demo user missing or inactive |
| `NOT_FOUND` | 404 | Unknown route |
| `METHOD_NOT_ALLOWED` | 405 | Wrong method |
| `PAYLOAD_TOO_LARGE` | 413 | Body over 16 KB |
| `INTERNAL_ERROR` | 500 | Unexpected failure |
| `RATE_LIMITED` | 429 | Production only, not implemented |
| `FORBIDDEN` | 403 | Production only, for moderation roles |

### 11.3 Logging

- Use Python's standard `logging` module; log to stdout.
- Each request gets a UUID (`uuid.uuid4()`), returned in `X-Request-Id` and included in error responses.
- Access log fields: timestamp, level, request ID, method, path, status, duration in ms, current user ID (if signed in).
- **Never log** message bodies, cookies, session contents, secrets, or full request bodies.
- Log 500 errors with a stack trace server-side only.
- Production should ship structured JSON logs to a central system with retention and alerting.

---

## 12. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | Ephemeral random value + warning | Signs the session cookie. Must be stable in a real deployment. |
| `KUDOS_DB_PATH` | `data/kudos.db` (project-relative) | SQLite file location. |
| `HOST` | `127.0.0.1` | Bind address; local-only by default. |
| `PORT` | `5000` | Local port. |
| `KUDOS_DEBUG` | `0` | Enables Flask debug mode; never enabled in production. |
| `ALLOW_DEMO_LOGIN` | `1` | Enables demo identity routes; set to `0` in production. |
| `SESSION_COOKIE_SECURE` | `0` | Set to `1` behind HTTPS. |

- Configuration is read from environment variables with safe defaults.
- `.env` auto-loading is **not** included, to avoid an extra dependency; the README documents `export` commands.
- `KUDOS_DEBUG=1` enables Flask's debugger and must never be used outside local development; the app logs a prominent warning when it is enabled.
- Tests inject configuration directly into `create_app(test_config)`, overriding the database path and secret.

---

## 13. Testing Strategy

### 13.1 Test Levels

| Level | Tool | Scope |
|---|---|---|
| Unit | pytest | Message trimming, length boundaries, control characters, integer parsing, pagination parsing. |
| Integration | pytest + Flask test client | Demo login, 401s, users, create kudos, validation responses, feed order/pagination, persistence. |
| Manual | Browser + checklist | Responsive layout, keyboard use, screen-reader announcements, XSS rendering, visual states. |

No end-to-end browser automation is included, to keep dependencies minimal. The manual checklist covers what unit tests cannot.

### 13.2 Test Fixtures

```python
@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "DATABASE": str(tmp_path / "test.db"),
        "ALLOW_DEMO_LOGIN": True,
    })
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
```

Each test gets a fresh temporary database. A helper signs in via `POST /api/demo/session`.

### 13.3 Planned Test Cases

**Validation (`test_validation.py`)**

- Trims leading/trailing whitespace.
- Accepts 1 and 500 characters; rejects 0 and 501.
- Rejects whitespace-only and non-string messages.
- Rejects NUL and control characters except `\n` and `\t`.
- Accepts emoji and non-ASCII text.
- Parses integer IDs; rejects strings, floats, and booleans.
- Parses `limit`/`offset` defaults, bounds, and invalid values.

**Authentication (`test_api_auth.py`)**

- Protected endpoints return 401 without a session.
- Demo login sets a session; `/api/me` returns the user.
- Unknown/inactive user returns 404 and creates no session.
- Switching user clears the previous identity.
- Demo endpoints return 404 when `ALLOW_DEMO_LOGIN` is false.
- Session survives requests via the test client cookie jar.

**Users (`test_api_users.py`)**

- Active users only; sorted by name; no email exposed.
- Inactive users excluded.

**Kudos creation (`test_api_kudos.py`)**

- Valid request returns 201 and inserts exactly one row.
- Giver comes from the session; a supplied `giverId` is ignored.
- Empty, whitespace-only, 501-character, and non-string messages are rejected.
- Self-kudos rejected.
- Unknown/inactive recipient rejected.
- Malformed JSON and wrong content type rejected.
- Leading/trailing whitespace trimmed in storage.
- XSS payload stored and returned as a literal string.
- Two sequential submissions create two rows (no accidental idempotency).
- Database rollback leaves no row on failure.

**Feed (`test_api_feed.py`)**

- Newest first; ID tiebreaker correct.
- First page returns 20 by default.
- `hasMore` and `nextOffset` correct at page boundaries.
- `limit` bounds and invalid values.
- Empty feed returns `items: []`, not an error.
- JOIN returns giver and recipient names.
- Duplicate-safe pagination behaviour is documented; client dedupe is manually checked.

**Persistence**

- Create kudos, dispose the app/connection, create a new app against the same file, and confirm the row is still returned.

### 13.4 Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
pytest tests/test_api_kudos.py -q
```

### 13.5 Manual QA Checklist

- [ ] First visit shows the identity picker; no feed data is visible.
- [ ] Choosing a user shows the dashboard; reload preserves identity.
- [ ] Switch user returns to the picker.
- [ ] Composer excludes the current user.
- [ ] Counter matches code-point length, including emoji.
- [ ] Empty, whitespace-only, and 501-character messages show errors.
- [ ] Double-clicking Submit creates one kudos.
- [ ] Success clears the form and puts the new item at the top.
- [ ] Feed shows giver, recipient, message, and readable time.
- [ ] "Load more" appends and eventually hides.
- [ ] Empty feed shows the empty state.
- [ ] Long messages and long names wrap at 320 px without horizontal scroll.
- [ ] Keyboard-only completion of the full flow.
- [ ] Focus is visible; errors are announced; success is announced.
- [ ] `<script>alert(1)</script>` is displayed literally.
- [ ] Restarting the server preserves kudos.
- [ ] Browser console has no errors.

---

## 14. Implementation Plan

No work starts until the specification is approved. Timing is deliberately expressed as ordering and dependencies, not calendar estimates.

### Phase 0 — Foundation

| ID | Task | Depends on | Done when |
|---|---|---|---|
| **T0.1** | Create project skeleton, `.gitignore`, `requirements.txt`, `requirements-dev.txt`, README placeholder. | — | Files exist; README documents the intended commands. |
| **T0.2** | Implement `schema.sql` and `db.py` (connection, teardown, init, seed, transaction). | T0.1 | A fresh database is created with both tables and indexes; seed is idempotent. |
| **T0.3** | Add 8 fictional seed users in `seed.sql`. | T0.2 | Re-running seed does not duplicate users. |
| **T0.4** | Create `create_app()` in `app.py`: config, page route, health endpoint, request IDs, security headers, logging. | T0.1 | `GET /` returns the shell; `GET /api/health` returns 200. |

### Phase 1 — Backend API

| ID | Task | Depends on | Done when |
|---|---|---|---|
| **T1.1** | Implement validation helpers and `ValidationError`. | T0.1 | Unit tests for message and parameter rules pass. |
| **T1.2** | Implement `login_required`, session helpers, and demo identity endpoints (`/api/demo/users`, `POST`/`DELETE /api/demo/session`). | T0.2, T0.3, T0.4 | Login, logout, 401, and disabled-demo behaviour match the API contract. |
| **T1.3** | Implement `GET /api/me` and `GET /api/users`. | T1.2 | Current user and active colleague list work; emails are not exposed. |
| **T1.4** | Implement `POST /api/kudos` with validation, transaction, and joined response. | T1.1, T1.2, T1.3 | Valid create returns 201; all rejection cases return the specified codes. |
| **T1.5** | Implement `GET /api/kudos` with validation, JOIN, ordering, and pagination. | T1.1, T1.2, T1.3 | Order, limits, offsets, `hasMore`, and `nextOffset` are correct. |
| **T1.6** | Add JSON error handlers for 400/401/404/405/413/500 and consistent envelopes. | T0.4, T1.1 | API errors always use the envelope; page errors remain HTML. |

### Phase 2 — Frontend

| ID | Task | Depends on | Done when |
|---|---|---|---|
| **T2.1** | Build `index.html`, CSS tokens, layout, and the kudos-card `<template>`. | T0.4 | Shell renders; layout is usable at 320 px and desktop. |
| **T2.2** | Implement `api.js` (fetch wrapper, error handling) and app bootstrap (`GET /api/me`). | T1.3, T2.1 | 401 leads to the picker; 200 leads to the dashboard. |
| **T2.3** | Implement identity picker and switch-user flow. | T1.2, T2.2 | Choose, persist on reload, and switch all work. |
| **T2.4** | Implement composer: colleague list excluding self, counter, submit, field errors, double-submit guard. | T1.3, T1.4, T2.3 | Full create flow works; errors are shown and announced. |
| **T2.5** | Implement feed: first page, cards, relative time, empty/error states, load more, dedupe. | T1.5, T2.3 | Feed and pagination match acceptance criteria. |
| **T2.6** | Add success toasts, session-expiry handling, loading states, and accessibility polish. | T2.4, T2.5 | Live regions, focus handling, and 401 transition verified. |
| **T2.7** | Responsive and visual polish; 44 px targets; 16 px inputs; long-text wrapping. | T2.6 | Manual checks at 320/768/1280 px pass. |

### Phase 3 — Verification and Documentation

| ID | Task | Depends on | Done when |
|---|---|---|---|
| **T3.1** | Write validation unit tests. | T1.1 | All planned unit cases pass. |
| **T3.2** | Write API integration tests. | T1.2–T1.6 | Auth, users, create, and feed tests pass against temporary databases. |
| **T3.3** | Run the manual QA checklist and fix defects. | T2.7, T3.2 | Every checklist item passes. |
| **T3.4** | Verify persistence across a real restart. | T1.4, T2.5 | A submitted kudos is visible after stopping and restarting the app. |
| **T3.5** | Complete README: setup, run, demo identity warning, tests, reset instructions. | T0.1, T3.3 | A new person can run the demo from the README alone. |
| **T3.6** | Review implementation against REQUIREMENTS.md and record deviations. | All | No unexplained deviations; spec or code updated as agreed. |

### Critical Path

```text
T0.1 → T0.2 → T0.3 → T1.2 → T1.3 → T1.4 → T2.4 → T2.6 → T2.7 → T3.3 → T3.6
```

### Sequencing Notes

- Backend endpoints exist before their frontend consumers, so the UI can be built against a stable contract.
- Tests for a module are written alongside or immediately after it; final verification is a separate gate.
- Moderation work from Task 2 Step 2 must be added to the specification and design **before** implementation begins, so the schema and endpoints are designed once rather than retrofitted mid-build.

---

## 15. Deployment and Operations

### 15.1 Local Demo Run

```bash
cd kudos-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

- The database is created at `data/kudos.db`.
- Seed users are inserted on first start.
- Stop with Ctrl+C.
- Reset the demo by deleting `data/kudos.db`, `data/kudos.db-wal`, and `data/kudos.db-shm`.
- The Flask development server is for local use only.

### 15.2 Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

### 15.3 Production Considerations (Not Part of the Demo)

- Use a production WSGI server (for example, Gunicorn) behind a TLS-terminating reverse proxy.
- Bind only to internal interfaces; enforce HTTPS and HSTS.
- Replace demo identity with SSO; disable demo routes.
- Move to a managed database if concurrency, availability, or multi-instance deployment requires it; otherwise keep SQLite with backups and WAL.
- Add structured logging, metrics, health/readiness checks, and alerts.
- Add rate limiting, CSRF tokens, abuse controls, and moderation audit logs.
- Automate backups and test restores.
- Run dependency and container scanning in CI.
- Complete privacy, security, and accessibility reviews.

### 15.4 Packaging

- The demo runs from a source checkout; no container is required.
- A Dockerfile is optional and out of scope for the initial deliverable.
- `.gitignore` excludes `.venv/`, `data/*.db*`, `__pycache__/`, and `.pytest_cache/`.

---

## 16. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Demo identity mistaken for real authentication | Medium | High | Visible demo banner; README warning; localhost binding; demo routes disabled by config in production. |
| Unapproved assumptions baked into schema (self-kudos, 500 chars) | Medium | Medium | Confirm A-07/A-08 before implementation; note that CHECK constraints are harder to change later. |
| XSS through message rendering | Low if rules followed | High | `textContent` only; code review; CSP; manual XSS test. |
| Offset pagination duplicates/skips under concurrent writes | Medium | Low | Client dedupe; documented trade-off; cursor pagination as production upgrade. |
| Python 3.9 is end-of-life | High over time | Medium | Demo only; production on Python 3.11+; pin versions. |
| SQLite single-writer bottleneck | Low at demo scale | Medium | WAL; low write volume; reassess for production multi-instance. |
| Scope creep (moderation, notifications, profiles) | High | Medium | Explicit out-of-scope list; Step 2 scope agreed before coding. |
| Seed data mistaken for real employees | Low | Medium | Fictional names/emails; README states they are fake. |
| Unicode length mismatch between JS and Python | Medium | Low | Count code points in both; remove `maxlength`; server authoritative. |
| Secret leakage | Low | High | No secrets in repo; environment configuration; managed store in production. |
| Timezone confusion | Medium | Low | Store UTC; parse with `Date`; show local time and absolute title. |
| Student environment lacks Flask | Certain initially | Low | Virtual environment and pinned `requirements.txt`; documented install step. |

---

## 17. Open Design Questions

These mirror REQUIREMENTS.md; only design-relevant ones are repeated.

| ID | Question | Current proposal |
|---|---|---|
| **OQ-01** | Moderation workflow, visibility fields, admin role, spam/duplicate handling. | Deliberately not designed in this draft. Add before approval (Task 2 Step 2). |
| **OQ-02** | Are self-kudos allowed? | No; enforced in app and schema. |
| **OQ-03** | Anonymous or private kudos? | No. |
| **OQ-04** | Can authors edit/delete their own kudos? | No. |
| **OQ-06** | Company-wide or team-scoped feed? | Company-wide. |
| **OQ-08** | Rate limits and duplicate detection? | None in the demo; production required. |
| **OQ-11** | Expected scale? | Low volume, single instance. |
| **OQ-12** | Is Python/Flask/SQLite approved? | Proposed; no code until approved. |
| **OQ-13** | Deployment target? | Local demo only for now. |

---

## 18. Review and Approval

This design is **not approved**. Before implementation:

- [ ] Confirm the stack and architecture (OQ-12).
- [ ] Confirm A-07/A-08 constraints before they are encoded in the schema.
- [ ] Confirm the demo identity mechanism and the demo/production boundary.
- [ ] Add moderation requirements and design (Task 2 Step 2): visibility, audit fields, admin authorisation, spam/duplicate handling.
- [ ] Consolidate the final, approved requirements and design into `SPECIFICATION.md`.
- [ ] Give explicit written approval.

Until approval, no code, dependency installation, database creation, Git initialisation, or remote repository will be produced.

---

## 19. Change Log

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-10-18 | AI development partner | Initial technical design for review. No implementation. |
