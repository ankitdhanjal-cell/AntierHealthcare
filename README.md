# Antier Healthcare Suite (Sandbox)

Patient-experience and quality-management platform for hospitals. Patients give feedback through a short bilingual (English/Arabic) form reached by WhatsApp, SMS or a ward QR code. AI tags the comment, happy patients are invited to leave a Google review, and everyone else becomes an SLA-tracked case with a call-back. The quality module covers incidents with corrective actions, infection-control audits, accreditation readiness with mock surveys, quality indicators with run charts, and a monthly committee pack as PDF. Every action is audited.

**Stack:** Next.js 14 · FastAPI · PostgreSQL · Celery + Redis · OpenAI · Docker Compose.

## Quick start

### Docker
```bash
cp .env.example .env          # optionally add OPENAI_API_KEY and SMTP_*
docker compose up -d --build
```
| Service | URL / port |
|---|---|
| Web | http://localhost:3010 |
| API (docs at `/docs`) | http://localhost:8010 |
| PostgreSQL | localhost:5442 |
| Redis | localhost:6389 |

The API container seeds demo data on first start. Rebuild it any time:
```bash
docker compose exec api python -m app.seed
```

### Without Docker
Requires python3, node 20+ and `redis-server`.
```bash
./run-local.sh     # embedded Postgres, Redis, API :8010, Celery worker, web :3010
./stop-local.sh
```
Logs and data live in `~/.ahs-local`.

### Manual dev
```bash
cd backend && .venv/bin/uvicorn app.main:app --port 8010
cd backend && .venv/bin/celery -A app.celery_app worker --beat --loglevel=info
cd web && npm run dev          # http://localhost:3010
```

### Sign in
All demo users share the password `Sandbox@2026`.

| Email | Role |
|---|---|
| quality.manager@hospital.example | Quality Manager (sees all departments) |
| patient.relations@hospital.example | Patient Relations Officer (sees all) |
| dept.head@hospital.example | Department Head (OPD, Emergency only) |
| infection.control@hospital.example | Infection Control Nurse |
| front.desk@hospital.example | Front desk |
| staff@hospital.example | Staff reporter (cases only) |
| management@hospital.example | Management viewer (read-only) |
| admin@hospital.example | Admin (full access) |

## Configuration (`.env`)
| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY`, `OPENAI_MODEL` | AI analysis (default `gpt-4o-mini`). Empty key uses the offline keyword analyser. |
| `JWT_SECRET` | Signs login and reset tokens. **Change it outside the sandbox.** |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Real email. Empty host means emails are only logged (see `/api/emails`). |
| `PUBLIC_WEB_URL` | Base URL used in emailed and WhatsApp links. |

`DATABASE_URL` and `REDIS_URL` default to the local Docker ports and are overridden by `docker-compose.yml`.

## Project layout
```
backend/
  app/
    main.py            FastAPI app, mounts routers, /api/health
    config.py          env-driven settings
    db.py              engine, session, get_db
    models.py          all SQLAlchemy tables
    security.py        JWT, bcrypt, require(module, action), dept_scope
    services.py        settings, email, notifications, open_case, SLA check
    audit.py           audit.log()
    defaults.py        default settings, roles, departments
    seed.py            rebuild DB with demo data (--if-empty to skip)
    celery_app.py      beat schedule and tasks
    routers/           auth · admin · feedback · cases · incidents · accreditation · actions · audits ·
                       indicators · reports · home (tasks, role homes) · analytics (NPS, funnel) · channels (QR) · misc · public
    committee_pack.py  monthly committee PDF (ReportLab)
    indicators_calc.py indicator values, run chart median and shift rule
    seed_*.py          sample data: feedback and cases, incidents, standards, audits, indicators
    seed_data/         texts and standards as JSON (committed, no API key needed to seed)
    ai/                adapter.py (provider) · feedback.py (prompt, schema, offline fallback)
    connectors/        sandbox.py (simulated HIS, WhatsApp and SMS)
  data/evidence/       evidence files and audit photos (created at runtime, not in git)
  tests/               pytest suite (needs a throwaway database, see Tests)
  local_db.py          starts embedded Postgres for run-local.sh
web/
  app/                 Next.js routes: login, forgot, reset, f/[token] (patient form), (app)/… (signed-in pages)
  components/          Providers (toast, confirm), Shell (layout, nav, search, notifications), ui (useFetch, atoms)
  lib/                 api.ts (fetch wrapper), i18n.ts (patient-form strings)
docker-compose.yml     db, redis, api, worker, web
```

## How it works
1. **Discharge** on `/admin/integrations` (simulated HL7 ADT^A03) creates a feedback request with a one-time token.
2. **WhatsApp** message with `/f/<token>` is sent immediately or after the configured delay (Celery).
3. **Patient form** is public. Submitting calls `ai.feedback.analyse`, which returns sentiment, themes, urgency, English translation, summary and suggested department. Failures fall back to "Needs review".
4. **Routing rule** (Settings): rating at or above the threshold with positive sentiment shows a Google review invitation. Anything else opens a case.
5. **Case** gets a number (`CS-1001…`), an owner (department head, else Patient Relations) and a due time from the SLA setting (high 24h, medium 72h, low 168h).
6. **SLA check** runs every 60 seconds and escalates overdue cases to the Quality Manager once.
7. Staff work cases, review AI tags, and watch the dashboard. All changes appear in the audit trail with before/after values.

## Access control
Each role maps modules (`feedback`, `cases`, `settings`, `users`, `audit`, `integrations`, `dashboard`) to actions (`view`, `create`, `approve`, `admin`). Roles that do not see all departments only get records for their own departments.

## API overview
All routes are under `/api`. Interactive docs: `http://localhost:8010/docs`.

