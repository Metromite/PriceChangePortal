# DispatchOPS — Cloudflare Hosting Migration Status

## Objective

Host DispatchOPS at a permanent public URL so multiple colleagues can use the same live application and the same central Neon PostgreSQL database, without relying on the user's PC being online.

The hard constraint is a genuinely free/ongoing solution, not a 30-day trial, not a platform that sleeps after inactivity, and not Railway's trial credits.

## Decision

Cloudflare Workers is the preferred target for the free/always-available requirement. The current Workers Free plan provides 100,000 requests/day and 10 ms CPU per request; Hyperdrive is available on the Free plan with 100,000 database queries/day. Cloudflare Workers do not use the traditional always-running server/sleep model. See the official Cloudflare pricing/limits documentation before deployment because limits can change.

Neon remains the database. Cloudflare officially supports connecting Workers to Neon through Hyperdrive.

## Important repository findings

The current application is a full FastAPI + React application, not a small static website.

Backend currently depends on:

- FastAPI 0.115.0
- Uvicorn
- SQLAlchemy 2.0.35
- psycopg2-binary 2.9.9
- Pydantic / pydantic-settings
- JWT/passlib/bcrypt authentication components
- Alembic migrations
- Pandas
- OpenPyXL
- PyYAML
- RapidFuzz
- multipart uploads

The frontend is React 18 + Vite + TypeScript and calls the API through `/api`.

The existing Dockerfile builds the React frontend and serves the resulting static files from the FastAPI process.

## Why we must not pretend the current Dockerfile can simply be deployed to free Cloudflare Workers

The current Dockerfile is a normal Linux container. Cloudflare Containers are currently a Workers Paid feature, so they do NOT satisfy the user's totally-free requirement.

The current FastAPI application also assumes:

1. A normal Python process/OS runtime.
2. SQLAlchemy connecting through psycopg2 to PostgreSQL.
3. Local filesystem directories for imports, exports and backups.
4. Background Python threads for jobs.
5. Long-lived Server-Sent Event job streams.

Those assumptions need adaptation for Workers.

## Current database layer

`backend/app/core/database.py` creates a SQLAlchemy engine from `DATABASE_URL` and uses a normal synchronous PostgreSQL driver. This is the main architectural compatibility point that must be handled before production deployment to Workers.

Cloudflare's official Neon/Hyperdrive examples use a JavaScript PostgreSQL driver such as `pg`. Hyperdrive provides a Worker-side database binding and connection pooling.

Do NOT put the user's Neon password or connection string into Git. Use Cloudflare secrets/bindings.

## Current filesystem usage

The import endpoints write uploaded SAP/Landmark files to `IMPORT_FOLDER` using Python `open()` and `shutil.copyfileobj()`. Generated exports and backups also use filesystem paths.

For a serverless Worker deployment, persistent user files should move to Cloudflare R2 (or another persistent object store). Temporary per-request data must remain in memory or temporary runtime-supported storage only.

## Current background jobs

`backend/app/services/jobs.py` starts a Python `threading.Thread` for every job and records progress in PostgreSQL.

This cannot be treated as a normal persistent worker queue on Cloudflare Workers. The migration should replace this with Cloudflare-native asynchronous execution (Workers Workflows/Queues where appropriate) or a request-streaming design where practical.

## Current frontend

The frontend already uses `/api` as its API base, which is good for a same-origin Cloudflare deployment. Avoid changing this unless the final architecture requires a separate API origin.

## What is already done

- Repository is public: `Metromite/DispatchOPS`.
- Neon PostgreSQL database was created.
- The repository has been cloned and the current backend dependencies install successfully on Windows/Python 3.12.
- A safe Git branch named `cloudflare-migration` exists. The production `main` branch has not been replaced by this migration.
- The current codebase has been inspected for deployment architecture.

## What is NOT done yet

- Cloudflare account-side setup.
- Hyperdrive configuration pointing at the Neon database.
- Cloudflare Worker deployment.
- Persistent object storage migration for uploaded/exported files.
- Background-job migration.
- Production authentication decision (the current source has AUTH_DISABLED=True as a temporary development state).
- End-to-end production testing.

## Required final architecture

Browser
  -> Cloudflare Worker / public workers.dev URL
  -> DispatchOPS API + frontend
  -> Neon PostgreSQL through Cloudflare Hyperdrive
  -> R2 for persistent import/export/backup files
  -> Cloudflare-native async jobs where required

## Critical security requirement

The Neon connection string previously pasted into chat must be considered exposed. Before production, rotate that database password and create a dedicated least-privilege database role for the application/Hyperdrive. Never commit the connection string to GitHub.

## User-side steps that cannot be performed from the GitHub repository connection

At the end of the code migration, the user will need to:

1. Log in to their Cloudflare account.
2. Create/enable the Workers project if prompted.
3. Create the Hyperdrive configuration connected to Neon (using a dedicated Neon role/password).
4. Provide the resulting Hyperdrive ID to the repository configuration or enter it through the Cloudflare dashboard.
5. Add production secrets such as `SECRET_KEY` through Cloudflare's secret manager.
6. Complete the first deployment authorization if Cloudflare asks for it.

Everything else that can safely be prepared in the repository should be done on `cloudflare-migration` first.
