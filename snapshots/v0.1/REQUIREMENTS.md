# Kudos System — Requirements

- **Status:** DRAFT v0.1 — awaiting review and explicit approval
- **Date:** 2026-10-18
- **Project:** Datacom Forage Task 2 — standalone Kudos demo
- **Related document:** [DESIGN.md](DESIGN.md)

> **Do not implement from this document yet.** This is the initial specification generated from the feature request. Items marked **Proposed** are recommendations, not approved requirements. Open questions must be resolved, and this document must be explicitly approved, before implementation starts.
>
> A later phase of Task 2 will add content moderation. It is intentionally **not specified** in this initial draft; see [OQ-01](#11-open-questions).

---

## 1. Purpose and Background

Datacom wants an internal way for employees to recognise each other. The feature lets a signed-in employee choose a colleague, write a short message of appreciation, submit it, and see recent recognition from across the company in a public feed on the dashboard.

This is a **new, standalone application**. No existing employee portal, user directory, authentication service, or dashboard is available to integrate with. The application's own home page acts as the "main dashboard" for the demo.

The demo must be small, locally runnable, and use persistent storage with minimal dependencies.

---

## 2. Scope

### 2.1 In Scope (Initial Demo)

- A locally runnable web application.
- Demo identity selection using seeded, fictional employees.
- A colleague list for choosing a recipient.
- A composer for a short, plain-text kudos message.
- Server-side validation and clear error feedback.
- Persistent storage that survives application restarts.
- A public, reverse-chronological feed of recent kudos.
- Pagination ("Load more") for older kudos.
- Responsive layout for mobile and desktop.
- Basic accessibility (keyboard, labels, focus, announcements).
- Automated tests for validation and API behaviour.

### 2.2 Out of Scope (This Draft)

The following are **not** requirements in this version. Some may be added later.

- Content moderation, admin roles, hiding or deleting kudos. **See OQ-01 — to be added in Task 2 Step 2.**
- Editing or deleting one's own kudos.
- Reactions, comments, likes, points, or leaderboards.
- Employee profiles or recognition histories.
- Notifications (email, Teams, Slack).
- Search, filtering, or sorting options in the feed.
- Anonymous or private kudos.
- Analytics and reporting.
- Real corporate authentication / SSO integration.
- Localisation / multi-language UI.
- Native mobile applications.
- Integration into an existing portal (none exists).

### 2.3 Product Boundary

| Item | Decision for this draft |
|---|---|
| Standalone app | Yes. One Flask application serves the page and the API. |
| "Main dashboard" | The application home page. |
| Storage | Local SQLite file (persistent across restarts). |
| Users | Seeded fictional employees for the demo. |
| Real employee data | Not used. |

---

## 3. Definitions

| Term | Meaning |
|---|---|
| **Kudos** | A short public message of appreciation from one employee to another. |
| **Giver** | The signed-in employee who submits the kudos. Derived from the server-side session, never from client input. |
| **Recipient** | The colleague selected to receive the kudos. |
| **Feed** | The reverse-chronological list of visible kudos shown on the home page. |
| **Demo user** | A fictional, seeded employee used to simulate sign-in. |
| **Demo session** | A signed browser cookie that records which demo user is currently acting. It is **not** real authentication. |
| **Active user** | A user with `is_active = 1`, eligible to appear in the colleague list and receive kudos. |
| **Character** | A Unicode code point, as counted by Python `len()` on a `str`. |

---

## 4. Users and Roles

| Role | Description | Available in this draft? |
|---|---|---|
| **Employee (demo user)** | Can choose a demo identity, view the feed, select a colleague, and submit kudos. | Yes |
| **Administrator** | Can moderate inappropriate kudos. | **No — not specified yet (OQ-01).** |
| **Anonymous visitor** | Can see the app shell and demo identity picker, but no employee data or kudos. | Yes, only for the demo identity picker |

No authorisation roles are modelled in this draft. Every signed-in demo user has the same permissions.

---

## 5. User Stories

Priorities use MoSCoW. All stories below are **proposed** until this document is approved.

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

### Known Gap: Content Moderation

There is currently **no user story** for hiding or deleting inappropriate kudos, handling spam, or resolving duplicate submissions. This is a known gap, recorded as **OQ-01**, and is expected to be added during Task 2 Step 2. It is not an approved requirement yet.

---

## 6. Functional Requirements

| ID | Requirement | Priority | Traces to |
|---|---|---|---|
| **FR-01** | The app must show a demo identity picker when no demo session exists. Choosing a seeded, active user must create a server-side demo session and sign the user in. | Must | US-01 |
| **FR-02** | The app must provide a "Switch user" action that clears the demo session and returns to the identity picker. | Must | US-01 |
| **FR-03** | The API must reject requests without a valid demo session with HTTP 401, except for `GET /api/health` and the demo identity endpoints. | Must | US-01, US-02, US-03, US-04 |
| **FR-04** | The colleague list must contain only active users, sorted case-insensitively by name, and must exclude the signed-in user in the composer UI. | Must | US-02 |
| **FR-05** | The composer must contain a recipient selector, a plain-text message field, a live character counter, and a submit button. | Must | US-03 |
| **FR-06** | The server must derive the giver from the demo session. Any client-supplied giver identifier must be ignored. | Must | US-03 |
| **FR-07** | A valid submission must be stored in the database with giver, recipient, trimmed message, and a UTC creation timestamp. | Must | US-03 |
| **FR-08** | The server must validate all input as described in [Section 7](#7-validation-rules). Validation failures must create no database row and return structured field errors. | Must | US-03, US-06 |
| **FR-09** | After a successful submission, the UI must confirm success, clear the composer, and show the new kudos at the top of the feed without a full page reload. | Must | US-03, US-04 |
| **FR-10** | The feed must show kudos newest first, each with giver name, recipient name, message, and creation time. | Must | US-04 |
| **FR-11** | The feed must load at most 20 kudos per page by default, support a "Load more" action, and report whether more items exist. | Should | US-04, US-05 |
| **FR-12** | The UI must show distinct loading, empty, error, and success states. | Must | US-06 |
| **FR-13** | The layout must work from 320 px width upward without horizontal page scrolling. | Must | US-07 |
| **FR-14** | All interactive controls must be keyboard operable and have programmatic labels; errors and success messages must be announced to assistive technology. | Should | US-08 |
| **FR-15** | User-generated message text must be rendered as text, never as HTML. | Must | US-03, US-04 |
| **FR-16** | Data must persist across application restarts in a local database file. | Must | US-04 |
| **FR-17** | The app must expose a lightweight health endpoint for local checks. | Could | — |
| **FR-18** | The server must return consistent JSON error envelopes for API failures and log request metadata with a request ID, without logging message bodies. | Should | US-06 |

---

## 7. Validation Rules

These rules are **proposed** and must be confirmed during review. The server is always authoritative; client-side checks are only for user experience.

| Field | Rule | On failure |
|---|---|---|
| `recipientId` | Required. Must be a JSON integer (booleans are rejected). Must reference an existing, active user. Must not equal the signed-in user (proposed rule A-07). | `400 VALIDATION_ERROR` / `404 RECIPIENT_NOT_FOUND` / `400 SELF_KUDOS` |
| `message` | Required. Must be a string. Leading and trailing whitespace is trimmed; the trimmed value must be 1–500 Unicode code points. NUL and other control characters are rejected, except line feed and tab. Internal line breaks are preserved. | `400 VALIDATION_ERROR` with `fields.message` |
| Request body | Must be valid JSON with `Content-Type: application/json`. Body size is capped (proposed: 16 KB). | `400 INVALID_JSON` / `413 PAYLOAD_TOO_LARGE` |
| `limit` (feed) | Optional integer, default 20, range 1–50. | `400 VALIDATION_ERROR` with `fields.limit` |
| `offset` (feed) | Optional integer, default 0, minimum 0. | `400 VALIDATION_ERROR` with `fields.offset` |
| `userId` (demo login) | Required integer referencing an existing, active demo user. | `400 VALIDATION_ERROR` / `404 USER_NOT_FOUND` |

**Message semantics (proposed):**

- The stored message is the trimmed original; HTML is not stripped or escaped in storage.
- The UI must render it with `textContent` and preserve line breaks visually.
- Emoji and other non-ASCII text are allowed.
- Whitespace-only messages are rejected.
- The database applies defensive constraints, but application validation is the source of truth.

---

## 8. Acceptance Criteria

Each criterion is testable and uses Given/When/Then. Numbering is `AC-<story>-<n>`.

### US-01 — Choose a demo identity

- **AC-01-1:** Given no active demo session, when I open the app, then I see a list of seeded employees with names and departments, and no kudos feed.
- **AC-01-2:** Given the identity picker, when I choose an active employee, then the app signs me in as that employee, shows the dashboard, and the API returns that employee from `GET /api/me`.
- **AC-01-3:** Given I am signed in, when I reload the page, then I remain signed in as the same employee.
- **AC-01-4:** Given I am signed in, when I choose "Switch user", then my session is cleared and the identity picker returns.
- **AC-01-5:** Given no demo session, when I request a protected API endpoint, then the server returns HTTP 401 `UNAUTHENTICATED`.
- **AC-01-6:** Given I submit a nonexistent or inactive user ID to the demo login endpoint, then the server returns 404 and no session is created.

### US-02 — Select a colleague

- **AC-02-1:** Given I am signed in, when the composer loads, then the recipient selector lists active employees only, sorted by name.
- **AC-02-2:** Given I am signed in, then my own name does not appear as a selectable recipient.
- **AC-02-3:** Given there are no other active employees, then the composer displays an explanatory message and submission is disabled.
- **AC-02-4:** Given I do not choose a recipient and submit, then I see a field-level error and no kudos is created.

### US-03 — Write and submit kudos

- **AC-03-1:** Given a valid recipient and a message of 1–500 characters, when I submit, then the server returns 201, stores one kudos row, and identifies the giver from my session.
- **AC-03-2:** Given I enter leading/trailing whitespace, when the kudos is stored, then the stored message is trimmed.
- **AC-03-3:** Given I enter only whitespace, when I submit, then I see a validation error and no row is created.
- **AC-03-4:** Given I enter 501 characters, when I submit, then I see a validation error and no row is created.
- **AC-03-5:** Given I click Submit repeatedly while the request is in flight, then only one kudos is created.
- **AC-03-6:** Given I submit a message containing `<script>alert(1)</script>`, then it is stored as literal text and rendered as visible text, not executed.
- **AC-03-7:** Given the recipient is the signed-in user, then the server rejects the request with `SELF_KUDOS` (proposed rule A-07).
- **AC-03-8:** Given the recipient does not exist or is inactive, then the server returns 404 `RECIPIENT_NOT_FOUND` and no row is created.
- **AC-03-9:** Given a client sends a `giverId` in the body, then the server ignores it and uses the session identity.
- **AC-03-10:** Given the submission succeeds, then the composer is cleared and the new kudos appears at the top of the feed without a full page reload.

### US-04 — View the feed

- **AC-04-1:** Given at least one kudos exists, when I open the dashboard, then the feed shows the most recent 20 items, newest first.
- **AC-04-2:** Given a feed item, then it displays giver name, recipient name, message, and a human-readable creation time.
- **AC-04-3:** Given two kudos have the same timestamp, then the higher ID appears first.
- **AC-04-4:** Given no kudos exist, then the feed shows an empty state rather than an error.
- **AC-04-5:** Given a long message or unbroken string, then it wraps and does not cause horizontal page scrolling.
- **AC-04-6:** Given the feed request fails, then I see a retryable error message.

### US-05 — Load older kudos

- **AC-05-1:** Given more than 20 kudos exist, when the first page loads, then the response reports `hasMore: true` and a `nextOffset`.
- **AC-05-2:** Given more items exist, when I choose "Load more", then the next 20 items are appended without removing existing items.
- **AC-05-3:** Given all items are loaded, then "Load more" is hidden and `hasMore` is false.
- **AC-05-4:** Given duplicate IDs appear across pages (caused by concurrent inserts), then the UI shows each kudos at most once.
- **AC-05-5:** Given `limit=0`, `limit=51`, `limit=abc`, or `offset=-1`, then the server returns 400 with a field error.

### US-06 — Understand errors and states

- **AC-06-1:** Given a validation failure, then the relevant field is marked invalid, an error message is shown, and focus moves appropriately.
- **AC-06-2:** Given a network failure, then a non-technical error message and a retry action are shown.
- **AC-06-3:** Given a protected request returns 401, then the UI returns to the identity picker with a session-expired notice.
- **AC-06-4:** Given a successful submission, then a success message is announced politely to assistive technology.
- **AC-06-5:** Given an unexpected server error, then the UI shows a generic message and the API returns a request ID for support.

### US-07 — Use on phone and desktop

- **AC-07-1:** At 320 px viewport width, the page has no horizontal scroll and all controls are usable.
- **AC-07-2:** At 320 px, 768 px, and 1280 px, the composer and feed remain readable and the submit button is reachable.
- **AC-07-3:** Touch targets for primary controls are at least 44 × 44 CSS pixels.
- **AC-07-4:** Input text is at least 16 px to avoid automatic zoom on mobile Safari.

### US-08 — Keyboard and assistive technology

- **AC-08-1:** I can choose an identity, select a recipient, type a message, submit, and load more using only the keyboard.
- **AC-08-2:** Every input has a programmatic label; the character counter and errors are associated with the message field.
- **AC-08-3:** Focus is always visible, and focus moves to the error summary or first invalid field after a failed submit.
- **AC-08-4:** Success and error messages use an appropriate `aria-live` region.
- **AC-08-5:** Text and background colours meet WCAG 2.1 AA contrast (4.5:1 for normal text).

---

## 9. Non-Functional Requirements

| ID | Requirement |
|---|---|
| **NFR-01 Security (demo)** | The demo must run locally only. Demo identity selection is not authentication; the app must state this in its own UI and documentation. Passwords and real employee data must never be used. |
| **NFR-02 Security (production direction)** | A production version must use Datacom SSO/OIDC (or equivalent), server-side session validation, role-based access, CSRF protection, rate limiting, HTTPS-only cookies, and dependency scanning. See [Section 10](#10-assumptions) and DESIGN.md. |
| **NFR-03 Privacy** | Only fictional seed data is used in the demo. Employee email addresses must not be exposed by the colleague API. Production needs a privacy review covering visibility, retention, and deletion. |
| **NFR-04 Performance** | With 1,000 kudos in the database, the first feed page should render in under 500 ms on a typical developer machine. Feed queries must use an index and pagination. |
| **NFR-05 Persistence** | Submitted kudos must still exist after the application process is stopped and restarted. |
| **NFR-06 Reliability** | Invalid input must never crash the app or create partial rows. Each write is atomic. |
| **NFR-07 Accessibility** | WCAG 2.1 AA for the implemented screens, including keyboard use, labels, focus, contrast, and live regions. |
| **NFR-08 Compatibility** | Latest two versions of Chrome, Firefox, Safari, and Edge on desktop; Safari and Chrome on iOS/Android for responsive checks. |
| **NFR-09 Maintainability** | Small, readable modules with plain SQL and no build step. A beginner should be able to follow a request from browser to database. |
| **NFR-10 Testability** | Validation is unit-testable without HTTP; API behaviour is testable with Flask's test client and an isolated temporary database. |
| **NFR-11 Observability** | Logs include timestamp, level, request ID, method, path, status, duration, and current user ID. Message bodies and secrets are not logged. |
| **NFR-12 Local operability** | The demo must start with documented commands on macOS, with no external services, containers, or database server required. |

---

## 10. Assumptions

**None of the following are approved requirements.** "Given" items come from the brief; "Proposed" items need your confirmation; "Production expectation" items describe the eventual system, not the demo.

| ID | Assumption | Type | Status | If wrong |
|---|---|---|---|---|
| **A-01** | This is a standalone app with no existing footprint. | Given by request | Confirmed by brief | Architecture and integration work change. |
| **A-02** | The app home page serves as the "main dashboard". | Given by request | Proposed interpretation | If it must embed in a portal, an integration task is needed. |
| **A-03** | Demo users are 8 fictional, seeded employees. | Demo assumption | Proposed | Seed data and identity flow change. |
| **A-04** | Demo identity is chosen from a picker and stored in a signed session cookie; it is not real authentication. | Demo assumption | Proposed | A different demo login mechanism is needed. |
| **A-05** | Production authentication uses Datacom SSO/OIDC, with roles from directory groups. | Production expectation | Unconfirmed | Identity and admin design change. |
| **A-06** | All signed-in employees can read the whole company feed; anonymous visitors cannot. | Proposed product rule | Needs confirmation | Feed authorisation and query scoping change. |
| **A-07** | Users cannot give kudos to themselves. | Proposed product rule | Needs confirmation | Remove self-exclusion and the server rule. |
| **A-08** | Messages are plain text, 1–500 characters after trimming. | Proposed product rule | Needs confirmation | Validation, counter, and DB constraints change. |
| **A-09** | "Recent" means newest first, 20 per page. | Proposed product rule | Needs confirmation | Pagination defaults and UI change. |
| **A-10** | Authors cannot edit or delete their own kudos in this version. | Proposed scope | Needs confirmation | New endpoints, UI, and audit rules. |
| **A-11** | Kudos are always attributed; there are no anonymous kudos. | Proposed product rule | Needs confirmation | Data model and UI change. |
| **A-12** | No notifications are sent when kudos are created. | Proposed scope | Needs confirmation | Integration work (email/Teams/Slack). |
| **A-13** | The demo UI is English-only. | Demo assumption | Proposed | Localisation work. |
| **A-14** | Timestamps are stored in UTC and displayed in the viewer's local time. | Proposed technical rule | Needs confirmation | Storage/display change. |
| **A-15** | Content moderation (hide/delete, spam, duplicates) is out of scope for this draft. | Known gap | Pending Step 2 | Final spec is incomplete until added. |
| **A-16** | Modern evergreen browsers are the target. | Proposed technical rule | Needs confirmation | Polyfills or different frontend approach. |
| **A-17** | The demo is a single local instance with low volume. | Demo assumption | Given by "locally runnable" | Database and caching design change. |

---

## 11. Open Questions

| ID | Question | Why it matters | Proposed default in this draft | Blocks implementation? |
|---|---|---|---|---|
| **OQ-01** | Who can moderate kudos, and how? Should kudos be hidden (soft delete) or permanently deleted? What audit fields and reasons are required? How are spam and duplicate submissions handled? | Required by Task 2 Step 2 and by the specification checklist. | **Not designed yet.** Do not implement. Add to this document and DESIGN.md before approval. | **Yes** (for the final spec) |
| **OQ-02** | Can employees give kudos to themselves? | Affects validation, recipient list, and DB constraint. | Disallowed (A-07). | No |
| **OQ-03** | Can kudos be anonymous or private? | Changes attribution, visibility, and data model. | No (A-11). | No |
| **OQ-04** | Can authors edit or delete their own kudos? | Adds endpoints, UI, and audit requirements. | No (A-10). | No |
| **OQ-05** | Which production identity provider and protocol will Datacom use? | Determines the production auth design. | SSO/OIDC (A-05). | No for demo, yes for production |
| **OQ-06** | Is the feed company-wide or limited to a team/department? | Changes query scoping and privacy. | Company-wide (A-06). | No |
| **OQ-07** | What are the retention, export, and deletion rules for kudos? | Privacy and compliance obligations. | Indefinite retention for the demo; production policy TBD. | No for demo |
| **OQ-08** | What rate limits, duplicate detection, or spam controls are required? | Prevents abuse and duplicate posts. | None in the demo; production limits to be defined. | No (moderation-related) |
| **OQ-09** | Is automated profanity filtering required, or only human moderation? | Affects moderation design and third-party dependencies. | Human moderation only, to be specified in Step 2. | No |
| **OQ-10** | Should recipients or admins be notified? | Integration scope. | No notifications (A-12). | No |
| **OQ-11** | What user and kudos volumes are expected? | Database and caching choices. | Low volume, single instance (A-17). | No |
| **OQ-12** | Is the proposed Python/Flask/SQLite stack approved? | Determines all implementation tasks. | Proposed in DESIGN.md. | **Yes** |
| **OQ-13** | Where will the final system be deployed? | Affects packaging, TLS, database, and operations. | Local demo only for now. | No for demo |
| **OQ-14** | If a portal is introduced later, should the feed be embedded or remain standalone? | Future architecture. | Standalone now. | No |
| **OQ-15** | What exactly defines an "administrator" in production? | Required for moderation authorisation. | Not modelled yet. | Yes (with OQ-01) |

---

## 12. Demo Assumptions vs Production Requirements

This table separates what the demo deliberately simulates from what a real Datacom deployment would need. **The demo must not be presented as production-ready.**

| Concern | Demo (this project) | Production requirement |
|---|---|---|
| **Identity** | Choose a seeded fictional user from a picker. | Corporate SSO/OIDC (or SAML), MFA, account lifecycle. |
| **Authentication proof** | Signed session cookie set after selecting a user. No password, no identity proof. | Verified identity token, server-side session, secure cookies, session expiry/revocation. |
| **Authorisation** | All signed-in users have identical permissions. | Role-based access; admin/moderation role; least privilege. |
| **Users** | 8 fictional seed records. | Synced from the employee directory; leavers deactivated. |
| **Data** | Local SQLite file with fake data. | Managed database, backups, encryption at rest, disaster recovery. |
| **Moderation** | None (to be specified in Step 2). | Hide/delete workflow, audit trail, reasons, appeals, abuse reporting. |
| **Abuse controls** | None. | Rate limiting, duplicate detection, spam controls, monitoring. |
| **Transport** | Local HTTP on `127.0.0.1`. | HTTPS only, HSTS, reverse proxy/WAF. |
| **CSRF** | SameSite=Lax cookie + JSON requests. | CSRF tokens, origin checks, security review. |
| **Secrets** | Ephemeral development secret if not configured. | Managed secret store, rotation. |
| **Logging** | Console logs with request IDs; no message bodies. | Centralised structured logs, metrics, alerts, retention policy. |
| **Privacy** | Fictional data only. | Privacy impact assessment, lawful basis, retention and deletion policy. |
| **Availability** | Single local process. | Redundancy, health checks, monitoring, on-call. |
| **Accessibility** | WCAG 2.1 AA target for implemented screens. | Audited and maintained accessibility compliance. |

---

## 13. Dependencies and Constraints

- **Runtime:** Python 3.9.6 is available on this machine. Node.js is **not** installed.
- **Storage:** SQLite via Python's standard library; no database server.
- **Dependencies:** Proposed runtime dependency is Flask only. Dev dependency is pytest only. See DESIGN.md for rationale.
- **Local only:** No external services, no cloud resources, no real employee data.
- **No build step:** Vanilla HTML/CSS/JavaScript.
- **Task 2 Step 1 constraint:** No code, no dependency installation, no Git initialisation, and no remote repository at this stage.
- **Final deliverable:** After approval and implementation, requirements and design will be consolidated into `SPECIFICATION.md` as required by Task 2 Step 4.

---

## 14. Traceability Matrix

| Story | Functional requirements | Acceptance criteria |
|---|---|---|
| US-01 | FR-01, FR-02, FR-03 | AC-01-1 … AC-01-6 |
| US-02 | FR-04, FR-05 | AC-02-1 … AC-02-4 |
| US-03 | FR-05, FR-06, FR-07, FR-08, FR-09, FR-15 | AC-03-1 … AC-03-10 |
| US-04 | FR-10, FR-12, FR-16 | AC-04-1 … AC-04-6 |
| US-05 | FR-11, FR-12 | AC-05-1 … AC-05-5 |
| US-06 | FR-08, FR-12, FR-18 | AC-06-1 … AC-06-5 |
| US-07 | FR-13 | AC-07-1 … AC-07-4 |
| US-08 | FR-14 | AC-08-1 … AC-08-5 |

---

## 15. Review and Approval

This document is **not approved**. Before implementation, please:

- [ ] Confirm or change assumptions A-02 … A-17.
- [ ] Answer open questions OQ-02 … OQ-12 (OQ-01 and OQ-15 are required for the final spec).
- [ ] Add the content-moderation user story and edge cases (Task 2 Step 2).
- [ ] Update DESIGN.md with moderation fields and endpoints (Task 2 Step 2).
- [ ] Confirm the proposed stack and architecture.
- [ ] Give explicit written approval to begin implementation.

**Approval statement format (to be provided by the project owner):**

> I approve REQUIREMENTS.md v0.1 and DESIGN.md v0.1, including the agreed changes listed in this review, and authorise implementation.

Until that statement is given, no application code, dependency installation, or Git operations will occur.

---

## 16. Change Log

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-10-18 | AI development partner | Initial draft generated from the feature request, for review. |