| Area | Routes |
|---|---|
| Auth | `POST /auth/login`, `GET /auth/me`, `GET /auth/branding`, `POST /auth/forgot`, `/auth/reset`, `/auth/change-password`, `PUT /auth/profile` |
| Public form | `GET/POST /public/feedback/{token}`, `POST /public/feedback/{token}/google-click` |
| Feedback | `GET /feedback`, `GET /feedback/{id}`, `PUT /feedback/{id}/tags`, `POST /feedback/{id}/open-case`, `POST /feedback/bulk-review`, `GET /feedback/review-requests` |
| Incidents | `GET/POST /incidents`, `GET /incidents/{id}`, `PUT /incidents/{id}/triage`, `/investigation`, `POST /incidents/{id}/facts`, `/capas`, `/escalate`, `/status`, `PUT /incidents/capas/{id}`, `GET /incidents/capas`, `POST /incidents/ai-suggest`, `POST /cases/{id}/raise-incident` |
| Quality | `/accreditation/*` (summary, chapters, elements, evidence, tracers), `/audits/*` (templates, schedule, runs, compliance), `/indicators/*` (dictionary, values, entry, pareto), `/actions`, `/reports/committee/{month}` and `/pdf`, `/tasks`, `/home` |
| Patient experience | `/analytics/nps`, `/analytics/funnel`, `/feedback/compliments`, `/channels` and `/channels/{id}/qr.svg`, `/public/channel/{token}`, `/public/preview/{lang}`, `POST /cases/{id}/closing-message` |
| Cases | `GET /cases`, `GET /cases/{id}`, `POST /cases/{id}/assign`, `/status`, `/notes`, `POST /cases/bulk` |
| Admin | `/settings/{key}`, `/organisation`, `/departments`, `/users`, `/roles` |
| Other | `/notifications`, `/emails`, `/audit`, `/audit/export`, `/integrations`, `/integrations/his/*`, `/whatsapp/messages`, `/search`, `/dashboard`, `POST /admin/reset-sandbox`, `GET /health` |

## AI
`backend/app/ai/adapter.py` is the single provider adapter. Without `OPENAI_API_KEY`, a bilingual keyword analyser keeps the app usable, but Arabic translation is unavailable. Invalid model output is rejected and falls back to "Needs review". AI results are suggestions only: staff accept or edit them, and the audit trail keeps both.

## Built
**Quality module** (sidebar group Quality): incidents with triage, investigation, CAPA and effectiveness checks; accreditation readiness with evidence upload, one-click evidence from closed actions and audits, countdown and mock survey mode; audit templates, scheduling, mobile audit screen with photos, compliance by ward against target; indicator dictionary with definitions, numerators and denominators, monthly entry, run charts with median and shift rule, Pareto charts; monthly Quality and Patient Safety Committee pack as a branded PDF; actions register; role-based home pages and a My tasks list.

**Patient experience**: NPS by department and doctor, compliments list that can be shared with department heads, review funnel, call-back log with loop-closed status and optional closing message, printable QR codes per ward and clinic, SMS fallback, a side-by-side preview of what the patient sees in English and Arabic, CSV export and print on lists, Arabic menu toggle, help centre.

Incident management (Quality → Incidents): 60-second report form with anonymous option and AI category/harm suggestion, triage queue, investigation workspace (timeline, contributing factors, 5 Whys, root cause), corrective and preventive actions with effectiveness checks, serious-event escalation, similar-incident lookup, and one-click raise from a complaint case. Auth and password reset, roles with department scoping, settings (branding, departments, questions, themes, SLA, routing, KPIs, escalation, privacy), notification centre, email log, audit trail with CSV export, HIS event console with WhatsApp phone preview, bilingual patient form (RTL), AI feedback analysis, routing rule, inbox, cases with SLA and escalation, dashboard, global search, reset sandbox data.

## Not built yet
Documents, risks, Assistant, enquiries, CSV import. Staff screens are English only (the header toggle translates the menu); patient-facing screens are fully bilingual. The accreditation standards are a generic sample set: load your programme's own standards before a real survey.

## Tests
```bash
cd backend && pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+psycopg2://…/ahs_test pytest   # use a throwaway database, tests rebuild it
```

## Notes
- After pulling schema changes, `./run-local.sh` rebuilds the sandbox data automatically when the database is out of date; with Docker run `docker compose exec api python -m app.seed`.
- This is a sandbox. Before real use: set a strong `JWT_SECRET`, restrict CORS in `main.py`, replace the shared demo password, and add login rate limiting.
- `POST /admin/reset-sandbox` drops and reseeds every table. There are no migrations; schema changes are applied by reseeding.
- Evidence files and audit photos are stored under `backend/data/evidence` (a Docker volume in Compose). Tests use a temporary folder instead.
- Product requirements are in `Antier_Healthcare_Suite_Product_Build_Spec.pdf`.
