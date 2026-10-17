# Antier Healthcare Suite (Sandbox)

Stack: Next.js · FastAPI · PostgreSQL + pgvector · Celery + Redis · OpenAI · MinIO · Docker Compose.

## Run
    cp .env.example .env          # add OPENAI_API_KEY (and SMTP_* for real email)
    docker compose up -d --build  # web :3010, api :8010, minio console :9011
    # seed runs automatically on first start; rebuild any time with:
    docker compose exec api python -m app.seed

Local dev: `backend/.venv/bin/uvicorn app.main:app --port 8010` and `cd web && npm run dev`.

Sign in at http://localhost:3010 (all users share the password `Sandbox@2026`, e.g. `quality.manager@hospital.example`).

## Built (Foundation + Module 1)
Auth/reset, roles and department scoping, Settings (branding, departments, questions, themes, SLA, routing, KPIs, escalation, privacy),
notification centre + email log/SMTP, audit trail (filter, before/after, CSV), HIS event console + WhatsApp phone preview,
bilingual patient form (RTL), AI feedback analysis, routing rule, inbox, cases with SLA/escalation (Celery beat), dashboard, global search, reset sandbox data.

## Not built yet
Incidents, audits, accreditation, documents, risks, reports/exports, Assistant, Enquiries, CSV import, Help centre, evidence uploads (MinIO wired in compose only).

## AI
`backend/app/ai/adapter.py` is the single provider adapter. Without `OPENAI_API_KEY` a keyword-based offline analyser keeps the app usable
(Arabic translation is then unavailable). Invalid or failed model output falls back to "Needs review".
