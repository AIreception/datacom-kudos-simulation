# Specification Snapshot — v0.1 (Initial Draft)

These are frozen copies of the Step 1 specification, taken on **2026-10-18 before content moderation was added**.

- `REQUIREMENTS.md` — initial requirements (no moderation; no `role` or `is_visible`).
- `DESIGN.md` — initial technical design (no moderation endpoints, no CSRF, no admin role).

**Do not edit these files.** They exist so the v0.2 changes can be reviewed with a diff.

The current, living specification is in the repository root:

- `../../REQUIREMENTS.md` (v0.2)
- `../../DESIGN.md` (v0.2)

To review what changed:

```bash
diff -u snapshots/v0.1/REQUIREMENTS.md REQUIREMENTS.md
diff -u snapshots/v0.1/DESIGN.md DESIGN.md
```
