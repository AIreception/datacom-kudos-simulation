# Kudos System — Technical Design

- **Status:** APPROVED v0.2 — approved for implementation on 2026-10-18
- **Date:** 2026-10-18
- **Project:** Datacom Forage Task 2 — standalone Kudos demo
- **Related document:** [REQUIREMENTS.md](REQUIREMENTS.md)
- **Consolidated specification:** [SPECIFICATION.md](SPECIFICATION.md)
- **Supersedes:** v0.1 (frozen at [snapshots/v0.1/DESIGN.md](snapshots/v0.1/DESIGN.md))

> **Approved for implementation on 2026-10-18.** The project owner formally approved this technical design and REQUIREMENTS.md v0.2. The implementation follows this design; [SPECIFICATION.md](SPECIFICATION.md) consolidates the approved requirements and design. A full audit trail, reporting workflows, automated moderation, and notifications remain out of scope.

## What Changed in v0.2

- Added `users.role` (`employee` | `admin`) and one seeded fictional administrator.
- Added `kudos.is_visible` (`INTEGER NOT NULL DEFAULT 1`, constrained to 0/1).
- Added an administrator moderation view listing visible and hidden kudos.
- Added hide, restore, and permanent-delete endpoints, all admin-only.
- Added server-side role resolution from the session's user ID and the database.
- Added CSRF protection for every unsafe HTTP method, including demo login/logout.
- Added an employee-feed filter so hidden and deleted kudos never appear in employee API responses.
- Added moderation UI, a delete confirmation dialog, and role indicators in the demo picker.
- Explicitly documented that anyone can select the demo administrator; this is role demonstration, not secure authentication.

The frozen v0.1 snapshot is available in `snapshots/v0.1/` for diff review.

---

## 1. Design Goals and Constraints

| Goal | Consequence |
|---|---|
| Small and locally runnable | One Python web process and one SQLite file. No containers or external services. |
| Persistent storage | Data and moderation state live in `data/kudos.db` and survive restarts. |
| Minimal dependencies | Flask only at runtime; pytest only for development. No ORM, no frontend framework, no build step. |
| Beginner-readable | Plain SQL, small modules, request flow traceable from browser to database. |
| Secure by construction within demo limits | Server-side validation and authorization, parameterised SQL, safe DOM rendering, signed session cookie, CSRF tokens, security headers. |
| Correct moderation semantics | Hidden kudos are filtered at the database level; deletion is permanent; restored kudos keep their original timestamp. |
| Honest demo identity | A visible picker, an "Administrator" badge, and an explicit warning that identity is simulated. |
| Production-extensible | Clear seams for SSO, directory-synced roles, CSRF rotation, audit logging, and a different database. |

**Verified environment (2026-10-18):**

- Python **3.9.6** is installed at `/usr/bin/python3`.
- SQLite **3.54.0** is available both as a CLI and via Python's standard library.
- Node.js and npm are **not** installed.
- Flask is not installed yet; it will be installed into a virtual environment during implementation.
- The project owner accepted the Python/Flask/SQLite/vanilla JavaScript stack on 2026-10-18.

---

## 2. Stack and Rationale

### 2.1 Chosen Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.9+ | Already installed; readable for beginners. |
| Web framework | Flask 3.1.x | One small dependency; simple routing; built-in test client; no build step. |
| Database | SQLite via stdlib `sqlite3` | File-based persistence, real SQL schema, zero server setup, no extra dependency. |
| DB access | Plain SQL + `sqlite3.Row` | Transparent; teaches what an ORM would hide. |
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
| Flask-WTF for CSRF | Adds a dependency and conventions beyond the small token mechanism needed here. |

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
│  index.html + styles.css + app.js/api.js/moderation.js      │
│  - identity picker (with administrator badge)               │
│  - kudos composer                                           │
│  - employee feed + "Load more"                              │
│  - administrator moderation panel + delete dialog           │
└──────────────────────────┬──────────────────────────────────┘
                           │ same-origin HTTP, JSON + signed cookie
                           │ X-CSRF-Token on POST/DELETE
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Flask application (single process)                          │
│                                                             │
│  app.py      app factory, config, page route, error handlers│
│  auth.py     session user, login_required, admin_required,  │
│              CSRF issue/validate/rotate                     │
│  api.py      /api blueprint: CSRF, demo identity, users,    │
│              kudos, admin moderation                        │
│  validation.py  input parsing and product rules             │
│  db.py       SQLite connection, schema init, seed data      │
│  schema.sql  tables, constraints, indexes                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ parameterised SQL
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ data/kudos.db  (SQLite file, WAL mode, foreign keys ON)     │
│  users(role)          kudos(is_visible)                     │
└─────────────────────────────────────────────────────────────┘
```

There is one origin and no CORS. Flask serves both the HTML shell and the JSON API. The browser never talks to SQLite directly.

### 3.2 Key Flows

**First visit / CSRF bootstrap**

1. Browser loads `GET /` → HTML shell.
2. `app.js` calls `GET /api/csrf` → the server ensures a per-session token and returns `{"csrfToken": "..."}`. The client stores it in memory.
3. `app.js` calls `GET /api/me` → `401`.
4. `app.js` calls `GET /api/demo/users` and renders the identity picker, marking the administrator.
5. The user chooses a user → `POST /api/demo/session` with `X-CSRF-Token`.
6. The server validates CSRF, validates the user, clears the old session, sets `user_id`, rotates the CSRF token, and returns the user plus the new token.
7. The client updates its token and loads the colleague list and first visible feed page. If the user is an administrator, it also loads the moderation list.

**Submitting kudos**

1. User selects a recipient and writes a message.
2. `POST /api/kudos` with JSON `{ "recipientId": 2, "message": "..." }` and `X-CSRF-Token`.
3. The global CSRF guard validates the token.
4. `login_required` resolves the giver from the signed session cookie and the database.
5. `validation.py` validates and trims the input; `db.py` inserts one row in a transaction.
6. The server returns `201` with the created kudos (joined with names).
7. The UI clears the composer, shows a success message, and refreshes the first employee feed page.

**Moderation: hide / restore / delete**

1. The administrator opens the moderation panel. `GET /api/admin/kudos?visibility=all` returns visible and hidden kudos.
2. **Hide:** `POST /api/admin/kudos/{id}/hide` with CSRF → sets `is_visible = 0`; returns the updated item. The UI removes it from the employee feed and refreshes the admin list.
3. **Restore:** `POST /api/admin/kudos/{id}/restore` with CSRF → sets `is_visible = 1`; returns the updated item. The UI refreshes the employee feed, where it reappears at its original chronological position.
4. **Delete:** the UI opens a confirmation `<dialog>`; only after confirmation does it send `DELETE /api/admin/kudos/{id}` with CSRF. The row is removed permanently. The UI removes it from the admin list and refreshes the employee feed.
5. Every moderation route re-checks `role = 'admin'` from the database; a client-supplied role is ignored.

**Employee feed read**

1. `GET /api/kudos?limit=20&offset=0`.
2. `login_required` resolves the current user.
3. The query filters `is_visible = 1`, orders by `created_at DESC, id DESC`, and fetches `limit + 1` rows.
4. The extra row determines `hasMore` from the visible set only.
5. Hidden rows never enter the result set; deleted rows no longer exist.

### 3.3 Request Lifecycle

```text
Request
  → before_request: assign request_id, start timer
  → API blueprint before_request:
       if method is POST/PUT/PATCH/DELETE:
           validate X-CSRF-Token against the session token
           on failure: 403 CSRF_FAILED, no state change
  → route decorators:
       login_required  → 401 if no valid session
       admin_required  → 403 FORBIDDEN if role is not admin
  → route handler
      → validation.py
      → db.py (connection from flask.g)
  → after_request: security headers, X-Request-Id, access log
  → teardown_appcontext: close DB connection
```

**Error precedence for unsafe requests:** CSRF is checked before authentication. A missing or invalid token returns `403 CSRF_FAILED` even if there is no session. With a valid token, a protected route without a session returns `401 UNAUTHENTICATED`, and an employee calling an admin route returns `403 FORBIDDEN`.

---

## 4. Application Structure

```text
kudos-app/
├── app.py                  # create_app(), config, page route, CLI entry point
├── auth.py                 # session user loading, guards, CSRF token helpers
├── api.py                  # Flask blueprint for /api routes (demo, users, kudos, admin)
├── db.py                   # get_db(), close_db(), init_db(), seed_db(), transaction()
├── validation.py           # ValidationError and input/parameter validators
├── schema.sql              # tables, constraints, indexes
├── seed.sql                # 8 employees + 1 administrator, fictional
├── requirements.txt        # Flask
├── requirements-dev.txt    # -r requirements.txt + pytest
├── README.md               # setup, run, demo identity caveat, test commands
├── .gitignore              # .venv/, data/, __pycache__/, .pytest_cache/
├── templates/
│   └── index.html          # shell, kudos template, moderation template, delete dialog
├── static/
│   ├── css/
│   │   └── styles.css      # tokens, layout, components, responsive rules
│   └── js/
│       ├── api.js          # fetch wrapper, CSRF header, ApiError, endpoints
│       ├── app.js          # state, bootstrap, composer, feed, identity picker
│       └── moderation.js   # admin panel rendering and actions
├── data/                   # created at runtime; gitignored
│   └── kudos.db            # SQLite database
└── tests/
    ├── conftest.py         # app/client fixtures, CSRF/login helpers
    ├── test_validation.py  # product rules and parameter parsing
    ├── test_api_auth.py    # session, CSRF, login rotation, 401s
    ├── test_api_users.py   # colleague list and role privacy
    ├── test_api_kudos.py   # create + validation + authorisation
    ├── test_api_feed.py    # visible-only order, pagination, hasMore
    └── test_api_moderation.py  # admin list, hide/restore/delete, 403s
