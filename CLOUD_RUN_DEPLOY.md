# Cloud Run Deployment Guide

Use this guide to roll out the shared `intake-agent` image to the three Cloud Run services (worker, intake API, data API). The new image tag is:

```
us-central1-docker.pkg.dev/zscribe/intake-agent/intake-agent:prod-2025-11-06
```

## 1. Prerequisites

- `gcloud` CLI authenticated and set to project `zscribe`.
- The Artifact Registry repo `intake-agent` (region `us-central1`) contains the tag above.
- You have permissions to update the Cloud Run services.

## 2. Common Configuration

For **all** services ensure:

- **Image**: `us-central1-docker.pkg.dev/zscribe/intake-agent/intake-agent:prod-2025-11-06`
- **Region**: `us-central1`
- **CPU/Memory**: leave existing values unless a change is required.
- **Port**: Cloud Run will inject `PORT=8080`; no manual override needed, but do **not** change the container port away from 8080.
- **Environment variables** (set or confirm all keys below):
  - `LIVEKIT_URL`
  - `LIVEKIT_API_KEY`
  - `LIVEKIT_API_SECRET`
  - `SIP_OUTBOUND_TRUNK_ID`
  - `GOOGLE_API_KEY`
  - `DEEPGRAM_API_KEY`
  - `CARTESIA_API_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `BASETEN_API_KEY`
  - `INTAKE_LANGFUSE_SECRET_KEY`
  - `INTAKE_LANGFUSE_PUBLIC_KEY`
  - `INTAKE_LANGFUSE_HOST`
  - `INTAKE_AGENT_NAME` (optional override)
  - `INTAKE_ORGANIZATION_NAME` (optional override)
  - `API_BASE_URL` (if pointing to an external data API; omit when services network together inside Cloud Run)

> Cloud Run automatically sets `PORT`. Locally we required it manually, but in Cloud Run it is injected for you.

## 3. Service-Specific Steps

### 3.1 Intake Agent Worker

This service uses the image default command, so no override is necessary.

```bash
gcloud run deploy intake-agent-worker \
  --image us-central1-docker.pkg.dev/zscribe/intake-agent/intake-agent:prod-2025-11-06 \
  --region us-central1
```

If you manage this via the console, choose *Deploy → Existing service → intake-agent-worker*, select the new image, and deploy.

### 3.2 Intake API (`src.intake_api`)

Override the command so the container runs the FastAPI app:

```bash
gcloud run deploy intake-agent-api \
  --image us-central1-docker.pkg.dev/zscribe/intake-agent/intake-agent:prod-2025-11-06 \
  --region us-central1 \
  --command "python" \
  --args "-m,src.intake_api"
```

In the console, set the *Container command* to `python` and *Arguments* to `-m,src.intake_api` (comma-separated in the UI). Keep the HTTP port at 8080.

### 3.3 Intake Data API (`src.api_server`)

Deploy with the command that launches the Supabase-backed API:

```bash
gcloud run deploy intake-agent-data-api \
  --image us-central1-docker.pkg.dev/zscribe/intake-agent/intake-agent:prod-2025-11-06 \
  --region us-central1 \
  --command "python" \
  --args "-m,src.api_server"
```

Console instructions mirror the intake API: command `python`, arguments `-m,src.api_server`.

## 4. Post-Deployment Verification

1. Open the Cloud Run service view and confirm the new revision shows the `prod-2025-11-06` tag.
2. Use *Logs → View logs* to check startup messages (look for “Application startup complete” and health checks).
3. Hit the health endpoints:
   - Worker: N/A (long-running worker), but ensure it registers successfully in logs.
   - Intake API: `GET https://<service-url>/health` → `{"status":"ok"}`.
   - Data API: `GET https://<service-url>/health` → `{"status":"healthy"}`.
4. If either API returns 5xx, re-check env vars and the command override.

## 5. Rollback

If you need to revert, redeploy the prior known-good image tag (e.g., `prod-2025-11-05-2`) using the same commands above, replacing the image reference.
