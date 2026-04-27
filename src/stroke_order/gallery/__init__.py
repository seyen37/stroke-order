"""
stroke_order.gallery — 公眾分享庫 (Phase 5g)

Independent module. Self-contained: SQLite + filesystem upload store +
HMAC-signed magic-link auth. Touches the rest of the codebase only via
the FastAPI endpoint registrations in ``stroke_order.web.server``.

Submodules:

    config   — env-var-driven config (paths, secrets, dev mode)
    db       — SQLite schema + connection helper
    smtp     — magic-link email (with dev-mode console fallback)
    auth     — token sign/verify + session management (Phase 5g-3)
    service  — upload / list / delete business logic (Phase 5g-4)
"""
