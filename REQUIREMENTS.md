# Kudos System — Requirements

- **Status:** APPROVED v0.2 — approved for implementation on 2026-10-18
- **Date:** 2026-10-18
- **Project:** Datacom Forage Task 2 — standalone Kudos demo
- **Related document:** [DESIGN.md](DESIGN.md)
- **Consolidated specification:** [SPECIFICATION.md](SPECIFICATION.md)
- **Supersedes:** v0.1 (frozen at [snapshots/v0.1/REQUIREMENTS.md](snapshots/v0.1/REQUIREMENTS.md))

> **Approved for implementation on 2026-10-18.** The project owner formally approved this requirements document and DESIGN.md v0.2. This file remains the approved requirements record; [SPECIFICATION.md](SPECIFICATION.md) consolidates the approved requirements and design. The v0.1 snapshot remains frozen and unchanged.

## What Changed in v0.2

- Added administrator user story **US-09** for hiding, restoring, and permanently deleting inappropriate kudos.
- Added testable moderation acceptance criteria **AC-09-1 … AC-09-15**.
- Added `users.role` (`employee` | `admin`) and one fictional administrator to the demo data.
- Added `kudos.is_visible` (`INTEGER NOT NULL DEFAULT 1`, constrained to 0/1).
- Added server-side role authorization for every moderation endpoint; role is read from the database, never from client input.
- Added CSRF protection for all state-changing requests, including the demo identity flow.
- Added explicit rules that moderation actions use non-GET methods and that hidden/deleted kudos never appear in employee API responses.
- Recorded the assumptions accepted by the project owner on 2026-10-18.
- Kept moderation audit fields, reporting, automated moderation, and notifications out of scope.

The frozen v0.1 snapshot is available in `snapshots/v0.1/` for diff review.

---

## 1. Purpose and Background

Datacom wants an internal way for employees to recognise each other. The feature lets a signed-in employee choose a colleague, write a short message of appreciation, submit it, and see recent recognition from across the company in a public feed on the dashboard.

Because the feed is public inside the company, the system also needs **content moderation**: an administrator must be able to remove inappropriate recognition from the employee feed. Moderation must not be possible for ordinary employees, even if they call the API directly.

This is a **new, standalone application**. No existing employee portal, user directory, authentication service, or dashboard is available to integrate with. The application's own home page acts as the "main dashboard" for the demo.

The demo must be small, locally runnable, and use persistent storage with minimal dependencies.

---

## 2. Scope

### 2.1 In Scope (Initial Demo)

- A locally runnable web application.
- Demo identity selection using seeded, fictional employees.
- One seeded fictional administrator.
- Employee and administrator roles.
- A colleague list for choosing a recipient.
- A composer for a short, plain-text kudos message.
- Server-side validation and clear error feedback.
- Persistent storage that survives application restarts.
- A public, reverse-chronological feed of recent, **visible** kudos.
- Pagination ("Load more") for older visible kudos.
- An administrator moderation view showing both visible and hidden kudos.
- Hide (soft delete) and restore visibility.
- Permanent deletion after explicit UI confirmation.
- Server-side authorization for every moderation endpoint.
- CSRF protection for every state-changing request.
- Responsive layout for mobile and desktop.
- Basic accessibility (keyboard, labels, focus, announcements).
- Automated tests for validation, authorization, CSRF, and API behaviour.

### 2.2 Out of Scope (Approved)

The following are **not** requirements in this version.

- Reporting workflows (employee reporting of kudos).
- Automated moderation, profanity filters, or machine-learning classification.
- Notifications (email, Teams, Slack).
- A full moderation audit system: no `moderated_by`, `moderated_at`, or `reason_for_moderation` fields, no moderation history UI, no appeals.
- Editing one's own kudos.
- Reactions, comments, likes, points, or leaderboards.
- Employee profiles or recognition histories.
- Search, filtering, or sorting options in the employee feed.
- Anonymous or private kudos.
- Analytics and reporting.
- Real corporate authentication / SSO integration.
- Localisation / multi-language UI.
- Native mobile applications.
- Integration into an existing portal (none exists).

> **Scope boundary:** moderation in this exercise is limited to **hide, restore, and permanent delete**, guarded by role authorization and CSRF. Basic application logs of moderation actions are allowed for debugging, but there is no persisted audit trail.

### 2.3 Product Boundary

| Item | Decision |
|---|---|
| Standalone app | Yes. One Flask application serves the page and the API. |
| "Main dashboard" | The application home page. |
| Storage | Local SQLite file (persistent across restarts). |
| Users | Seeded fictional employees, including one administrator. |
| Roles | `employee` and `admin`, stored in the database. |
| Moderation | Hide/restore and permanent delete, admin-only. |
| Real employee data | Not used. |

---

## 3. Definitions

