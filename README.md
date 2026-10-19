# Kudos System — Datacom Forage Task 2

A small, locally runnable employee recognition application built through a
spec-driven development process. Employees choose a colleague, write a short
message of appreciation, and publish it to a shared dashboard feed. A fictional
administrator can hide, restore, or permanently delete inappropriate kudos.

The application uses Python, Flask, SQLite, and vanilla HTML/CSS/JavaScript.
It has no external services, no build step, and no third-party frontend
dependencies. It is a demonstration, not a production employee portal, and it
is not deployed.

## Documentation

| Document | Purpose |
|---|---|
| [SPECIFICATION.md](SPECIFICATION.md) | Final approved requirements and technical design, with the project owner's approval record |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | Implementation summary and validation results (automated tests, browser checks, manual checks) |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Approved requirements document |
| [DESIGN.md](DESIGN.md) | Approved technical design document |
| [snapshots/v0.1](snapshots/v0.1/) | Frozen initial draft, kept for review history |
| [snapshots/v0.2](snapshots/v0.2/) | Frozen approved baseline taken immediately before implementation |
| [kudos-app/README.md](kudos-app/README.md) | Detailed application guide: configuration, API, security notes, troubleshooting |

## Important: demo identity is not authentication

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
authentication (for example, SSO/OIDC), keep roles in a trusted directory or
database, serve over HTTPS, use a managed secret store, and add audit logging,
retention policies, rate limiting, and deployment hardening.

## Requirements

- Python 3.9 or newer (tested with Python 3.9.6)
- `pip`
- A modern browser

## Setup

From the repository root:

```bash
cd kudos-app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

`requirements-dev.txt` installs Flask plus pytest. If you only want to run the
application, `pip install -r requirements.txt` is enough.

On Windows, activate the virtual environment with:

```powershell
.venv\Scripts\activate
```

## Run the application

```bash
cd kudos-app

# Optional but recommended: keep sessions valid across restarts.
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

python app.py
```

Open <http://127.0.0.1:5000>.

The SQLite database is created automatically at `kudos-app/data/kudos.db` on
first run, and the nine fictional demo users are seeded once. The initial feed
is empty.

Configuration is through environment variables (`SECRET_KEY`, `KUDOS_DB_PATH`,
`HOST`, `PORT`, `KUDOS_DEBUG`, `ALLOW_DEMO_LOGIN`, and
`SESSION_COOKIE_SECURE`). See [kudos-app/README.md](kudos-app/README.md) for the
full table and examples.

## Test the application

```bash
cd kudos-app
source .venv/bin/activate
python -m pytest -q
```

The suite uses temporary SQLite databases and Flask's test client; it does not
touch `kudos-app/data/kudos.db`. It covers validation, demo sessions and CSRF,
server-side authorization, visible-only feed behavior, moderation, restart
persistence, and focused frontend error-handling contracts.

On 2026-10-18 the full suite passed:

```text
180 passed in 1.58s
```

Additional headless Chrome checks exercised field-error placement, feed Retry,
moderation errors, CSRF refresh ordering, and delete-dialog behavior. See
[IMPLEMENTATION.md](IMPLEMENTATION.md) for exactly what was automated, what was
browser-checked, and what remains manual.

## Project structure

```text
.
├── SPECIFICATION.md          # Final approved requirements and design
├── IMPLEMENTATION.md         # Implementation and validation summary
├── REQUIREMENTS.md           # Approved requirements
├── DESIGN.md                 # Approved technical design
├── snapshots/                # Frozen v0.1 and v0.2 specification snapshots
├── README.md                 # This repository guide
└── kudos-app/
    ├── app.py                # Application factory, page route, headers, errors
    ├── api.py                # JSON API and administrator moderation routes
    ├── auth.py               # Demo session, CSRF, and role decorators
    ├── db.py                 # SQLite lifecycle, schema, and seed
    ├── validation.py         # Server-side validation and API error types
    ├── schema.sql            # Tables, constraints, and indexes
    ├── seed.sql              # Fictional demo users
    ├── templates/index.html  # Accessible single-page shell
    ├── static/               # CSS and ES-module JavaScript
    ├── tests/                # pytest suite
    └── data/                 # Local SQLite database (created at runtime, ignored)
```

## Security notes

Implemented in this demo:

- The acting user comes from the signed session cookie, and the role is
  reloaded from SQLite on every request. Client-supplied `giverId` or `role`
  values are ignored.
- Every administrator endpoint enforces authorization on the server, so direct
  API calls by an employee return `403 Forbidden`.
- Every unsafe request requires a per-session CSRF token; the token rotates at
  sign-in.
- SQL is parameterized, user-generated text is rendered with `textContent`, and
  a strict Content Security Policy blocks inline and third-party scripts.
- Request bodies are capped at 16 KB and messages at 500 Unicode code points.
- The server binds to localhost by default and is not intended for deployment.

## Status

Implementation and local validation are complete. The source repository is
published for the Datacom Forage simulation. The application is **not
deployed**.
