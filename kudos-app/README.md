# Kudos Demo

A small, locally runnable employee recognition app built for the Datacom Forage
Task 2 simulation. Employees choose a colleague, write a short message of
appreciation, and publish it to a shared dashboard feed. A fictional
administrator can hide, restore, or permanently delete kudos that are not
appropriate for the feed.

The application uses Python, Flask, SQLite, and vanilla HTML/CSS/JavaScript.
It has no external services, no build step, and no third-party frontend
dependencies.

## Important: demo identity is not authentication

This is a **local demonstration**, not a production employee portal.

- There is no password, SSO, email verification, or real authentication.
- A visitor selects any seeded fictional user from an identity picker.
- **Anyone running the demo can select the fictional administrator,
  Morgan Reed.** This demonstrates role-based authorization; it does not secure
  the administrator role.
- All names, departments, and kudos are fictional. No real employee data is
  included.
- The server binds to `127.0.0.1` by default. Do not expose it to a network or
  deploy it as-is.
- The demo identity routes can be disabled with `ALLOW_DEMO_LOGIN=0`, but then
  no one can sign in because production authentication is out of scope.

A production deployment would replace the identity picker with real
authentication (for example, SSO), keep roles in a trusted directory or
database, serve over HTTPS, use an external secret manager, and add audit
logging and retention policies.

## Requirements

- Python 3.9 or newer (tested with Python 3.9.6)
- `pip`
- A modern browser

## Setup

From this `kudos-app` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

`requirements-dev.txt` installs the runtime dependency (Flask) plus pytest.
If you only want to run the app, `pip install -r requirements.txt` is enough.

On Windows, activate the environment with:

```powershell
.venv\Scripts\activate
```

## Run the app

```bash
# Optional but recommended: keep sessions valid across restarts.
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

python app.py
```

Open <http://127.0.0.1:5000>.

The SQLite database is created automatically at `data/kudos.db` on first run,
and the nine fictional demo users are seeded once. The initial feed is empty.

### Configuration

All configuration is through environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Random per process | Signs the session cookie. If unset, a warning is logged and sessions/CSRF tokens reset on restart. |
| `KUDOS_DB_PATH` | `data/kudos.db` | SQLite database file. Parent directories are created automatically. |
| `HOST` | `127.0.0.1` | Bind address. Keep the localhost default for the demo. |
| `PORT` | `5000` | Port to listen on. |
| `KUDOS_DEBUG` | `0` | Set to `1` to enable Flask debug mode. Local development only. |
| `ALLOW_DEMO_LOGIN` | `1` | Set to `0` to disable the demo identity endpoints. |
| `SESSION_COOKIE_SECURE` | `0` | Set to `1` when serving over HTTPS. Leave `0` for local HTTP. |

Example with a different port and an explicit database path:

```bash
PORT=5001 KUDOS_DB_PATH=/tmp/kudos-demo.db python app.py
```

## Using the demo

1. On the welcome screen, select a fictional employee such as **Alice Ng**.
2. In the composer, choose a colleague, write 1–500 characters, and submit.
3. The new kudos appears at the top of the shared feed.
4. Open the user menu and **Switch user**.
5. Select **Morgan Reed** (the administrator) to show the moderation panel.
6. In the moderation panel you can:
   - filter by **All**, **Visible**, or **Hidden**;
   - **Hide** a kudos — a reversible visibility change that removes it from the
     employee feed while keeping the record;
   - **Restore** a hidden kudos — makes it visible in the employee feed again;
   - **Delete** a kudos — permanently removes it after a confirmation dialog.
7. Switch back to an employee to confirm hidden and deleted kudos are absent
   from the feed.

Moderation changes are written to SQLite and survive an application restart.
Hiding and restoring are idempotent. Deleting is permanent.

## Test the app

Run the full suite from `kudos-app` with the virtual environment active:

```bash
pytest -q
```

The tests use temporary SQLite databases and Flask's test client; they do not
touch `data/kudos.db`. Coverage includes:

- message validation, length boundaries, Unicode, control characters, and
  malformed or oversized request bodies;
- demo sign-in, session switching, logout, and CSRF token rotation;
- CSRF enforcement on every state-changing endpoint, including precedence over
  authentication;
- server-side session and role authorization for every administrator endpoint;
- role changes being read from the database on each request;
- visible-only feed filtering, deterministic ordering, and pagination;
- hide and restore idempotency, deletion semantics, and preservation of
  `created_at`;