| Term | Meaning |
|---|---|
| **Kudos** | A short public message of appreciation from one employee to another. |
| **Giver** | The signed-in employee who submits the kudos. Derived from the server-side session, never from client input. |
| **Recipient** | The colleague selected to receive the kudos. |
| **Feed** | The reverse-chronological list of **visible** kudos shown to employees. |
| **Demo user** | A fictional, seeded employee used to simulate sign-in. |
| **Demo session** | A signed browser cookie that records which demo user is currently acting. It is **not** real authentication. |
| **Role** | The value stored in `users.role`: `employee` or `admin`. |
| **Administrator** | A user with `role = 'admin'`. Can moderate kudos in addition to employee actions. |
| **Moderation** | Hiding, restoring, or permanently deleting a kudos. |
| **Hide (soft delete)** | Set `kudos.is_visible = 0`. The row remains in the database but is excluded from employee responses. |
| **Restore** | Set `kudos.is_visible = 1`. The kudos returns to the employee feed at its original chronological position. |
| **Permanent delete (hard delete)** | Remove the kudos row from the database. It cannot be restored. |
| **Moderation view** | The administrator-only UI that lists visible and hidden kudos with moderation controls. |
| **CSRF token** | A per-session unpredictable value required in a request header for state-changing requests. |
| **Active user** | A user with `is_active = 1`, eligible to appear in the colleague list and receive kudos. |
| **Character** | A Unicode code point, as counted by Python `len()` on a `str`. |

---

## 4. Users and Roles

| Role | Description | Permissions |
|---|---|---|
| **Employee** | A signed-in demo user with `role = 'employee'`. | View visible feed; select colleague; create kudos. Cannot hide, restore, delete, or list hidden kudos. |
| **Administrator** | A signed-in demo user with `role = 'admin'`. Administrators are also employees. | All employee permissions, plus: view visible and hidden kudos, hide, restore, and permanently delete kudos. |
| **Anonymous visitor** | No selected demo identity. | View app shell, fetch a CSRF token, and use the demo identity picker. No employee data or kudos. |

**Demo limitation (explicit):** anyone using the demo can select the fictional administrator from the identity picker. This demonstrates role-based behaviour; it is **not** secure authentication. The UI must show a demo-mode warning and identify the administrator in the picker.

**Authorization source:** the acting user and role are always resolved on the server from the session's `user_id` and the current `users` row. A role supplied in a request body, query string, header, cookie, or client-side state is ignored.

---

## 5. User Stories

Priorities use MoSCoW. The project owner formally approved this document and DESIGN.md v0.2 on 2026-10-18. The stories below are the agreed specification.

| ID | User story | Priority |
|---|---|---|
| **US-01** | As a demo participant, I can choose which seeded employee I am acting as, so that I can use the app without a real login system. | Must (demo only) |
| **US-02** | As a signed-in employee, I can select a colleague from a list of active employees, so that I know who will receive my kudos. | Must |
| **US-03** | As a signed-in employee, I can write a short message of appreciation and submit it, so that my colleague receives public recognition. | Must |
| **US-04** | As a signed-in employee, I can view a public feed of recent kudos on the dashboard, so that I can see recognition across the company. | Must |
| **US-05** | As a signed-in employee, I can load older kudos beyond the first page, so that I can browse more of the feed. | Should |
| **US-06** | As a signed-in employee, I receive clear validation and error messages, so that I know why a submission failed and how to fix it. | Must |
| **US-07** | As a signed-in employee, I can use the app on a phone or desktop, so that the layout remains readable and usable. | Must |
| **US-08** | As a signed-in employee using a keyboard or assistive technology, I can complete the main tasks, so that the feature is accessible. | Should |
| **US-09** | **As an administrator, I want to hide or delete inappropriate kudos so that the employee feed remains appropriate.** | Must |

### US-09 Notes

- "Hide" is a reversible soft delete; "delete" is permanent.
- Administrators can see hidden kudos in the moderation view; ordinary employees cannot.
- Deleted kudos are gone for everyone, including administrators.
- The employee feed and its API responses contain only visible kudos.

---

## 6. Functional Requirements