```

**Why this layout:** each file has one responsibility and can be read in one sitting. `auth.py` keeps session, role, and CSRF logic out of route handlers. `moderation.js` keeps the administrator UI separate from the employee feed. There is no package directory, which keeps imports and the run command simple.

---

## 5. Data Design

### 5.1 Design Principles

- Normalised: giver and recipient reference a single `users` table.
- IDs are integer primary keys.
- Timestamps are ISO 8601 UTC strings (`YYYY-MM-DDTHH:MM:SS.sssZ`), which sort correctly and are readable.
- Foreign keys are enforced.
- Messages are stored as plain text, exactly as submitted after trimming; rendering is responsible for safety.
- Visibility is stored as an integer and filtered in SQL, not only in the UI.
- Roles are stored on the user and read on every request; they are never stored in the session.
- No moderation audit fields are included, by explicit scope decision.

### 5.2 Entity Relationship

```text
users 1 ─────< kudos (as giver_id)
users 1 ─────< kudos (as recipient_id)

users
  id            PK
  name
  email         UNIQUE
  department
  role          'employee' | 'admin'
  is_active     0 | 1
  created_at

kudos
  id            PK
  giver_id      FK → users.id
  recipient_id  FK → users.id
  message       TEXT
  is_visible    0 | 1 (NOT NULL, default 1)
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
    role        TEXT    NOT NULL DEFAULT 'employee'
                CHECK (role IN ('employee', 'admin')),
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS kudos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    giver_id      INTEGER NOT NULL REFERENCES users(id),
    recipient_id  INTEGER NOT NULL REFERENCES users(id),
    message       TEXT    NOT NULL
                  CHECK (length(trim(message)) BETWEEN 1 AND 500),
    is_visible    INTEGER NOT NULL DEFAULT 1 CHECK (is_visible IN (0, 1)),
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (giver_id <> recipient_id)
);

-- Full ordering index: employee feed and administrator list.
CREATE INDEX IF NOT EXISTS idx_kudos_created_at
    ON kudos (created_at DESC, id DESC);

-- Partial index: employee feed reads only visible kudos.
CREATE INDEX IF NOT EXISTS idx_kudos_visible_created_at
    ON kudos (created_at DESC, id DESC)
    WHERE is_visible = 1;
```

### 5.4 Field Rationale

| Field | Rationale |
|---|---|
| `users.id` | Stable internal identifier. Not an email, so a person's email can change. |
| `users.email` | Unique directory key for seed data and future SSO mapping. Not exposed by the colleague API. |
| `users.department` | Helps users distinguish colleagues with similar names and is useful seed context. |
| `users.role` | `employee` or `admin`; the sole source of moderation authorization. Defaults to `employee`. |
| `users.is_active` | Allows leavers or hidden demo users without deleting historical kudos. |
| `kudos.giver_id` | Who gave recognition. Always derived from the session. |
| `kudos.recipient_id` | Who received it. |
| `kudos.message` | Plain text, 1–500 code points after trimming. |
| `kudos.is_visible` | `1` = visible; `0` = hidden by an administrator. NOT NULL, default `1`. |
| `kudos.created_at` | UTC timestamp used for ordering and display. Hide/restore never changes it. |
| `idx_kudos_created_at` | Serves administrator ordering across all rows. |
| `idx_kudos_visible_created_at` | Serves the employee feed's visible-only `ORDER BY … LIMIT/OFFSET`. |

### 5.5 Constraints and Assumptions

- `role` is constrained to exactly `'employee'` or `'admin'`. There is no third role in this exercise.
- `is_visible` is `INTEGER NOT NULL DEFAULT 1` with `CHECK (is_visible IN (0, 1))`. The API exposes it as a JSON boolean only in administrator responses.
- `CHECK (giver_id <> recipient_id)` encodes accepted rule A-07.
- The message `CHECK` encodes accepted rule A-08. SQLite's `length()` on `TEXT` counts Unicode code points, matching Python's `len()`.
- The app trims whitespace before insert. SQLite's `trim()` only removes ASCII spaces, so the application remains authoritative for whitespace-only rejection.
- Foreign keys prevent orphaned kudos but do not define delete behaviour. Users should be deactivated rather than deleted. A production delete policy is an open, non-blocking question.
- There is no `moderated_by`, `moderated_at`, or `reason_for_moderation` column. This is intentional: a full moderation audit system is out of scope. Application logs record the actor ID, kudos ID, and action for debugging only; they are not a durable audit trail.
- SQLite cannot easily drop a `CHECK` constraint; changing A-07/A-08 after data exists may require a table rebuild. These rules are accepted for this exercise.

### 5.6 Seed Data (`seed.sql`)

Nine fictional employees: eight employees and one administrator. Inserted idempotently with `INSERT OR IGNORE` on the unique email.

| Name | Department | Role | Email |
|---|---|---|---|
| Alice Ng | Engineering | employee | alice.ng@example.internal |
| Ben Okafor | Product | employee | ben.okafor@example.internal |
| Carla Mendes | Design | employee | carla.mendes@example.internal |
| Daniel Kim | Engineering | employee | daniel.kim@example.internal |
| Elif Yilmaz | People & Culture | employee | elif.yilmaz@example.internal |
| Farhan Ali | Finance | employee | farhan.ali@example.internal |
| Grace Chen | Customer Success | employee | grace.chen@example.internal |
| Hemi Walker | Security | employee | hemi.walker@example.internal |
| **Morgan Reed** | **People & Culture** | **admin** | **morgan.reed@example.internal** |

All data is fictional. No real Datacom employee data, names, or email addresses are used.

The administrator is also an employee and may give kudos. The identity picker marks Morgan Reed as an administrator. Anyone using the demo can select this account; this is intentional role demonstration, not authentication.

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

- **Demo:** `schema.sql` uses `CREATE TABLE IF NOT EXISTS`, and seed data uses `INSERT OR IGNORE`. There is no migration framework. The demo database is disposable.
- **Upgrading a v0.1 database in place (optional):**

```sql
ALTER TABLE users
    ADD COLUMN role TEXT NOT NULL DEFAULT 'employee'
    CHECK (role IN ('employee', 'admin'));

ALTER TABLE kudos
    ADD COLUMN is_visible INTEGER NOT NULL DEFAULT 1
    CHECK (is_visible IN (0, 1));