- moderation changes surviving an application restart;
- frontend source contracts for awaited async error handlers, server field
  errors beside their inputs, feed Retry behavior, actual moderation errors,
  CSRF refresh ordering, and failed-delete dialog behavior.

For the approved specification and the validation summary, see the repository
root: [`SPECIFICATION.md`](../SPECIFICATION.md) and
[`IMPLEMENTATION.md`](../IMPLEMENTATION.md).

## Project structure

```text
kudos-app/
├── app.py                 # Application factory, page route, headers, errors
├── api.py                 # JSON API and administrator moderation routes
├── auth.py                # Demo session, CSRF, and role decorators
├── db.py                  # SQLite connection lifecycle, schema, and seed
├── validation.py          # Server-side validation and API error types
├── schema.sql             # Tables, constraints, and indexes
├── seed.sql               # Fictional demo users and kudos
├── requirements.txt       # Runtime dependencies
├── requirements-dev.txt   # Runtime plus test dependencies
├── templates/index.html   # Accessible single-page shell
├── static/
│   ├── css/styles.css
│   └── js/
│       ├── api.js         # Fetch wrapper and CSRF handling
│       ├── app.js         # Identity picker, composer, and feed
│       └── moderation.js  # Administrator moderation panel
├── tests/                 # pytest suite
└── data/                  # Local SQLite database (created at runtime, ignored)
```

## API overview

All API responses are JSON. Unsafe requests (`POST`, `PUT`, `PATCH`, `DELETE`)
must include the `X-CSRF-Token` header. The client obtains a token from
`GET /api/csrf`; the token rotates at sign-in.

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Public | Health check |
| `GET` | `/api/csrf` | Public | Get or refresh the CSRF token |
| `GET` | `/api/demo/users` | Public (demo only) | List fictional identities |
| `POST` | `/api/demo/session` | CSRF | Choose a demo identity |
| `DELETE` | `/api/demo/session` | Session + CSRF | Sign out |
| `GET` | `/api/me` | Session | Current user and role |
| `GET` | `/api/users` | Session | Active colleagues |
| `GET` | `/api/kudos` | Session | Visible kudos feed |
| `POST` | `/api/kudos` | Session + CSRF | Create a kudos |
| `GET` | `/api/admin/kudos` | Admin | List all kudos; `visibility=all\|visible\|hidden` |
| `POST` | `/api/admin/kudos/{id}/hide` | Admin + CSRF | Hide a kudos |
| `POST` | `/api/admin/kudos/{id}/restore` | Admin + CSRF | Restore a hidden kudos |
| `DELETE` | `/api/admin/kudos/{id}` | Admin + CSRF | Permanently delete a kudos |

Feed pagination uses `limit` (1–50, default 20) and `offset` (default 0).
Ordering is `created_at DESC, id DESC` for deterministic results.

## Security notes

Implemented in this demo:

- The acting user is always derived from the signed session cookie, and the
  role is reloaded from SQLite on every request. Client-supplied `giverId` or
  `role` fields are ignored.
- Administrator endpoints enforce authorization on the server, so calling them
  directly from a tool still returns `403 Forbidden` for employees.
- A per-session synchronizer CSRF token is required on every unsafe request.
  On unsafe requests the CSRF check runs before authentication.
- All SQL uses parameterized statements.
- Messages are rendered with `textContent`, never `innerHTML`, and a strict
  Content Security Policy blocks inline and third-party scripts.
- Request bodies are capped at 16 KB and messages at 500 Unicode code points.
- Responses include `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and `Cache-Control: no-store` for API responses.
- The server binds to localhost by default.

Not suitable for production without the additions listed under
[Important: demo identity is not authentication](#important-demo-identity-is-not-authentication).

## Resetting the demo data

Stop the server, then delete the SQLite files:

```bash
rm -f data/kudos.db data/kudos.db-wal data/kudos.db-shm
```

The next `python app.py` recreates the schema and seeds the fictional users.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'flask'`** — the virtual environment
  is not active. Run `source .venv/bin/activate` (or the Windows equivalent).
- **Port already in use** — run on another port: `PORT=5001 python app.py`.
- **“Security token missing or invalid”** — refresh the page. Tokens rotate at
  sign-in and reset if the app restarts without a fixed `SECRET_KEY`.
- **Sessions reset after every restart** — set a stable `SECRET_KEY` as shown
  above.
- **Database is locked** — stop any other running copy of the app, then retry.