| ID | Requirement | Priority | Traces to |
|---|---|---|---|
| **FR-01** | The app must show a demo identity picker when no demo session exists. Choosing a seeded, active user must create a server-side demo session and sign the user in. The picker must identify the administrator and the demo-mode limitation. | Must | US-01, US-09 |
| **FR-02** | The app must provide a "Switch user" action that clears the demo session and returns to the identity picker. | Must | US-01 |
| **FR-03** | The API must reject requests without a valid demo session with HTTP 401, except for `GET /api/health`, `GET /api/csrf`, and the demo identity endpoints. For unsafe methods (POST/PUT/PATCH/DELETE), CSRF validation is evaluated first; a missing or invalid token returns `403 CSRF_FAILED` even when no session exists. | Must | US-01, US-02, US-03, US-04, US-09 |
| **FR-04** | The colleague list must contain only active users, sorted case-insensitively by name, and must exclude the signed-in user in the composer UI. Administrators are also colleagues. | Must | US-02 |
| **FR-05** | The composer must contain a recipient selector, a plain-text message field, a live character counter, and a submit button. | Must | US-03 |
| **FR-06** | The server must derive the giver from the demo session. Any client-supplied giver identifier must be ignored. | Must | US-03 |
| **FR-07** | A valid submission must be stored in the database with giver, recipient, trimmed message, and a UTC creation timestamp. | Must | US-03 |
| **FR-08** | The server must validate all input as described in [Section 7](#7-validation-and-authorization-rules). Validation failures must create no database row and return structured field errors. | Must | US-03, US-06, US-09 |
| **FR-09** | After a successful submission, the UI must confirm success, clear the composer, and show the new kudos at the top of the feed without a full page reload. | Must | US-03, US-04 |
| **FR-10** | The employee feed must show only visible kudos, newest first, each with giver name, recipient name, message, and creation time. | Must | US-04, US-09 |
| **FR-11** | The employee feed must load at most 20 visible kudos per page by default, support a "Load more" action, and report whether more visible items exist. | Should | US-04, US-05, US-09 |
| **FR-12** | The UI must show distinct loading, empty, error, and success states, including moderation states. | Must | US-06, US-09 |
| **FR-13** | The layout must work from 320 px width upward without horizontal page scrolling. | Must | US-07 |
| **FR-14** | All interactive controls must be keyboard operable and have programmatic labels; errors, success messages, and confirmation dialogs must be accessible. | Should | US-08, US-09 |
| **FR-15** | User-generated message text must be rendered as text, never as HTML. | Must | US-03, US-04, US-09 |
| **FR-16** | Data and moderation state must persist across application restarts in a local database file. | Must | US-04, US-09 |
| **FR-17** | The app must expose a lightweight health endpoint for local checks. | Could | — |
| **FR-18** | The server must return consistent JSON error envelopes for API failures and log request metadata with a request ID, without logging message bodies. | Should | US-06 |
| **FR-19** | `users.role` must be `TEXT NOT NULL DEFAULT 'employee'` constrained to `'employee'` or `'admin'`. The demo must seed exactly one fictional administrator. | Must | US-09 |
| **FR-20** | An authenticated administrator must be able to list both visible and hidden kudos, with pagination and a current visibility indicator. Deleted kudos are not listed. | Must | US-09 |
| **FR-21** | An authenticated administrator must be able to hide a visible kudos (soft delete) and restore a hidden kudos. Both actions must be idempotent and must not change the kudos' original `created_at`. | Must | US-09 |
| **FR-22** | An authenticated administrator must be able to permanently delete a kudos after explicit UI confirmation. Deletion removes the row; it cannot be restored. | Must | US-09 |
| **FR-23** | Hidden kudos must be excluded from the employee feed and every employee-facing API response. Deleted kudos must be absent for all roles. Pagination and `hasMore` must be computed from the employee-visible set only. | Must | US-04, US-05, US-09 |
| **FR-24** | Every moderation endpoint must enforce administrator authorization on the server. The role must be read from the session's user ID and the current database row, never from client input. Ordinary employees must receive `403 FORBIDDEN` and no state change. | Must | US-09 |
| **FR-25** | Every state-changing request (demo login/logout, kudos creation, hide, restore, delete) must include a valid CSRF token in the `X-CSRF-Token` header. Missing or invalid tokens must return `403 CSRF_FAILED` with no state change. | Must | US-01, US-03, US-09 |
| **FR-26** | Creating, hiding, restoring, and deleting kudos must use non-GET HTTP methods. GET must be used only for reading data. Calling a state-changing route with GET must return `405 METHOD_NOT_ALLOWED`. | Must | US-03, US-09 |
| **FR-27** | Hiding, restoring, and deleting must be persisted. After an application restart, hidden kudos must remain hidden, restored kudos must remain visible, and deleted kudos must remain absent. | Must | US-09 |
| **FR-28** | The UI must render moderation controls only for administrators, including visibility status, Hide, Restore, and Delete actions. Delete must open a confirmation dialog showing the kudos excerpt; cancellation must send no request. | Must | US-09 |
| **FR-29** | The demo identity picker must include the fictional administrator, visibly marked. The UI, README, and specification must state that anyone can select the administrator and that this demonstrates role-based behaviour, not secure authentication. | Must | US-01, US-09 |
| **FR-30** | Administrators may moderate any kudos, including their own, because moderation is a role-based action distinct from author self-service. Authors still cannot edit or delete their own kudos through employee features. | Approved 2026-10-18 | US-09 |

---

## 7. Validation and Authorization Rules

These rules are **proposed** and must be confirmed during review, except where marked as accepted. The server is always authoritative; client-side checks are only for user experience.

### 7.1 Kudos Creation

| Field | Rule | On failure |
|---|---|---|
| `recipientId` | Required. Must be a JSON integer (booleans are rejected). Must reference an existing, active user. Must not equal the signed-in user. | `400 VALIDATION_ERROR` / `404 RECIPIENT_NOT_FOUND` / `400 SELF_KUDOS` |
| `message` | Required. Must be a string. Leading and trailing whitespace is trimmed; the trimmed value must be 1–500 Unicode code points. NUL and other control characters are rejected, except line feed and tab. Internal line breaks are preserved. | `400 VALIDATION_ERROR` with `fields.message` |
| Request body | Must be valid JSON with `Content-Type: application/json`. Body size is capped at 16 KB. | `400 INVALID_JSON` / `413 PAYLOAD_TOO_LARGE` |

### 7.2 Moderation

| Rule | Behaviour |
|---|---|
| **Authentication** | No valid demo session → `401 UNAUTHENTICATED`. |
| **Authorization** | Session user's database `role` must be `'admin'` → otherwise `403 FORBIDDEN`, no state change. |
| **Role source** | Only `users.role` for the session's `user_id` is used. Client-supplied `role`, `isAdmin`, or similar fields are ignored. |
| **Kudos identifier** | Path parameter must be a positive integer and reference an existing kudos. Missing or deleted → `404 KUDOS_NOT_FOUND`. |
| **Hide** | Set `is_visible = 0`. Idempotent: hiding an already hidden kudos returns success and leaves it hidden. |
| **Restore** | Set `is_visible = 1`. Idempotent: restoring a visible kudos returns success and leaves it visible. |
| **Delete** | Permanently remove the row. A repeat delete returns `404 KUDOS_NOT_FOUND`. The UI must require confirmation first. |
| **Visibility value** | Stored as `INTEGER NOT NULL DEFAULT 1`, constrained to `0` or `1`. API exposes it as a JSON boolean `isVisible` in admin responses. |
| **Created time** | Hide and restore must not modify `created_at`. Restored kudos return to their original chronological position. |
| **Admin list pagination** | `limit` default 20, range 1–50; `offset` ≥ 0; `visibility` one of `all` (default), `visible`, `hidden`. Invalid values → `400 VALIDATION_ERROR`. |
| **HTTP methods** | Hide and restore use `POST`; delete uses `DELETE`; listing uses `GET`. GET on a state-changing route → `405 METHOD_NOT_ALLOWED`. |

### 7.3 CSRF

| Rule | Behaviour |
|---|---|
| **Token issuance** | `GET /api/csrf` returns `{"csrfToken": "..."}` and ensures a per-session token exists. It is safe and may be called before sign-in. |
| **Token transport** | State-changing requests send `X-CSRF-Token: <token>`. |
| **Validation** | The server compares the header with the token stored in the signed session using a constant-time comparison. |
| **Failure** | Missing, empty, or mismatched token → `403 CSRF_FAILED`; no state change. |
| **Login rotation** | A successful demo login clears the old session and issues a new CSRF token in the response. The client must use the new token. |
| **Logout** | Logout clears the session; the client obtains a fresh token before the next sign-in. |
| **Scope** | Applies to `POST /api/demo/session`, `DELETE /api/demo/session`, `POST /api/kudos`, `POST /api/admin/kudos/{id}/hide`, `POST /api/admin/kudos/{id}/restore`, and `DELETE /api/admin/kudos/{id}`. |
| **GET safety** | All GET endpoints are read-only and must not change kudos or moderation state. |

### 7.4 Employee Feed Query Rules

- `GET /api/kudos` always applies `is_visible = 1`.
- Hidden rows never appear in employee responses, including when the client sends unexpected query parameters.
- `hasMore` and `nextOffset` are calculated from the visible result set.
- Deleted rows do not exist and therefore cannot appear.
- The admin list (`GET /api/admin/kudos`) is the only endpoint that returns hidden rows.

---

## 8. Acceptance Criteria

Each criterion is testable and uses Given/When/Then. Numbering is `AC-<story>-<n>`.

### US-01 — Choose a demo identity

- **AC-01-1:** Given no active demo session, when I open the app, then I see a list of seeded employees with names, departments, and role indicators, and no kudos feed.
- **AC-01-2:** Given the identity picker, when I choose an active employee, then the app signs me in as that employee, shows the dashboard, and `GET /api/me` returns the employee including their `role`.
- **AC-01-3:** Given I am signed in, when I reload the page, then I remain signed in as the same employee.
- **AC-01-4:** Given I am signed in, when I choose "Switch user", then my session is cleared and the identity picker returns.
- **AC-01-5:** Given no demo session, when I request a protected API endpoint with a safe method (GET), then the server returns HTTP 401 `UNAUTHENTICATED`. For an unsafe method, CSRF validation is evaluated first (see AC-03-11).
- **AC-01-6:** Given I submit a nonexistent or inactive user ID to the demo login endpoint with a valid CSRF token, then the server returns 404 and no session is created.
- **AC-01-7:** Given the identity picker, then exactly one seeded user is marked as an administrator.
- **AC-01-8:** Given I select the administrator, then the UI shows the moderation view and a demo-mode warning; the same would happen for any other person using the demo.

### US-02 — Select a colleague

- **AC-02-1:** Given I am signed in, when the composer loads, then the recipient selector lists active employees only, sorted by name.
- **AC-02-2:** Given I am signed in, then my own name does not appear as a selectable recipient.
- **AC-02-3:** Given there are no other active employees, then the composer displays an explanatory message and submission is disabled.
- **AC-02-4:** Given I do not choose a recipient and submit, then I see a field-level error and no kudos is created.

### US-03 — Write and submit kudos

- **AC-03-1:** Given a valid recipient, a valid message, and a valid CSRF token, when I submit, then the server returns 201, stores one kudos row, and identifies the giver from my session.
- **AC-03-2:** Given I enter leading/trailing whitespace, when the kudos is stored, then the stored message is trimmed.
- **AC-03-3:** Given I enter only whitespace, when I submit, then I see a validation error and no row is created.
- **AC-03-4:** Given I enter 501 characters, when I submit, then I see a validation error and no row is created.
- **AC-03-5:** Given I click Submit repeatedly while the request is in flight, then only one kudos is created.
- **AC-03-6:** Given I submit a message containing `<script>alert(1)</script>`, then it is stored as literal text and rendered as visible text, not executed.
- **AC-03-7:** Given the recipient is the signed-in user, then the server rejects the request with `SELF_KUDOS`.
- **AC-03-8:** Given the recipient does not exist or is inactive, then the server returns 404 `RECIPIENT_NOT_FOUND` and no row is created.
- **AC-03-9:** Given a client sends a `giverId` in the body, then the server ignores it and uses the session identity.
- **AC-03-10:** Given the submission succeeds, then the composer is cleared and the new kudos appears at the top of the feed without a full page reload.
- **AC-03-11:** Given a state-changing request without a valid CSRF token, then the server returns `403 CSRF_FAILED` and no row is created.

### US-04 — View the feed

- **AC-04-1:** Given at least one visible kudos exists, when I open the dashboard, then the feed shows the most recent 20 visible items, newest first.
- **AC-04-2:** Given a feed item, then it displays giver name, recipient name, message, and a human-readable creation time.
- **AC-04-3:** Given two visible kudos have the same timestamp, then the higher ID appears first.
- **AC-04-4:** Given no visible kudos exist, then the feed shows an empty state rather than an error.
- **AC-04-5:** Given long text or an unbroken string, then it wraps and does not cause horizontal page scrolling.
- **AC-04-6:** Given the feed request fails, then I see a retryable error message.
- **AC-04-7:** Given hidden kudos exist, then they do not appear in the employee feed or in any employee-facing API response.

### US-05 — Load older kudos

- **AC-05-1:** Given more than 20 visible kudos exist, when the first page loads, then the response reports `hasMore: true` and a `nextOffset`.
- **AC-05-2:** Given more visible items exist, when I choose "Load more", then the next 20 visible items are appended without removing existing items.
- **AC-05-3:** Given all visible items are loaded, then "Load more" is hidden and `hasMore` is false.
- **AC-05-4:** Given duplicate IDs appear across pages (caused by concurrent inserts), then the UI shows each kudos at most once.
- **AC-05-5:** Given `limit=0`, `limit=51`, `limit=abc`, or `offset=-1`, then the server returns 400 with a field error.
- **AC-05-6:** Given hidden kudos are interleaved between visible kudos, then pagination counts only visible items and `hasMore` is correct.

### US-06 — Understand errors and states

- **AC-06-1:** Given a validation failure, then the relevant field is marked invalid, an error message is shown, and focus moves appropriately.
- **AC-06-2:** Given a network failure, then a non-technical error message and a retry action are shown.
- **AC-06-3:** Given a protected request returns 401, then the UI returns to the identity picker with a session-expired notice.
- **AC-06-4:** Given a successful submission or moderation action, then a success message is announced politely to assistive technology.
- **AC-06-5:** Given an unexpected server error, then the UI shows a generic message and the API returns a request ID for support.
- **AC-06-6:** Given a CSRF failure, then the UI reports that the session security token expired and asks the user to retry, without automatically repeating the request.

### US-07 — Use on phone and desktop

- **AC-07-1:** At 320 px viewport width, the page has no horizontal scroll and all controls are usable.
- **AC-07-2:** At 320 px, 768 px, and 1280 px, the composer, feed, and moderation controls remain readable and reachable.
- **AC-07-3:** Touch targets for primary controls are at least 44 × 44 CSS pixels.
- **AC-07-4:** Input text is at least 16 px to avoid automatic zoom on mobile Safari.

### US-08 — Keyboard and assistive technology

- **AC-08-1:** I can choose an identity, select a recipient, type a message, submit, load more, and operate moderation controls using only the keyboard.
- **AC-08-2:** Every input has a programmatic label; the character counter and errors are associated with the message field.
- **AC-08-3:** Focus is always visible, and focus moves to the error summary or first invalid field after a failed submit.
- **AC-08-4:** Success and error messages use an appropriate `aria-live` region.
- **AC-08-5:** Text and background colours meet WCAG 2.1 AA contrast (4.5:1 for normal text).
- **AC-08-6:** The delete confirmation dialog is modal, traps focus, can be cancelled with Escape, and returns focus to the triggering control.

### US-09 — Content moderation

- **AC-09-1:** Given I am signed in as an administrator, then I can open a moderation view that lists both visible and hidden kudos, each marked with its visibility status.
- **AC-09-2:** Given I am signed in as an administrator and a kudos is visible, when I hide it, then `is_visible` becomes 0, the kudos disappears from the employee feed and all employee-facing API responses, and it remains listed as hidden in the moderation view.
- **AC-09-3:** Given I am signed in as an administrator and a kudos is hidden, when I restore it, then `is_visible` becomes 1, it reappears in the employee feed at its original chronological position, and its `created_at` is unchanged.
- **AC-09-4:** Given I am signed in as an administrator, when I choose Delete for a kudos and confirm in the dialog, then the request permanently removes the row, the kudos is absent from both the employee feed and the moderation view, and a repeat delete returns `404 KUDOS_NOT_FOUND`.
- **AC-09-5:** Given a kudos is hidden or deleted, then it does not appear in `GET /api/kudos`, in the employee feed UI, in any pagination metadata derived from the employee feed, or in any other employee-facing API response.
- **AC-09-6:** Given I am signed in as an ordinary employee, when I call any moderation endpoint directly (list hidden, hide, restore, or delete), then the server returns `403 FORBIDDEN` and no state changes.
- **AC-09-7:** Given a client supplies a role, `isAdmin` flag, or similar value in the body, query string, or headers, then the server ignores it; authorization depends only on the database role for the session user.
- **AC-09-8:** Given an administrator is demoted to employee in the database, then the next moderation request is rejected with `403 FORBIDDEN` without restarting the app.
- **AC-09-9:** Given moderation state changes, when the application is restarted, then hidden kudos remain hidden, restored kudos remain visible, and deleted kudos remain absent.
- **AC-09-10:** Given a moderation request without a valid CSRF token, then the server returns `403 CSRF_FAILED` and no state changes.
- **AC-09-11:** Given I send `GET` to a hide, restore, or delete route, then the server returns `405 METHOD_NOT_ALLOWED` and no state changes.
- **AC-09-12:** Given I am an administrator and a kudos is hidden, then the employee feed does not expose it even if I am the giver or recipient.
- **AC-09-13:** Given the moderation view is paginated, then it can list both visible and hidden kudos using `visibility=all` and filter to `visible` or `hidden`.
- **AC-09-14:** Given the demo identity picker, then the fictional administrator is visibly marked and selectable, and the UI states that identity selection is simulated.
- **AC-09-15:** Given an administrator moderates their own kudos, then the action succeeds under proposed rule FR-30; employee self-service still cannot edit or delete kudos.

---

## 9. Non-Functional Requirements

| ID | Requirement |
|---|---|
| **NFR-01 Security (demo)** | The demo must run locally only. Demo identity selection is not authentication; anyone can select the administrator. The app must state this in its UI and documentation. Passwords and real employee data must never be used. |
| **NFR-02 Security (production direction)** | A production version must use Datacom SSO/OIDC (or equivalent), server-side session validation, directory-derived roles, CSRF protection with rotation, rate limiting, HTTPS-only cookies, and dependency scanning. |
| **NFR-03 Privacy** | Only fictional seed data is used in the demo. Employee email addresses must not be exposed by the colleague API. Production needs a privacy review covering visibility, retention, and deletion. |
| **NFR-04 Performance** | With 1,000 kudos in the database, the first feed page should render in under 500 ms on a typical developer machine. Employee feed and admin list queries must use indexes and pagination. |
| **NFR-05 Persistence** | Submitted kudos and moderation state (hidden, restored, deleted) must survive application restarts. |
| **NFR-06 Reliability** | Invalid input must never crash the app or create partial rows. Each write is atomic. A failed moderation request must leave state unchanged. |
| **NFR-07 Accessibility** | WCAG 2.1 AA for the implemented screens, including keyboard use, labels, focus, contrast, live regions, and the confirmation dialog. |
| **NFR-08 Compatibility** | Latest two versions of Chrome, Firefox, Safari, and Edge on desktop; Safari and Chrome on iOS/Android for responsive checks. |
| **NFR-09 Maintainability** | Small, readable modules with plain SQL and no build step. A beginner should be able to follow a request from browser to database. |
| **NFR-10 Testability** | Validation, authorization, and CSRF are testable without a browser; API behaviour is testable with Flask's test client and an isolated temporary database. |
| **NFR-11 Observability** | Logs include timestamp, level, request ID, method, path, status, duration, current user ID, and moderation actions (actor ID, kudos ID, action). Message bodies, CSRF tokens, and secrets are not logged. |
| **NFR-12 Local operability** | The demo must start with documented commands on macOS, with no external services, containers, or database server required. |
| **NFR-13 Authorization** | Every moderation endpoint must enforce authorization server-side on every request. Roles are never cached in the browser session or trusted from client input. |
| **NFR-14 CSRF** | All unsafe HTTP methods must require a valid per-session CSRF token. GET requests must remain safe and side-effect free. |
| **NFR-15 Moderation integrity** | Hide/restore/delete must be atomic. Employee feed queries must filter hidden rows at the database level, not only in the UI. |

---

## 10. Assumptions

**All assumptions in this approved v0.2 specification are accepted.** The project owner formally approved REQUIREMENTS.md v0.2 and DESIGN.md v0.2 on 2026-10-18, including the items that were previously marked Proposed. Items described as production expectations remain outside the demo's scope.

| ID | Assumption | Type | Status | If wrong |
|---|---|---|---|---|
| **A-01** | This is a standalone app with no existing footprint. | Given by request | Accepted 2026-10-18 | Architecture and integration work change. |
| **A-02** | The app home page serves as the "main dashboard". | Given by request | Approved 2026-10-18 | If it must embed in a portal, an integration task is needed. |
| **A-03** | Demo users are fictional, seeded employees: 8 employees plus 1 administrator. | Demo assumption | Approved 2026-10-18 | Seed data and identity flow change. |
| **A-04** | Demo identity is chosen from a picker and stored in a signed session cookie; it is not real authentication. | Demo assumption | Accepted 2026-10-18 | A different demo login mechanism is needed. |
| **A-05** | Production authentication uses Datacom SSO/OIDC, with roles from directory groups. | Production expectation | Unconfirmed | Identity and admin design change. |
| **A-06** | The feed is available to demo users who have selected an identity, not anonymous visitors. | Product rule | Accepted 2026-10-18 | Feed authorisation changes. |
| **A-07** | Users cannot give kudos to themselves. | Product rule | Accepted 2026-10-18 | Remove self-exclusion and the server rule. |
| **A-08** | Messages are plain text, 1–500 characters after trimming. | Product rule | Accepted 2026-10-18 | Validation, counter, and DB constraints change. |
| **A-09** | "Recent" means newest first, 20 per page, with deterministic ordering (`created_at DESC, id DESC`). | Product rule | Accepted 2026-10-18 | Pagination defaults and UI change. |
| **A-10** | Authors cannot edit or delete their own kudos. Administrators can still moderate any kudos as a role-based action. | Product rule | Accepted 2026-10-18 | New employee endpoints, UI, and audit rules. |
| **A-11** | Kudos are always attributed; there are no anonymous kudos. | Product rule | Accepted 2026-10-18 | Data model and UI change. |
| **A-12** | No email or Teams notifications are sent. | Scope | Accepted 2026-10-18 | Integration work. |
| **A-13** | The demo UI is English-only. | Demo assumption | Approved 2026-10-18 | Localisation work. |
| **A-14** | Timestamps are stored in UTC and displayed in the viewer's local time. | Technical rule | Approved 2026-10-18 | Storage/display change. |
| **A-15** | Content moderation is specified in v0.2 as hide/restore and permanent delete, with role authorization and CSRF. | Product rule | Resolved in v0.2 | — |
| **A-16** | Modern evergreen browsers are the target. | Technical rule | Approved 2026-10-18 | Polyfills or a different frontend approach. |
| **A-17** | The demo is a single local instance, bound to `127.0.0.1`, with low volume. | Demo assumption | Accepted 2026-10-18 | Database and caching design change. |
| **A-18** | The role field has exactly two values, `employee` and `admin`; exactly one admin is seeded. | Product rule | Approved 2026-10-18 | Role model and seed change. |
| **A-19** | Administrators may moderate any kudos, including their own. | Product rule | Approved 2026-10-18 | Add an ownership restriction to moderation. |
| **A-20** | Moderation is hide/restore plus hard delete. No moderation reason, moderator identity, or moderation history is persisted; basic application logs are allowed. | Scope | Approved 2026-10-18 | Audit schema and UI change. |
| **A-21** | CSRF uses a per-session synchronizer token delivered by `GET /api/csrf` and sent in `X-CSRF-Token`. | Technical rule | Approved 2026-10-18 | Different CSRF mechanism. |
| **A-22** | Administrators are also employees and may give kudos. | Product rule | Approved 2026-10-18 | Separate admin-only account behaviour. |
| **A-23** | The moderation view appears as an admin-only panel on the same dashboard, not a separate admin site. | Demo assumption | Approved 2026-10-18 | New page/routing. |
| **A-24** | Hide and restore are idempotent; repeating either action succeeds without changing other fields. | Technical rule | Approved 2026-10-18 | Error responses for repeat actions. |

---

## 11. Open Questions

### 11.1 Resolved in v0.2

| ID | Question | Resolution |
|---|---|---|
| **OQ-01** | Who can moderate, and how? | Administrators via a role field; hide/restore and permanent delete. No audit system. |
| **OQ-02** | Can employees give kudos to themselves? | No (accepted A-07). |
| **OQ-03** | Can kudos be anonymous or private? | No (accepted A-11). |
| **OQ-04** | Can authors edit/delete their own kudos? | No; administrators moderate by role (accepted A-10). |
| **OQ-06** | Is the feed company-wide or team-scoped? | Available to all demo users with an identity (accepted A-06). |
| **OQ-10** | Are notifications required? | No (accepted A-12). |
| **OQ-12** | Is the Python/Flask/SQLite/vanilla stack approved? | Yes, accepted by the project owner on 2026-10-18. |
| **OQ-13** | Where will the demo be deployed? | Local only, bound to `127.0.0.1` (accepted A-17). |
| **OQ-15** | What defines an administrator? | `users.role = 'admin'`, one seeded fictional admin. |

### 11.2 Unresolved — Non-Blocking

These questions remain open but **do not block implementation** of the demo. The approved defaults below apply to this demo; production decisions remain future work.

| ID | Question | Approved demo default | Blocks implementation? |
|---|---|---|---|
| **OQ-05** | Which production identity provider and protocol will Datacom use? | SSO/OIDC (A-05) for production only. | No |
| **OQ-07** | What are the production retention, export, and deletion rules? | Indefinite retention for the demo; production policy TBD. | No |
| **OQ-08** | What production rate limits or duplicate detection are required? | None in the demo. | No |
| **OQ-09** | Is automated profanity filtering required? | No; manual admin moderation only. | No |
| **OQ-11** | What production scale is expected? | Low volume, single instance (A-17). | No |
| **OQ-14** | If a portal is introduced later, should the feed be embedded? | Standalone now. | No |
| **OQ-16** | Should administrators be able to moderate their own kudos? | Yes (A-19/FR-30). | No |
| **OQ-17** | Should moderation reasons or an audit trail be persisted? | No, explicitly out of scope (A-20). | No |

**No unresolved question blocks implementation.** This specification was approved for implementation on 2026-10-18.

---

## 12. Demo Assumptions vs Production Requirements

This table separates what the demo deliberately simulates from what a real Datacom deployment would need. **The demo must not be presented as production-ready.**

| Concern | Demo (this project) | Production requirement |
|---|---|---|
| **Identity** | Choose a seeded fictional user from a picker. | Corporate SSO/OIDC (or SAML), MFA, account lifecycle. |
| **Authentication proof** | Signed session cookie set after selecting a user. No password, no identity proof. | Verified identity token, server-side session, secure cookies, session expiry/revocation. |
| **Authorisation** | Role stored in SQLite; anyone can select the seeded admin. | Role-based access synced from directory groups; least privilege; admin actions audited. |
| **Administrator** | One fictional admin selectable by anyone in the demo. | Named administrators or an admin group; separation of duties. |
| **Moderation** | Hide/restore and hard delete; no persisted audit trail. | Full moderation workflow, reasons, audit trail, appeals, reporting. |
| **Users** | 9 fictional seed records. | Synced from the employee directory; leavers deactivated. |
| **Data** | Local SQLite file with fake data. | Managed database, backups, encryption at rest, disaster recovery. |
| **Abuse controls** | None beyond admin moderation. | Rate limiting, duplicate detection, spam controls, monitoring. |
| **CSRF** | Per-session synchronizer token; SameSite=Lax cookie. | Rotating tokens, origin checks, security review. |
| **Transport** | Local HTTP on `127.0.0.1`. | HTTPS only, HSTS, reverse proxy/WAF. |
| **Secrets** | Ephemeral development secret if not configured. | Managed secret store, rotation. |
| **Logging** | Console logs with request IDs and moderation action metadata; no message bodies. | Centralised structured logs, metrics, alerts, retention policy, immutable audit. |
| **Privacy** | Fictional data only. | Privacy impact assessment, lawful basis, retention and deletion policy. |
| **Availability** | Single local process. | Redundancy, health checks, monitoring, on-call. |
| **Accessibility** | WCAG 2.1 AA target for implemented screens. | Audited and maintained accessibility compliance. |

---

## 13. Dependencies and Constraints

- **Runtime (accepted 2026-10-18):** Python 3.9.6 is available; Flask and the standard-library `sqlite3` are the proposed implementation stack. Node.js is **not** installed.
- **Frontend (accepted 2026-10-18):** vanilla HTML/CSS/JavaScript, no build step.
- **Dependencies:** Runtime dependency is Flask only. Dev dependency is pytest only. See DESIGN.md for rationale.
- **Local only:** No external services, no cloud resources, no real employee data; bind to `127.0.0.1`.
- **Process history:** Step 2 prohibited implementation while the specification was reviewed. Step 3 began after the approval recorded below. Step 4 publishes the source repository; the application is not deployed.
- **Snapshots:** v0.1 and v0.2 are frozen under `snapshots/` and must not be edited. The current approved specification is v0.2.
- **Final deliverable:** The approved requirements and design are consolidated in [SPECIFICATION.md](SPECIFICATION.md).

---

## 14. Traceability Matrix

| Story | Functional requirements | Acceptance criteria |
|---|---|---|
| US-01 | FR-01, FR-02, FR-03, FR-29 | AC-01-1 … AC-01-8 |
| US-02 | FR-04, FR-05 | AC-02-1 … AC-02-4 |
| US-03 | FR-05, FR-06, FR-07, FR-08, FR-09, FR-15, FR-25, FR-26 | AC-03-1 … AC-03-11 |
| US-04 | FR-10, FR-12, FR-16, FR-23 | AC-04-1 … AC-04-7 |
| US-05 | FR-11, FR-12, FR-23 | AC-05-1 … AC-05-6 |
| US-06 | FR-08, FR-12, FR-18, FR-25 | AC-06-1 … AC-06-6 |
| US-07 | FR-13 | AC-07-1 … AC-07-4 |
| US-08 | FR-14, FR-28 | AC-08-1 … AC-08-6 |
| US-09 | FR-01, FR-03, FR-10, FR-16, FR-19 … FR-30 | AC-09-1 … AC-09-15 |

---

## 15. Review and Approval

**Approved on 2026-10-18.** The project owner gave this approval in the development conversation:

> I formally approve REQUIREMENTS.md and DESIGN.md v0.2 for implementation.
>
> I also accept the documented defaults:
> - Administrators may moderate kudos they sent.
> - Moderation audit fields are outside this demo's scope.
> - Hide and restore operations are idempotent.
> - The moderation panel appears on the same dashboard.

The approved material includes:

- [x] All assumptions in Section 10, including the items previously marked Proposed.
- [x] The moderation model: hide/restore plus permanent delete, with no persisted audit fields.
- [x] Administrators may moderate their own kudos (FR-30 / A-19).
- [x] The CSRF mechanism (`GET /api/csrf` + `X-CSRF-Token`) and token rotation at sign-in.
- [x] The v0.2 specification, with v0.1 preserved unchanged under `snapshots/v0.1/`.
- [x] Consolidation of the approved requirements and design into `SPECIFICATION.md`.
- [x] Implementation and validation before repository publication.

The v0.2 snapshot remains an unchanged record of the approved baseline taken immediately before implementation. [SPECIFICATION.md](SPECIFICATION.md) is the consolidated final specification.

---

## 16. Change Log

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-10-18 | AI development partner | Initial draft generated from the feature request; frozen in `snapshots/v0.1/`. |
| 0.2 | 2026-10-18 | AI development partner | Added US-09 and moderation acceptance criteria; added `users.role` and `kudos.is_visible`; added admin seed; added server-side authorization and CSRF; recorded accepted assumptions; explicitly excluded audit/reporting/automated moderation. |
| 1.0 | 2026-10-18 | Project owner and AI development partner | Formally approved v0.2; marked all retained assumptions and FR-30 as approved; recorded the approval statement; consolidated the approved requirements and design into `SPECIFICATION.md`. No requirements were changed after approval. |
