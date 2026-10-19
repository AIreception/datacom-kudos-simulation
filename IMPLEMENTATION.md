# Implementation and Validation Summary

- **Status:** Implementation complete; source published, application not deployed
- **Approved specification:** [SPECIFICATION.md](SPECIFICATION.md)
- **Project:** Datacom Forage Task 2 — standalone Kudos demo
- **Date:** 2026-10-18

## Implementation summary

The implementation follows the approved v0.2 requirements and technical design. It is a standalone Flask application backed by SQLite, with a vanilla HTML/CSS/JavaScript frontend and no build step.

Delivered functionality:

- **Demo identity:** nine fictional seeded users, including one administrator
  (Morgan Reed). Identity is selected from a picker and stored in a signed
  session cookie. This is explicitly not authentication.
- **Kudos workflow:** choose an active colleague, write a 1–500 character
  plain-text message, and submit it. The giver is always derived on the server
  from the session; client-supplied identity and role fields are ignored.
- **Public feed:** visible kudos only, newest first, 20 per page, with
  deterministic ordering and a Load more control.
- **Moderation:** an administrator-only panel lists visible and hidden kudos,
  supports filtering, hides or restores kudos (reversible visibility changes),
  and permanently deletes after confirmation.
- **Authorization:** session and administrator checks run on the server for
  every protected endpoint. Roles are reloaded from SQLite on every request.
- **CSRF:** a per-session synchronizer token from `GET /api/csrf` is required in
  `X-CSRF-Token` on every unsafe request; the token rotates at sign-in.
- **Validation and errors:** server-side validation is authoritative; field
  errors are shown beside the relevant input, feed failures expose a working
  Retry button, moderation failures show their actual message, and a failed
  delete keeps its dialog open so the administrator can retry or cancel.
- **Persistence:** schema, seed users, kudos, and moderation state live in a
  local SQLite database and survive restarts.
- **Security headers and rendering:** strict Content Security Policy,
  `textContent` for all user-generated text, parameterized SQL, a 16 KB request
  body limit, and localhost binding by default.

## Changes found during validation

An independent frontend review found that the async `handleApiError()` result
was used directly as a boolean in four places in `app.js`, and that the shared
`handleError` callback in `moderation.js` had the same problem. Because a
Promise is always truthy, several error paths were suppressed. The fix awaits
the handler before testing its result at every call site.

The failed-delete flow was tightened at the same time: only session expiry
(`401`) and an already-deleted kudos (`KUDOS_NOT_FOUND`) close the delete
dialog. Every other failure, including a refreshed CSRF token, a permission
error, or a network/server failure, keeps the dialog open with Retry and Cancel
available.

Focused source-contract regression tests were added in
`kudos-app/tests/test_frontend_contracts.py` so these async and dialog
behaviours cannot silently regress.

## Automated tests

Command, run from `kudos-app` with the virtual environment active:

```bash
python -m pytest -q
```

Result on 2026-10-18:

```text
180 passed in 1.58s
```

The suite uses temporary SQLite databases and Flask's test client. It covers:

- demo sign-in, session switching, logout, CSRF token rotation, and CSRF
  precedence over authentication;
- validation boundaries, Unicode code-point length, control characters,
  malformed JSON, and oversized bodies;
- self-kudos, unknown or inactive recipients, and server-derived giver identity;
- visible-only feed filtering, newest-first ordering, and pagination;
- server-side authorization for every administrator endpoint, including direct
  API calls by employees and client-supplied role fields;
- role changes read from the database on each request;
- hide and restore idempotency, permanent deletion, and preservation of the
  original `created_at`;
- moderation changes surviving an application restart;
- nine frontend source-contract checks for awaited error handlers, field-error
  placement, feed Retry behavior, actual moderation errors, CSRF refresh
  ordering, and delete-dialog behavior.

## Browser checks

A one-off headless Chrome run used Google Chrome 155.0.8059.80 through the
DevTools Protocol against a real local Flask server and a temporary database.
Network failures were injected by replacing `window.fetch` in the page; no
product code was modified for the checks. All 11 checks passed:

| Check | Result |
|---|---|
| Demo login and feed render | Passed |
| Server field errors appear beside the recipient and message inputs, with `aria-invalid` set | Passed |
| Feed server failure shows the actual error and Retry recovers the feed | Passed |
| Administrator moderation panel renders | Passed |
| Moderation failure displays the server's actual error | Passed |
| CSRF refresh completes before the retry notice appears | Passed |
| Failed delete keeps the dialog open with Retry and Cancel enabled | Passed |
| Cancel closes the failed dialog without deleting the kudos | Passed |
| Retry after a failed delete succeeds and closes the dialog | Passed |
| Already-deleted (`KUDOS_NOT_FOUND`) closes the dialog and explains why | Passed |
| Session expiry (`401`) closes the dialog and returns to the identity picker | Passed |

The browser harness is not part of the pytest suite because it depends on a
local Chrome installation and platform-specific launching. It was used as
additional verification for this implementation.

## Remaining manual checks

The following are not fully covered by automation and remain manual checks:

- a real network disconnection or stopped server, rather than an injected HTTP
  failure;
- real elapsed session expiry, rather than an injected `401`;
- Firefox and Safari rendering and behavior (the browser run used Chrome only);
- screen-reader and full keyboard walkthroughs (basic labels, focus handling,
  and `aria-invalid` are implemented, but no formal accessibility audit was
  performed);
- visual review of responsive layout on physical phone and desktop screens;
- production concerns intentionally outside this demo: SSO, HTTPS, managed
  secrets, audit trail, retention, rate limiting, and deployment hardening.

## Reproduce the validation

```bash
cd kudos-app
source .venv/bin/activate
python -m pytest -q
```

To run the application locally, follow [kudos-app/README.md](kudos-app/README.md).

## Deployment status

The application was **not deployed**. Step 4 publishes the source repository
only. The demo is designed for local use on `127.0.0.1` and must not be exposed
as a production employee portal.
