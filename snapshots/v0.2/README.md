# Specification Snapshot — v0.2 (Approved)

These are frozen copies of the **approved** specification, taken on **2026-10-18 immediately before implementation began**.

- `REQUIREMENTS.md` — approved requirements, including content moderation, roles, server-side authorization, and CSRF.
- `DESIGN.md` — approved technical design for the same version.

**Do not edit these files.** They are the reference for checking that the implementation matches what was approved. The living copies remain in the repository root:

- `../../REQUIREMENTS.md`
- `../../DESIGN.md`

To compare the approved baseline with the current living documents:

```bash
diff -u snapshots/v0.2/REQUIREMENTS.md REQUIREMENTS.md
diff -u snapshots/v0.2/DESIGN.md DESIGN.md
```

To compare the initial draft with the approved version:

```bash
diff -u snapshots/v0.1/REQUIREMENTS.md snapshots/v0.2/REQUIREMENTS.md
diff -u snapshots/v0.1/DESIGN.md snapshots/v0.2/DESIGN.md
```