INSERT OR IGNORE INTO users (name, email, department, role)
VALUES ('Morgan Reed', 'morgan.reed@example.internal', 'People & Culture', 'admin');
```

- **Recommended for the demo:** delete `data/kudos.db*` and let the v0.2 schema and seed recreate it. No user data needs preserving.
- **Production:** numbered, reviewed migrations (for example, Alembic if the team adopts SQLAlchemy, or plain ordered `.sql` files with `PRAGMA user_version`) and backups before migration.

### 5.9 Expected Scale

The demo targets tens of users and low thousands of kudos. SQLite with WAL and one indexed feed query is comfortably sufficient. SQLite allows one writer at a time; that is acceptable for a local demo and a low-write internal tool. Production should reassess if concurrency or multi-instance deployment is required.

---

## 6. Demo Identity, Roles, and Production Path

### 6.1 Demo Identity (Approved for the Demo)

**Mechanism:** Flask's built-in signed session cookie.

1. The page loads and calls `GET /api/csrf` to obtain a CSRF token.
2. If unauthenticated, the UI shows `GET /api/demo/users` — all active seeded users, exposing `id`, `name`, `department`, and `role`.
3. Choosing a user calls `POST /api/demo/session` with `{ "userId": 1 }` and `X-CSRF-Token`.
4. The server verifies CSRF, the user exists, and the user is active. It calls `session.clear()`, sets `session.permanent = True`, stores `session["user_id"]`, generates a new CSRF token, and returns it.
5. Flask signs the cookie with `SECRET_KEY`. The cookie is `HttpOnly` and `SameSite=Lax`.
6. Every protected route loads the user row from the database and reads `role` from it. The session stores only `user_id` and the CSRF token.

**Why the role is not in the session:** storing it would risk stale authorization. Reading it from the database on each request means demotions and promotions take effect immediately, and a forged client value has no effect.

**What this demonstrates:** the production-shaped pattern where the server, not the request body, determines the actor and permissions.

**What this does not provide:**

- Proof of identity. Anyone who can reach the app can choose any seeded user, including the administrator.
- Password, MFA, account recovery, or session revocation.
- Protection against someone with the signing secret forging a cookie.

**Mitigations and honesty requirements:**

- The UI displays a visible banner: "Demo mode — identity is simulated."
- The administrator is clearly marked in the picker.
- The README and spec state that the demo is local-only and must not be deployed.
- The app binds to `127.0.0.1` by default.
- Demo routes are controlled by `ALLOW_DEMO_LOGIN`, which defaults to `True` for the demo and must be `False` in production (routes then return 404).
- If `SECRET_KEY` is not set, the app generates an ephemeral secret and logs a warning; sessions and CSRF tokens reset on restart.
- `SESSION_COOKIE_SECURE` defaults to `False` for local HTTP and must be `True` behind HTTPS.

### 6.2 CSRF Token Lifecycle (Demo)

| Step | Behaviour |
|---|---|
| **Bootstrap** | `GET /api/csrf` ensures `session["csrf_token"]` exists and returns it. It is safe and requires no login. |
| **Usage** | Every `POST`/`PUT`/`PATCH`/`DELETE` sends `X-CSRF-Token`. |
| **Validation** | The API blueprint checks the header against the session token with `hmac.compare_digest`. Failure → `403 CSRF_FAILED`, no state change. |
| **Login rotation** | `POST /api/demo/session` validates the old token, clears the session, sets `user_id`, and issues a new token returned in the response. The client updates its stored token. |
| **Logout** | `DELETE /api/demo/session` validates the token and clears the session. The client calls `GET /api/csrf` before the next sign-in. |
| **Expiry / failure** | The client fetches a new token, shows a "security token refreshed, please try again" message, and does not automatically repeat the request. |
| **Cookie** | `SameSite=Lax`, `HttpOnly`; `Secure` in production. |

**Why this is adequate for the demo:** a cross-site attacker cannot read the token, cannot set the custom header without a CORS preflight that the app does not allow, and `SameSite=Lax` prevents the session cookie from accompanying cross-site POSTs. The token is tied to the signed session.

**Production improvements:** rotate tokens on every privilege change, use server-side sessions, enforce Origin/`Sec-Fetch-Site` checks, add CSRF tokens to any future form-encoded endpoints, and conduct a security review.

### 6.3 Production Identity and Roles (Not Implemented)

Proposed production path:

1. Integrate with Datacom's SSO using OIDC (authorization code + PKCE) or SAML.
2. Map the verified token's stable subject and email to the `users` table; sync names and departments from the directory.
3. Use a server-side session (or short-lived signed token) with secure, HttpOnly, `SameSite=Lax` cookies over HTTPS.
4. Derive roles (employee, administrator) from directory groups; never trust a client-supplied role.
5. Remove or disable the demo endpoints and the demo picker.
6. Enforce CSRF tokens on all state-changing requests and rotate them on authentication changes.
7. Add rate limiting, audit logging, and separation of moderation duties.

This path preserves the API contract: handlers still ask the server for the current user and role. Only the identity and role source changes.

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
- Unknown JSON properties are ignored. A client-supplied `giverId`, `role`, or `isAdmin` is ignored for security.
- All protected endpoints require a valid demo session.
- **CSRF:** every `POST`, `PUT`, `PATCH`, and `DELETE` requires `X-CSRF-Token`. GET endpoints are read-only.
- **Error precedence:** CSRF failure (403) is evaluated before authentication (401) and authorization (403) for unsafe methods.

### 7.2 Endpoint Summary

| Method | Path | Auth | CSRF | Purpose |
|---|---|---|---|---|
| GET | `/` | No | No | HTML application shell |
| GET | `/api/health` | No | No | Liveness check |
| GET | `/api/csrf` | No | No | Obtain/refresh a CSRF token |
| GET | `/api/demo/users` | No (demo only) | No | List users for the identity picker, including roles |
| POST | `/api/demo/session` | No (demo only) | Yes | Choose a demo identity; rotates the CSRF token |
| DELETE | `/api/demo/session` | No | Yes | Clear the demo session |
| GET | `/api/me` | Yes | No | Current demo user, including role |
| GET | `/api/users` | Yes | No | Active colleague list (no roles) |
| GET | `/api/kudos` | Yes | No | Paginated **visible-only** employee feed |
| POST | `/api/kudos` | Yes | Yes | Create kudos |
| GET | `/api/admin/kudos` | Admin | No | Paginated list of visible and hidden kudos |
| POST | `/api/admin/kudos/{id}/hide` | Admin | Yes | Hide a kudos (soft delete) |
| POST | `/api/admin/kudos/{id}/restore` | Admin | Yes | Restore a hidden kudos |
| DELETE | `/api/admin/kudos/{id}` | Admin | Yes | Permanently delete a kudos |

There is no GET route that creates, hides, restores, or deletes kudos.

### 7.3 Endpoint Details

#### `GET /api/health`

- **Response:** `200 {"status":"ok"}`.
- May optionally execute `SELECT 1` against the database; no detail is exposed.

#### `GET /api/csrf`

- **Purpose:** Ensure the session has a CSRF token and return it. Safe to call before sign-in.
- **Response:** `200`

```json
{"csrfToken": "3xJ...opaque..."}
```

- Creates an anonymous session cookie if none exists.
- No auth required.

#### `GET /api/demo/users` (Demo Only)

- **Purpose:** Populate the identity picker before a session exists.
- **Response:** `200`

```json
{
  "users": [
    {"id": 1, "name": "Alice Ng", "department": "Engineering", "role": "employee"},
    {"id": 9, "name": "Morgan Reed", "department": "People & Culture", "role": "admin"}
  ]
}
```

- Active users only, sorted by name.
- No emails or timestamps.
- Returns `404` when `ALLOW_DEMO_LOGIN` is false.

#### `POST /api/demo/session` (Demo Only)

- **Headers:** `X-CSRF-Token`.
- **Request:**

```json
{"userId": 1}
```

- **Behaviour:** validates CSRF and the user; clears the old session; sets `user_id`; issues a new CSRF token; marks the session permanent.
- **Success:** `200`

```json
{
  "user": {
    "id": 1,
    "name": "Alice Ng",
    "department": "Engineering",
    "role": "employee"
  },
  "csrfToken": "new-opaque-token"
}
```

- **Errors:** `400 VALIDATION_ERROR`, `403 CSRF_FAILED`, `404 USER_NOT_FOUND` (unknown or inactive).
- Returns `404` when demo login is disabled.
- The previous CSRF token is invalid after a successful login.

#### `DELETE /api/demo/session`

- **Headers:** `X-CSRF-Token`.
- Clears the session, including the CSRF token.
- **Response:** `204 No Content` (idempotent; succeeds even with no user session, provided CSRF is valid).
- The client calls `GET /api/csrf` before the next sign-in.

#### `GET /api/me`

- **Success:** `200`

```json
{
  "user": {
    "id": 9,
    "name": "Morgan Reed",
    "department": "People & Culture",
    "role": "admin"
  }
}
```

- **Failure:** `401 UNAUTHENTICATED`.
- The role comes from the current database row, not from the session or client.

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

- No email addresses or roles are returned. Role information is not needed for selecting a recipient and should not leak.

#### `GET /api/kudos` (Employee Feed)

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

- **Always** filters `is_visible = 1`.
- Ordering: `created_at DESC, id DESC`.
- The server queries `limit + 1` rows to compute `hasMore` without `COUNT(*)`.
- `nextOffset` is `offset + len(items)` when `hasMore`, otherwise `null`.
- Hidden or deleted kudos never appear in `items` or affect pagination.
- **Errors:** `400 VALIDATION_ERROR` with `fields.limit` or `fields.offset`; `401 UNAUTHENTICATED`.

#### `POST /api/kudos`

- **Headers:** `X-CSRF-Token`.
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
| 400 | `SELF_KUDOS` | Recipient equals session user |
| 401 | `UNAUTHENTICATED` | No valid session (with a valid CSRF token) |
| 403 | `CSRF_FAILED` | Missing/invalid CSRF token |
| 404 | `RECIPIENT_NOT_FOUND` | Recipient missing or inactive |
| 413 | `PAYLOAD_TOO_LARGE` | Body exceeds 16 KB |
| 500 | `INTERNAL_ERROR` | Unexpected failure; log with request ID |

- The server ignores any `giverId`, `createdAt`, `id`, `role`, or `isAdmin` sent by the client.

#### `GET /api/admin/kudos`

- **Auth:** administrator only.
- **Query parameters:**

| Name | Type | Default | Rules |
|---|---|---|---|
| `limit` | integer | 20 | 1–50 |
| `offset` | integer | 0 | ≥ 0 |
| `visibility` | string | `all` | `all`, `visible`, or `hidden` |

- **Response:** `200`

```json
{
  "items": [
    {
      "id": 12,
      "message": "Thank you for staying late to help with the release!",
      "createdAt": "2026-10-18T09:12:34.567Z",
      "isVisible": true,
      "giver": {"id": 1, "name": "Alice Ng"},
      "recipient": {"id": 2, "name": "Ben Okafor"}
    },
    {
      "id": 11,
      "message": "...",
      "createdAt": "2026-10-18T08:00:00.000Z",
      "isVisible": false,
      "giver": {"id": 3, "name": "Carla Mendes"},
      "recipient": {"id": 4, "name": "Daniel Kim"}
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "hasMore": false,
    "nextOffset": null,
    "visibility": "all"
  }
}
```

- Includes hidden rows; deleted rows do not exist.
- Ordering: `created_at DESC, id DESC`.
- `isVisible` is a JSON boolean derived from the integer column.
- **Errors:** `400 VALIDATION_ERROR` with `fields.limit`, `fields.offset`, or `fields.visibility`; `401 UNAUTHENTICATED`; `403 FORBIDDEN` for employees.

#### `POST /api/admin/kudos/{id}/hide`

- **Auth:** administrator only.
- **Headers:** `X-CSRF-Token`.
- **Behaviour:** set `is_visible = 0`. Idempotent; `created_at` is unchanged.
- **Success:** `200`

```json
{"kudos": {"id": 12, "isVisible": false, "..." : "..."}}
```

- **Errors:** `400 VALIDATION_ERROR` (invalid ID), `401 UNAUTHENTICATED`, `403 FORBIDDEN`, `403 CSRF_FAILED`, `404 KUDOS_NOT_FOUND`.
- `GET` on this path returns `405 METHOD_NOT_ALLOWED`.

#### `POST /api/admin/kudos/{id}/restore`

- **Auth:** administrator only.
- **Headers:** `X-CSRF-Token`.
- **Behaviour:** set `is_visible = 1`. Idempotent; `created_at` is unchanged, so the kudos returns to its original chronological position.
- **Success:** `200`

```json
{"kudos": {"id": 12, "isVisible": true, "..." : "..."}}
```

- **Errors:** same as hide.
- `GET` on this path returns `405 METHOD_NOT_ALLOWED`.

#### `DELETE /api/admin/kudos/{id}`

- **Auth:** administrator only.
- **Headers:** `X-CSRF-Token`.
- **Behaviour:** permanently remove the row. The UI must have shown a confirmation dialog before sending this request. Deletion is irreversible.
- **Success:** `204 No Content`.
- **Errors:** `400 VALIDATION_ERROR` (invalid ID), `401 UNAUTHENTICATED`, `403 FORBIDDEN`, `403 CSRF_FAILED`, `404 KUDOS_NOT_FOUND`.
- `GET` on this path returns `405 METHOD_NOT_ALLOWED`.

### 7.4 Queries

**Employee feed — visible only:**

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
WHERE k.is_visible = 1
ORDER BY k.created_at DESC, k.id DESC
LIMIT ? OFFSET ?;
```

**Administrator list — all or filtered by visibility:**

```sql
SELECT
    k.id,
    k.message,
    k.created_at,
    k.is_visible,
    g.id   AS giver_id,
    g.name AS giver_name,
    r.id   AS recipient_id,
    r.name AS recipient_name
FROM kudos AS k
JOIN users AS g ON g.id = k.giver_id
JOIN users AS r ON r.id = k.recipient_id
WHERE (:visibility = 'all'
       OR (:visibility = 'visible' AND k.is_visible = 1)
       OR (:visibility = 'hidden'  AND k.is_visible = 0))
ORDER BY k.created_at DESC, k.id DESC
LIMIT :limit OFFSET :offset;
```

**Hide / restore:**

```sql
UPDATE kudos SET is_visible = ? WHERE id = ?;
```

- Check `cursor.rowcount`; `0` means the kudos does not exist → `404 KUDOS_NOT_FOUND`.
- An existing row is updated even if already in the requested state; the action is idempotent.

**Permanent delete:**

```sql
DELETE FROM kudos WHERE id = ?;
```

- Check `cursor.rowcount`; `0` → `404 KUDOS_NOT_FOUND`.

### 7.5 Status Codes

| Code | Meaning in this API |
|---|---|
| 200 | Successful read, demo login, hide, or restore |
| 201 | Kudos created |
| 204 | Session cleared or kudos permanently deleted |
| 400 | Malformed JSON, invalid parameters, validation failure, self-kudos |
| 401 | No valid session |
| 403 | CSRF failure, or authenticated employee attempting moderation |
| 404 | Unknown route/user/recipient/kudos; demo routes disabled |
| 405 | Wrong HTTP method (including GET on a state-changing route) |
| 413 | Request body too large |
| 500 | Unexpected server error |

### 7.6 Error Codes

| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHENTICATED` | 401 | No valid demo session |
| `VALIDATION_ERROR` | 400 | Field-level validation failure |
| `INVALID_JSON` | 400 | Malformed request body |
| `SELF_KUDOS` | 400 | Recipient is the giver |
| `CSRF_FAILED` | 403 | Missing, empty, or invalid CSRF token |
| `FORBIDDEN` | 403 | Authenticated user lacks the admin role |
| `RECIPIENT_NOT_FOUND` | 404 | Recipient missing or inactive |
| `USER_NOT_FOUND` | 404 | Demo user missing or inactive |
| `KUDOS_NOT_FOUND` | 404 | Kudos missing or already deleted |
| `NOT_FOUND` | 404 | Unknown route |
| `METHOD_NOT_ALLOWED` | 405 | Wrong method |
| `PAYLOAD_TOO_LARGE` | 413 | Body over 16 KB |
| `INTERNAL_ERROR` | 500 | Unexpected failure |
| `RATE_LIMITED` | 429 | Production only, not implemented |

---

## 8. Frontend Design

### 8.1 Approach

A single server-rendered HTML shell with a small vanilla JavaScript application. No framework, router, state library, or build step. ES modules are loaded with `<script type="module" src="/static/js/app.js">`. `moderation.js` is imported by `app.js`.

### 8.2 Page Structure

```text
<body>
  <header class="app-header">
    <h1>Kudos</h1>
    <div id="user-menu" hidden>
      <span>Signed in as <strong id="current-user-name"></strong></span>
      <span id="current-user-role" class="badge" hidden>Administrator</span>
      <span class="demo-badge">Demo mode — identity is simulated</span>
      <button id="switch-user">Switch user</button>
    </div>
  </header>

  <main>
    <section id="identity-picker" hidden aria-labelledby="identity-title">
      <h2 id="identity-title">Choose a demo user</h2>
      <p>This is not a real login. Anyone using the demo can select the administrator.</p>
      <ul id="identity-list"></ul>
    </section>

    <div id="app-content" hidden>
      <section id="moderation-panel" aria-labelledby="moderation-title" hidden>
        <h2 id="moderation-title">Moderation</h2>
        <p>Only administrators can see hidden kudos.</p>
        <label for="visibility-filter">Show</label>
        <select id="visibility-filter">
          <option value="all">All</option>
          <option value="visible">Visible</option>
          <option value="hidden">Hidden</option>
        </select>
        <p id="moderation-status" role="status" aria-live="polite"></p>
        <ol id="moderation-list"></ol>
        <p id="moderation-empty" hidden>No kudos match this filter.</p>
        <button id="moderation-load-more" type="button" hidden>Load more</button>
      </section>

      <section aria-labelledby="composer-title">
        <h2 id="composer-title">Give kudos</h2>
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
        <h2 id="feed-title">Recent kudos</h2>
        <p id="feed-status" role="status" aria-live="polite"></p>
        <ol id="feed-list"></ol>
        <p id="feed-empty" hidden>No kudos yet. Be the first to recognise a colleague.</p>
        <button id="load-more" type="button" hidden>Load more</button>
      </section>
    </div>
  </main>

  <div id="toast-region" aria-live="polite" aria-atomic="true"></div>

  <template id="kudos-card-template">
    <li class="kudos-card">
      <p class="kudos-card__meta">
        <span class="kudos-card__giver"></span>
        <span aria-hidden="true">→</span>
        <span class="visually-hidden">gave kudos to</span>
        <span class="kudos-card__recipient"></span>
      </p>
      <p class="kudos-card__message"></p>
      <time class="kudos-card__time"></time>
    </li>
  </template>

  <template id="moderation-card-template">
    <li class="moderation-card">
      <p class="moderation-card__meta">
        <span class="moderation-card__giver"></span>
        <span aria-hidden="true">→</span>
        <span class="visually-hidden">gave kudos to</span>
        <span class="moderation-card__recipient"></span>
        <span class="badge moderation-card__visibility"></span>
      </p>
      <p class="moderation-card__message"></p>
      <time class="moderation-card__time"></time>
      <div class="moderation-card__actions">
        <button type="button" class="hide-kudos">Hide</button>
        <button type="button" class="restore-kudos" hidden>Restore</button>
        <button type="button" class="delete-kudos">Delete</button>
      </div>
    </li>
  </template>

  <dialog id="delete-dialog" aria-labelledby="delete-title">
    <h2 id="delete-title">Delete this kudos permanently?</h2>
    <p id="delete-excerpt"></p>
    <p>This cannot be undone.</p>
    <div class="dialog-actions">
      <button type="button" id="delete-cancel">Cancel</button>
      <button type="button" id="delete-confirm">Delete permanently</button>
    </div>
  </dialog>
</body>
```

The exact markup may change during implementation, but these behaviours and accessible relationships are required.

### 8.3 Component Responsibilities

| Component | Responsibility |
|---|---|
| **App shell** | Header, main region, identity picker, moderation panel, composer, feed, toast region. |
| **Identity picker** | Fetches demo users, marks the administrator, presents an accessible button list, signs in, shows errors. |
| **User menu** | Shows current user, role badge for admins, and the demo-mode warning; clears the session on "Switch user". |
| **Composer** | Loads colleagues, excludes self, enforces the counter, submits with CSRF, reports field errors, prevents double submission. |
| **Employee feed** | Loads visible kudos, renders cards, appends subsequent pages, deduplicates by ID, shows empty/error states. |
| **Moderation panel** | Admin-only. Lists visible and hidden kudos, filters by visibility, paginates, and exposes Hide/Restore/Delete. |
| **Delete dialog** | Modal confirmation with the kudos excerpt; cancel sends no request; confirm sends DELETE. |
| **Kudos card / moderation card** | Clone templates and fill text nodes; render messages with `textContent`. |
| **Toast/status** | Announces success and non-field errors with `aria-live`. |

### 8.4 Client State

```js
const state = {
  csrfToken: null,          // per-session token from /api/csrf or login response
  me: null,                 // current demo user, including role
  isAdmin: false,           // derived from me.role === "admin" for UI only
  users: [],                // active colleagues
  kudos: [],                // visible feed items, newest first
  offset: 0,                // server offset for the next visible page
  hasMore: false,
  loadingFeed: false,
  submitting: false,
  moderation: {
    items: [],              // visible + hidden items
    offset: 0,
    hasMore: false,
    visibility: "all",
    loading: false,
  },
  pendingDeleteId: null,
};
```

State is in memory only. No `localStorage`, because the server session is the source of truth and sensitive data should not be persisted by the client.

### 8.5 Bootstrap and CSRF Flow

1. `GET /api/csrf` → store `csrfToken`.
2. `GET /api/me`.
3. If 401: fetch `/api/demo/users`, render the picker. Keep the app content hidden.
4. If 200: show the header and app content; load `/api/users` and `/api/kudos?limit=20&offset=0`; if `me.role === "admin"`, also load the moderation panel.
5. Every unsafe request (`POST`, `DELETE`) sends `X-CSRF-Token: state.csrfToken`.
6. After demo login, replace `state.csrfToken` with the token in the response.
7. After logout, clear `state.csrfToken`, call `GET /api/csrf` to obtain a fresh token, then show the picker.
8. On `403 CSRF_FAILED`: call `GET /api/csrf`, update the token, and show "Your security token expired. Please try again." Do not automatically repeat the state-changing request.
9. On `401`: clear client state, obtain a fresh CSRF token, and return to the picker with a session-expired notice.

### 8.6 Interaction Details

**Identity selection**

- Buttons show name, department, and an "Administrator" badge where applicable.
- The picker explains that anyone can select the administrator and that this is not authentication.
- During the request, disable all identity buttons and set `aria-busy="true"`.
- On success, hide the picker, update the CSRF token, show the app, and load data.
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
  - POST the request with the CSRF header.
  - On 201: clear the message, reset the counter, show a success toast, and reload the first employee feed page so the new kudos appears at the top.
  - On 400: show the field error, move focus to the field or error summary.
  - On 401/403 CSRF: follow the session/token recovery flow above.
  - On network/500: show a retryable error and keep the message so the user does not lose it.
  - Always re-enable the button in `finally`.

**Employee feed**

- Render only visible items, using the template; set giver, recipient, message, and time via `textContent`.
- Relative time: `Intl.RelativeTimeFormat` for recent items, with an absolute timestamp in the `title` attribute and a `<time datetime="...">` element.
- Long text: `overflow-wrap: anywhere` and `white-space: pre-wrap` for line breaks.
- "Load more": fetch with `offset = pagination.nextOffset`; append only IDs not already present; hide the button when `hasMore` is false.
- Empty feed: show the empty state, not an error.
- Feed error: show a retry control; keep already-loaded items visible.
- After creating or moderating, reload the first feed page to avoid offset drift and to ensure hidden/restored items are reflected.

**Moderation panel (admin only)**

- Shown only when `state.isAdmin`. This is a UI convenience; the server independently enforces the role.
- Load `GET /api/admin/kudos?limit=20&offset=0&visibility=all`.
- Each item displays giver → recipient, message, time, and a "Visible" or "Hidden" badge.
- Visibility filter: `all`, `visible`, `hidden`; changing it resets the list and offset.
- "Load more" appends the next page, deduplicating by ID.
- **Hide:** send `POST .../hide` with CSRF. On success, update the item to hidden, remove its ID from the employee feed, and refresh the moderation list and first employee feed page.
- **Restore:** send `POST .../restore` with CSRF. On success, update the item to visible and refresh the moderation list and first employee feed page.
- **Delete:** open the confirmation dialog. Store the pending ID. Do not send a request until the administrator activates "Delete permanently".
- **Delete confirmation:** send `DELETE .../{id}` with CSRF. On 204, close the dialog, remove the item from the moderation list and employee feed, and refresh the first feed page. On failure, keep the dialog open or show an error with a retry option.
- **Cancel:** close the dialog, clear the pending ID, and send nothing.
- If an item no longer exists (404), remove it from the list and show a notice.
- After each action, announce the result with `aria-live`.

**Session expiry**

- Any 401 from a protected endpoint triggers a single transition back to the picker, with a "Your demo session ended" notice. Avoid showing repeated errors for parallel requests.

### 8.7 Rendering Safety

- **Never** use `innerHTML` with kudos text, names, departments, or error messages.
- Create elements and assign `.textContent`.
- The Jinja template autoescapes any server-rendered values; in this design the shell contains no user data.
- The Content-Security-Policy forbids inline scripts and styles, so all JS and CSS live in external files.
- URLs are never constructed from user input.
- The delete dialog excerpt is inserted with `textContent`, not HTML.

### 8.8 Responsive Design

- Mobile-first CSS; base styles target 320 px and up.
- Content column: `max-width: 760px`, centred, with 16 px side padding.
- Header wraps on narrow screens; the user menu and role badge stack below the title if needed.
- The composer is a single column; on screens ≥ 640 px the counter and submit button sit in a row.
- Moderation cards stack their actions vertically on narrow screens; actions may sit in a row at ≥ 640 px.
- Feed and moderation cards use full width and 12–16 px padding.
- Primary controls are at least 44 × 44 CSS pixels.
- Form controls use `font-size: 16px` or larger to prevent iOS zoom.
- Breakpoints: base (mobile), `@media (min-width: 640px)`, `@media (min-width: 1024px)` where useful.
- No horizontal scrolling at 320 px; test with long messages and long names.
- The delete dialog fits within the viewport with internal padding and scrollable content if needed.
- Respect `prefers-reduced-motion` for toast and dialog transitions.

### 8.9 Accessibility

- One `<h1>`, sections with `<h2>` and `aria-labelledby`.
- Native `<label for>`, `<select>`, `<textarea>`, `<button>`.
- Visible `:focus-visible` outline with sufficient contrast.
- Character counter and error text connected through `aria-describedby`.
- `role="status"` / `aria-live="polite"` for success, loading, feed counts, and moderation results; `role="alert"` for blocking errors.
- After a failed submit, focus the error summary or the first invalid field.
- Keyboard-only path: choose identity → select recipient → type → submit → load more → hide/restore/delete.
- The native `<dialog>` is opened with `showModal()`, traps focus, closes on Escape, and returns focus to the triggering Delete button.
- The dialog's title and excerpt are programmatically associated.
- Colour contrast at least 4.5:1 for body text; do not rely on colour alone to convey visible/hidden status (use text badges).
- Test with VoiceOver on macOS as a manual check.

### 8.10 Progressive Enhancement

The app requires JavaScript to display data because the API is client-fetched. The HTML shell remains readable if JavaScript fails, and the UI shows a message if `fetch` is unavailable. A server-rendered fallback is out of scope.

---

## 9. Security Considerations

### 9.1 Demo Posture

The demo is explicitly **not secure for real use**:

- Anyone who can reach the port can impersonate any seeded user, **including the administrator**.
- There are no passwords, MFA, roles beyond the seeded values, or account recovery.
- The app binds to `127.0.0.1` by default.
- The UI and README state these limitations.
- Only fictional data is used.

These are acceptable **only** because the app is local and is a learning exercise. They must not be carried into production.

### 9.2 Implemented Controls

| Threat | Control |
|---|---|
| **SQL injection** | Every query uses `?`/named placeholders; no string interpolation of user input. |
| **XSS** | Messages stored as plain text; rendered with `textContent`; no `innerHTML`; Jinja autoescape; strict CSP; `X-Content-Type-Options: nosniff`. |
| **Broken access control** | Every moderation route uses `admin_required`, which loads the current user and role from the database and returns `403 FORBIDDEN` for employees. The employee feed filters `is_visible = 1` in SQL. |
| **Role spoofing** | The session stores only `user_id`; role is read from `users.role` on every request. Client-supplied `role`/`isAdmin` values are ignored. |
| **CSRF** | Per-session synchronizer token, required in `X-CSRF-Token` for all unsafe methods; constant-time comparison; token rotation on login; `SameSite=Lax` cookies. |
| **Session tampering** | Flask signs the cookie with `SECRET_KEY`; `HttpOnly`; `SameSite=Lax`; session contents are not exposed to JS. |
| **Session fixation** | `session.clear()` before setting the demo user; a new CSRF token is issued. |
| **Oversized requests** | `MAX_CONTENT_LENGTH = 16 KB`; `413` response. |
| **Mass assignment** | Only `recipientId` and `message` are read on create; moderation reads only the path ID; `giverId`, `id`, `createdAt`, `role`, and `isAdmin` are ignored. |
| **Irreversible deletion** | The UI requires explicit confirmation; deletion is admin-only and uses `DELETE`; the API documents it as permanent. |
| **Identity spoofing via body** | Giver and role always come from the server session and database. |
| **Error leakage** | Generic 500 message; details only in server logs; `DEBUG` off by default. |
| **Clickjacking** | `frame-ancestors 'none'` in CSP and `X-Frame-Options: DENY`. |
| **Referrer leakage** | `Referrer-Policy: no-referrer`. |
| **MIME sniffing** | `X-Content-Type-Options: nosniff`. |
| **Dependency risk** | Few dependencies, pinned ranges, `pip-audit` recommended in CI. |

**Response headers:**

```text
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self';
  img-src 'self' data:; connect-src 'self'; base-uri 'none';
  form-action 'self'; frame-ancestors 'none'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
```

### 9.3 CSRF Design Details

- `GET /api/csrf` creates a cryptographically random token (`secrets.token_urlsafe(32)`) in the signed session if absent.
- The API blueprint's `before_request` rejects unsafe methods without a matching `X-CSRF-Token`.
- Comparison uses `hmac.compare_digest`.
- The token is rotated on successful demo login. The login response returns the new token.
- Logout clears the session; the client fetches a new token before the next sign-in.
- `SameSite=Lax` provides an additional layer; the custom header cannot be set cross-origin without a CORS preflight, which this app does not grant.
- The client never stores the token in `localStorage`; it is held in memory.
- Failure responses do not reveal whether the session or the token was missing.

### 9.4 Production Requirements (Not Implemented)

- SSO/OIDC/SAML with verified identity and MFA.
- Server-side sessions with expiry, rotation, and revocation.
- Directory-derived roles and a named administration group.
- CSRF tokens rotated on every authentication or privilege change; Origin/`Sec-Fetch-Site` validation.
- HTTPS only, `Secure` cookies, HSTS.
- Rate limiting per user and IP (kudos creation, login, moderation).
- Duplicate/spam detection and abuse reporting.
- Secrets in a managed store; no development secret in production.
- Centralised, immutable audit logs for moderation actions, including moderator identity, timestamp, target, action, and optional reason.
- Privacy impact assessment; retention and deletion rules.
- Dependency scanning, SAST, and security review.
- Database backups and encryption at rest.

---

## 10. Performance Considerations

| Concern | Design |
|---|---|
| Employee feed query | Partial index `(created_at DESC, id DESC) WHERE is_visible = 1`; `WHERE is_visible = 1` in SQL; `LIMIT`/`OFFSET`. |
| Administrator list query | Full index `(created_at DESC, id DESC)`; optional visibility filter; paginated. |
| Pagination | `limit + 1` rows determines `hasMore` without a `COUNT(*)`; maximum page size 50. |
| N+1 queries | Avoided by joining both users in feed and admin queries. |
| Moderation writes | One indexed `UPDATE` or `DELETE` by primary key, followed by one joined read for hide/restore responses. |
| SQLite concurrency | WAL mode; `busy_timeout` 5 s; one connection per request. |
| Static assets | Served by Flask in development; production should use a reverse proxy or CDN with cache headers. |
| Caching | No application-level cache in the demo. The feed is small and read-heavy; SQLite is fast enough. Production could add HTTP `ETag`/`Cache-Control` for the first page or a short-lived cache if volume grows. |
| Offset pagination trade-off | Offset pagination can skip or duplicate items when rows are inserted or hidden/deleted. After create, hide, restore, or delete, the UI reloads the first feed page. The feed also deduplicates by ID. A cursor based on `(created_at, id)` is the recommended production upgrade. |
| Client work | Small DOM, no framework, template cloning; no full-page reloads. |
| Performance target | First visible feed page under 500 ms locally with 1,000 kudos. |

---

## 11. Error Handling and Logging

### 11.1 Error Handling Strategy

- Validation errors are raised as a custom `ValidationError` carrying a field map and converted to `400 VALIDATION_ERROR`.
- CSRF failures are returned by the API blueprint before route handlers run: `403 CSRF_FAILED`, no state change.
- Authorization failures return `403 FORBIDDEN`; missing sessions return `401 UNAUTHENTICATED`.
- Domain errors use explicit codes (`SELF_KUDOS`, `RECIPIENT_NOT_FOUND`, `USER_NOT_FOUND`, `KUDOS_NOT_FOUND`).
- Flask HTTP errors on `/api/*` are converted to the JSON envelope; page routes return a small HTML error page.
- Unexpected exceptions are logged with the request ID and return `500 INTERNAL_ERROR` without stack traces or database details.
- Database writes occur inside a transaction; any failure rolls back, so partial rows are impossible.
- The client distinguishes validation errors, session expiry, CSRF failure, authorization failure, network errors, and server errors, and preserves the user's message where possible.

### 11.2 Error Codes

See Section 7.6. Key additions in v0.2: `CSRF_FAILED`, `FORBIDDEN`, and `KUDOS_NOT_FOUND`.

### 11.3 Logging

- Use Python's standard `logging` module; log to stdout.
- Each request gets a UUID (`uuid.uuid4()`), returned in `X-Request-Id` and included in error responses.
- Access log fields: timestamp, level, request ID, method, path, status, duration in ms, current user ID (if signed in).
- Moderation log entries include actor user ID, kudos ID, and action (`hide`, `restore`, `delete`). They do **not** include the message body.
- **Never log** message bodies, cookies, CSRF tokens, session contents, secrets, or full request bodies.
- Log 500 errors with a stack trace server-side only.
- Logs are not a substitute for the audit trail excluded from this exercise. Production should ship structured JSON logs to a central system with retention and alerting.

---

## 12. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | Ephemeral random value + warning | Signs the session cookie and CSRF token. Must be stable in a real deployment. |
| `KUDOS_DB_PATH` | `data/kudos.db` (project-relative) | SQLite file location. |
| `HOST` | `127.0.0.1` | Bind address; local-only by default. |
| `PORT` | `5000` | Local port. |
| `KUDOS_DEBUG` | `0` | Enables Flask debug mode; never enabled in production. |
| `ALLOW_DEMO_LOGIN` | `1` | Enables demo identity routes; set to `0` in production. |
| `SESSION_COOKIE_SECURE` | `0` | Set to `1` behind HTTPS. |

- Configuration is read from environment variables with safe defaults.
- `.env` auto-loading is **not** included, to avoid an extra dependency; the README documents `export` commands.
- `KUDOS_DEBUG=1` enables Flask's debugger and must never be used outside local development; the app logs a prominent warning when it is enabled.
- `SESSION_COOKIE_HTTPONLY=True` and `SESSION_COOKIE_SAMESITE="Lax"` are set in code and are not configurable for the demo.
- Tests inject configuration directly into `create_app(test_config)`, overriding the database path and secret.

---

## 13. Testing Strategy

### 13.1 Test Levels

| Level | Tool | Scope |
|---|---|---|
| Unit | pytest | Message trimming, length boundaries, control characters, integer parsing, pagination parsing, role/visibility parsing. |
| Integration | pytest + Flask test client | CSRF, demo login/rotation, role authorization, users, create kudos, feed visibility/pagination, admin list, hide/restore/delete, persistence. |
| Manual | Browser + checklist | Responsive layout, keyboard use, screen-reader announcements, XSS rendering, confirmation dialog, visual states, demo administrator selection. |

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


def get_csrf(client):
    response = client.get("/api/csrf")
    return response.get_json()["csrfToken"]


def login(client, user_id):
    token = get_csrf(client)
    response = client.post(
        "/api/demo/session",
        json={"userId": user_id},
        headers={"X-CSRF-Token": token},
    )
    return response.get_json()["csrfToken"]
```

- Each test gets a fresh temporary database.
- Helpers sign in as an employee or the seeded administrator.
- Tests that exercise state changes always send `X-CSRF-Token`.
- Tests that verify CSRF protection deliberately omit or corrupt the token.

### 13.3 Planned Test Cases

**Validation (`test_validation.py`)**

- Trims leading/trailing whitespace.
- Accepts 1 and 500 characters; rejects 0 and 501.
- Rejects whitespace-only and non-string messages.
- Rejects NUL and control characters except `\n` and `\t`.
- Accepts emoji and non-ASCII text.
- Parses integer IDs; rejects strings, floats, and booleans.
- Parses `limit`/`offset` defaults, bounds, and invalid values.
- Parses moderation `visibility` values; rejects others.

**Authentication and CSRF (`test_api_auth.py`)**

- Protected GET endpoints return 401 without a session.
- Demo login sets a session; `/api/me` returns the user and role.
- Unknown/inactive user returns 404 and creates no session.
- Switching user clears the previous identity and rotates the CSRF token.
- The old CSRF token is invalid after login; the new token works.
- Demo endpoints return 404 when `ALLOW_DEMO_LOGIN` is false.
- `GET /api/csrf` works before login and returns a token.
- Unsafe requests without `X-CSRF-Token` return 403 `CSRF_FAILED` and do not change state.
- Unsafe requests with a wrong token return 403 `CSRF_FAILED`.
- A valid token on a protected route without a session returns 401.
- Logout requires a valid token and clears the session.
- CSRF is enforced on create, hide, restore, and delete.

**Users (`test_api_users.py`)**

- Active users only; sorted by name; no email or role exposed.
- Inactive users excluded.
- Demo user list includes roles and exactly one administrator.

**Kudos creation (`test_api_kudos.py`)**

- Valid request with CSRF returns 201 and inserts exactly one row.
- Giver comes from the session; a supplied `giverId`/`role` is ignored.
- Empty, whitespace-only, 501-character, and non-string messages are rejected.
- Self-kudos rejected.
- Unknown/inactive recipient rejected.
- Malformed JSON and wrong content type rejected.
- Leading/trailing whitespace trimmed in storage.
- XSS payload stored and returned as a literal string.
- Two sequential submissions create two rows.
- Database rollback leaves no row on failure.

**Employee feed (`test_api_feed.py`)**

- Only visible kudos are returned.
- Hidden kudos are excluded, including when interleaved with visible rows.
- Deleted kudos are absent.
- Newest first; ID tiebreaker correct.
- First page returns 20 by default; `hasMore`/`nextOffset` correct.
- `limit` bounds and invalid values.
- Empty feed returns `items: []`, not an error.
- JOIN returns giver and recipient names.
- Pagination metadata is based on the visible set only.

**Moderation (`test_api_moderation.py`)**

- Employee calls to admin list, hide, restore, and delete return 403 `FORBIDDEN`; no state changes.
- Administrator can list visible and hidden kudos.
- `visibility=visible|hidden|all` filters correctly; invalid values return 400.
- Hide sets `is_visible = 0`; the item disappears from the employee feed.
- Restore sets `is_visible = 1`; the item reappears at its original chronological position; `created_at` unchanged.
- Hide and restore are idempotent.
- Delete removes the row; repeat delete returns 404.
- Delete requires a valid CSRF token.
- GET on hide/restore/delete routes returns 405.
- A client-supplied role or `isAdmin` value has no effect.
- Demoting the admin in the database causes the next moderation request to return 403.
- The admin can moderate their own kudos (approved FR-30).

**Persistence**

- Create kudos, hide one, delete another, dispose the app/connection, create a new app against the same file: the visible, hidden, and deleted states are preserved.

### 13.4 Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
pytest tests/test_api_moderation.py -q
```

### 13.5 Manual QA Checklist

- [ ] First visit shows the identity picker; no feed data is visible.
- [ ] The picker marks exactly one administrator and warns that identity is simulated.
- [ ] Choosing a user shows the dashboard; reload preserves identity.
- [ ] Choosing the administrator shows the moderation panel and role badge.
- [ ] An employee does not see the moderation panel.
- [ ] Switch user returns to the picker and clears the previous session.
- [ ] Composer excludes the current user.
- [ ] Counter matches code-point length, including emoji.
- [ ] Empty, whitespace-only, and 501-character messages show errors.
- [ ] Submitting without a valid CSRF token shows the token-expired message and does not post.
- [ ] Double-clicking Submit creates one kudos.
- [ ] Success clears the form and puts the new item at the top.
- [ ] Feed shows giver, recipient, message, and readable time.
- [ ] "Load more" appends and eventually hides.
- [ ] Empty feed shows the empty state.
- [ ] Long messages and long names wrap at 320 px without horizontal scroll.
- [ ] Keyboard-only completion of the full employee flow.
- [ ] Administrator can see visible and hidden items in the moderation panel.
- [ ] Hide removes an item from the employee feed; it remains in the moderation panel as Hidden.
- [ ] Restore returns the item to the employee feed at its original position.
- [ ] Delete opens a confirmation dialog; Cancel sends no request; confirming removes the item permanently.
- [ ] Hidden and deleted items do not appear in employee API responses.
- [ ] A direct moderation API call as an employee returns 403.
- [ ] CSRF failure leaves state unchanged.
- [ ] Focus is visible; errors are announced; success is announced.
- [ ] Delete dialog traps focus, closes with Escape, and returns focus.
- [ ] `<script>alert(1)</script>` is displayed literally.
- [ ] Restarting the server preserves kudos, hidden state, and deletions.
- [ ] Browser console has no errors.

---

## 14. Implementation Plan

No work starts until the specification is approved. Timing is expressed as ordering and dependencies, not calendar estimates.

### Phase 0 — Foundation

| ID | Task | Depends on | Done when |
|---|---|---|---|
| **T0.1** | Create project skeleton, `.gitignore`, `requirements.txt`, `requirements-dev.txt`, README placeholder, and empty modules including `auth.py`. | — | Files exist; README documents the intended commands. |
| **T0.2** | Implement `schema.sql` and `db.py` with `users.role`, `kudos.is_visible`, full and partial indexes, init, seed, and transaction helpers. | T0.1 | A fresh database has both tables, constraints, indexes, and idempotent seed. |
| **T0.3** | Add 8 employees and 1 administrator to `seed.sql`. | T0.2 | Re-running seed does not duplicate users; exactly one admin exists. |
| **T0.4** | Create `create_app()` in `app.py`: config, page route, health endpoint, request IDs, security headers, logging, and error handlers. | T0.1 | `GET /` returns the shell; `GET /api/health` returns 200. |

### Phase 1 — Backend API, Auth, and Moderation

| ID | Task | Depends on | Done when |
|---|---|---|---|
| **T1.1** | Implement validation helpers and `ValidationError`, including moderation ID/visibility parsing. | T0.1 | Unit tests for message, parameter, and visibility rules pass. |
| **T1.2** | Implement `auth.py`: current-user loading, `login_required`, `admin_required`, CSRF token issue/validate/rotate. | T0.2, T0.4 | Guards return 401/403 correctly; CSRF helper tests pass. |
| **T1.3** | Implement `GET /api/csrf`, demo user list, login, and logout, including CSRF and login token rotation. | T1.2, T0.3 | Login, logout, rotation, disabled-demo, and CSRF behaviour match the contract. |
| **T1.4** | Implement `GET /api/me` (with role) and `GET /api/users` (without role/email). | T1.2, T1.3 | Current user and colleague list work; roles/emails are not leaked by `/api/users`. |
| **T1.5** | Implement `POST /api/kudos` with validation, CSRF, transaction, and joined response. | T1.1, T1.2, T1.4 | Valid create returns 201; all rejection cases return the specified codes. |
| **T1.6** | Implement `GET /api/kudos` with visible-only filter, JOIN, ordering, and pagination. | T1.1, T1.2, T1.4 | Hidden items never appear; order, limits, `hasMore`, and `nextOffset` are correct. |
| **T1.7** | Implement `GET /api/admin/kudos` with admin guard, visibility filter, and pagination. | T1.1, T1.2 | Admin sees visible and hidden items; employees get 403; filters work. |
| **T1.8** | Implement hide and restore endpoints with admin guard, CSRF, idempotency, and unchanged `created_at`. | T1.7 | Hide/restore update state; repeat calls succeed; invalid IDs return 404. |
| **T1.9** | Implement permanent delete with admin guard, CSRF, and 404 handling. | T1.7 | Delete removes the row; repeat delete returns 404. |
| **T1.10** | Add JSON error handlers for 400/401/403/404/405/413/500 and consistent envelopes. | T0.4, T1.1 | API errors always use the envelope; page errors remain HTML. |

### Phase 2 — Frontend

| ID | Task | Depends on | Done when |
|---|---|---|---|
| **T2.1** | Build `index.html`, CSS tokens, layout, kudos template, moderation template, and delete dialog. | T0.4 | Shell renders; layout is usable at 320 px and desktop. |
| **T2.2** | Implement `api.js`: CSRF-aware fetch wrapper, error handling, `GET /api/csrf` bootstrap. | T1.3, T2.1 | Safe and unsafe requests attach the correct headers; CSRF errors are surfaced. |
| **T2.3** | Implement identity picker with administrator badge and switch-user flow. | T1.3, T2.2 | Choose, persist on reload, switch, and token rotation all work. |
| **T2.4** | Implement composer: colleague list excluding self, counter, CSRF submit, field errors, double-submit guard. | T1.4, T1.5, T2.3 | Full create flow works; errors are shown and announced. |
| **T2.5** | Implement employee feed: visible-only first page, cards, relative time, empty/error states, load more, dedupe. | T1.6, T2.3 | Feed and pagination match acceptance criteria; hidden items absent. |
| **T2.6** | Implement moderation panel in `moderation.js`: visibility filter, list, pagination, Hide/Restore actions. | T1.7, T1.8, T2.2, T2.3 | Admin sees both states; actions update the panel and employee feed. |
| **T2.7** | Implement delete confirmation dialog and permanent delete flow. | T1.9, T2.6 | Cancel sends nothing; confirm deletes; focus and announcements are correct. |
| **T2.8** | Add success toasts, session-expiry handling, CSRF recovery, loading states, and accessibility polish. | T2.4, T2.5, T2.7 | Live regions, focus handling, 401/403 transitions verified. |
| **T2.9** | Responsive and visual polish; 44 px targets; 16 px inputs; long-text wrapping; dialog layout. | T2.8 | Manual checks at 320/768/1280 px pass. |

### Phase 3 — Verification and Documentation

| ID | Task | Depends on | Done when |
|---|---|---|---|
| **T3.1** | Write validation unit tests. | T1.1 | All planned unit cases pass. |
| **T3.2** | Write auth, CSRF, role, and login-rotation integration tests. | T1.2–T1.4 | Auth/CSRF/role tests pass against temporary databases. |
| **T3.3** | Write moderation and visible-feed integration tests. | T1.5–T1.9 | Hide/restore/delete, 403s, pagination, and visibility tests pass. |
| **T3.4** | Run the manual QA checklist and fix defects. | T2.9, T3.2, T3.3 | Every checklist item passes. |
| **T3.5** | Verify persistence across a real restart, including hidden and deleted states. | T1.8, T1.9, T2.7 | States survive restart. |
| **T3.6** | Complete README: setup, run, demo identity and admin warning, CSRF note, tests, reset instructions. | T0.1, T3.4 | A new person can run the demo from the README alone. |
| **T3.7** | Review implementation against REQUIREMENTS.md and record deviations. | All | No unexplained deviations; spec or code updated as agreed. |

### Critical Path

```text
T0.1 → T0.2 → T0.3 → T1.2 → T1.3 → T1.4 → T1.5 → T2.4 → T2.8 → T2.9 → T3.4 → T3.7

Moderation branch:
T1.7 → T1.8 → T1.9 → T2.6 → T2.7
```

### Sequencing Notes

- Backend endpoints exist before their frontend consumers, so the UI can be built against a stable contract.
- CSRF and role guards are implemented before any state-changing endpoint, so new routes are protected by default.
- Tests for a module are written alongside or immediately after it; final verification is a separate gate.
- The moderation schema and endpoints are designed once, before implementation, to avoid retrofitting authorization mid-build.

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
- Seed users are inserted on first start, including one administrator.
- Stop with Ctrl+C.
- Reset the demo by deleting `data/kudos.db`, `data/kudos.db-wal`, and `data/kudos.db-shm`. This also clears all moderation state and sessions.
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
- Sync roles from directory groups; protect the admin role.
- Rotate CSRF tokens on authentication/privilege changes; validate Origin.
- Add structured logging, metrics, health/readiness checks, and alerts.
- Add rate limiting, abuse controls, and an immutable moderation audit trail.
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
| Demo administrator mistaken for a secure admin | High | High | Visible demo banner; admin badge; README warning; localhost binding; demo routes disabled in production. |
| Broken access control on a moderation route | Medium | High | Central `admin_required` guard; every route uses it; integration tests call each route as an employee. |
| CSRF token lifecycle bug (login rotation/logout) | Medium | High | Explicit token flow; tests for missing/wrong/rotated tokens; client refreshes and asks for manual retry. |
| Hidden kudos leak through an employee endpoint | Medium | High | SQL-level `is_visible = 1` in the only employee feed query; tests with hidden rows interleaved; no generic kudos-by-ID endpoint. |
| Role cached in the session or trusted from the client | Medium | High | Session stores only `user_id`; role loaded from DB per request; tests demote an admin mid-session. |
| Delete confirmation bypassed by direct API call | Medium | Medium | Deletion is admin-only and CSRF-protected; UI confirmation is required; API documents permanence. A compromised admin can still delete directly by design. |
| Offset pagination skips/duplicates after hide/delete | Medium | Low | Reload the first feed page after moderation; client dedupe; cursor pagination as a production upgrade. |
| No moderation audit trail | Certain | Medium | Explicitly out of scope; basic logs record actor, kudos ID, and action; production must add an immutable audit trail. |
| Ambiguous assumptions baked into schema | Low | Medium | All v0.2 assumptions were approved on 2026-10-18 and are recorded in REQUIREMENTS.md; production questions remain explicitly listed as non-blocking. |
| Python 3.9 end-of-life | High over time | Medium | Demo only; production on Python 3.11+; pin versions. |
| SQLite single-writer bottleneck | Low at demo scale | Medium | WAL; low write volume; reassess for production multi-instance. |
| XSS through message rendering | Low if rules followed | High | `textContent` only; code review; CSP; manual XSS test. |
| Seed data mistaken for real employees | Low | Medium | Fictional names/emails; README states they are fake. |
| Unicode length mismatch between JS and Python | Medium | Low | Count code points in both; remove `maxlength`; server authoritative. |
| Secret leakage | Low | High | No secrets in repo; environment configuration; managed store in production. |
| Timezone confusion | Medium | Low | Store UTC; parse with `Date`; show local time and absolute title. |

---

## 17. Open Design Questions

### 17.1 Resolved in v0.2

- Stack: Python, Flask, SQLite, vanilla HTML/CSS/JavaScript (accepted 2026-10-18).
- Feed access: authenticated demo users only (accepted).
- Self-kudos: disallowed (accepted).
- Anonymous kudos: disallowed (accepted).
- Message rules: 1–500 characters after trimming, plain text (accepted).
- Ordering: newest first, 20 per page, `created_at DESC, id DESC` (accepted).
- Author edit/delete: not available; administrators moderate by role (accepted).
- Notifications: none (accepted).
- Deployment: local only, bound to `127.0.0.1` (accepted).
- Moderation: hide/restore and permanent delete; admin-only; no persisted audit trail.
- Role model: `users.role` with `employee` and `admin`; one seeded admin.
- CSRF: per-session synchronizer token in `X-CSRF-Token`; rotate on login.

### 17.2 Unresolved — Non-Blocking

| ID | Question | Approved demo default | Blocks implementation? |
|---|---|---|---|
| OQ-05 | Production identity provider/protocol | SSO/OIDC for production only. | No |
| OQ-07 | Production retention/export/deletion policy | Demo retains data; production policy TBD. | No |
| OQ-08 | Production rate limits/duplicate detection | None in the demo. | No |
| OQ-09 | Automated profanity filtering | None; manual moderation only. | No |
| OQ-11 | Production scale | Low volume, single instance. | No |
| OQ-14 | Future portal integration | Standalone now. | No |
| OQ-16 | Admin moderating own kudos | Allowed (FR-30/A-19). | No |
| OQ-17 | Persisted moderation audit fields/reasons | Excluded by scope (A-20). | No |

**No unresolved question blocks implementation.** This design was approved for implementation on 2026-10-18.

---

## 18. Review and Approval

**Approved on 2026-10-18.** The project owner gave this approval in the development conversation:

> I formally approve REQUIREMENTS.md and DESIGN.md v0.2 for implementation.
>
> I also accept the documented defaults:
> - Administrators may moderate kudos they sent.
> - Moderation audit fields are outside this demo's scope.
> - Hide and restore operations are idempotent.
> - The moderation panel appears on the same dashboard.

The approved material includes:

- [x] The moderation model: hide/restore plus permanent delete, admin-only, with no persisted audit fields.
- [x] `users.role` values and the single seeded administrator.
- [x] Server-side role resolution from the database, never from client input.
- [x] The CSRF mechanism and token rotation at sign-in.
- [x] The explicit limitation that anyone can select the demo administrator and that this is not authentication.
- [x] The v0.2 design, with v0.1 preserved unchanged under `snapshots/v0.1/`.
- [x] Consolidation into `SPECIFICATION.md`.
- [x] Implementation and validation before repository publication.

The v0.2 snapshot remains an unchanged record of the approved baseline taken immediately before implementation. [SPECIFICATION.md](SPECIFICATION.md) is the consolidated final specification.

---

## 19. Change Log

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-10-18 | AI development partner | Initial technical design; frozen in `snapshots/v0.1/`. |
| 0.2 | 2026-10-18 | AI development partner | Added role and visibility schema, admin seed, moderation API and UI, server-side authorization, CSRF token flow, visible-only feed filtering, and restart persistence. Excluded audit/reporting/automated moderation. |
| 1.0 | 2026-10-18 | Project owner and AI development partner | Formally approved v0.2; recorded the approval statement; consolidated the approved requirements and design into `SPECIFICATION.md`. No design changes were made after approval. |
