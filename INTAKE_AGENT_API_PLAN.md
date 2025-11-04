# Intake Agent API & Worker Deployment Plan

## Objectives
- Expose intake-call orchestration through a **single HTTP API** that the application layer can invoke.
- Keep the LiveKit voice agent running as a dedicated worker for low-latency call handling.
- Maintain existing integrations (Langfuse observability, Supabase lookups, transcript storage) with minimal refactors.

## Proposed Architecture
- **Service 1 – Intake API (FastAPI)**
  - Extends `src/api_server.py`.
  - Publishes REST endpoints, performs validation, and triggers call creation.
  - Runs under Uvicorn/Gunicorn on Cloud Run (or equivalent); stateless aside from outbound calls.
- **Service 2 – Agent Worker**
  - Runs `python -m src.calling_agent start`.
  - Registers with LiveKit’s agent dispatch queue (`agent_name="intake-agent"`).
  - Handles audio conversations, Langfuse tracing, and transcript persistence.
- Services communicate indirectly through LiveKit and shared data stores (Supabase, Langfuse).

> From the app team’s perspective there is one public API. The worker remains an internal component deployed alongside the API.

## Runtime Flow
1. Worker service boots, connects to LiveKit, and waits for dispatch jobs.
2. API service exposes endpoints and handles requests from the application layer.
3. Client calls `POST /intake-calls` with patient/org/template identifiers and phone number.
4. API validates payload, optionally enriches data via Supabase (`api_client` helpers).
5. API invokes `make_call.make_call(...)`, which:
   - Creates a LiveKit agent dispatch with metadata.
   - Initiates the SIP dial to the patient.
6. LiveKit assigns the dispatch to the running worker; the worker joins the room, loads prompts from Langfuse, and conducts the intake.
7. Worker saves transcripts and metadata (Supabase, Langfuse, filesystem).
8. API can expose status queries (optional future step) for downstream systems.

## API Surface (Initial)
- `GET /health`
  - Purpose: readiness/liveness probe for Cloud Run and monitoring.
  - Response: `{ "status": "ok", "livekit": "...", "supabase": "...", "langfuse": "..." }` (extend as needed).
- `POST /intake-calls`
  - Request body example:
    ```json
    {
      "phone_number": "+1971265679",
      "template_id": "8e86ef66-465f-4a5c-8ad4-ed6fca5c493e",
      "organization_id": "0da4a59a-275f-4f2d-92f0-5e0c60b0f1da",
      "patient_id": "4b3a1edb-76c5-46f4-ad0f-3c164348202b",
      "intake_id": "a8adaf8a-ed8e-48d2-9d45-8130e9c164e3",
      "greeting_override": null
    }
    ```
  - Handler behaviour:
    - Validate via Pydantic model.
    - Optionally verify referenced records via Supabase.
    - Call `make_call.make_call(...)`; run asynchronously so request returns after dispatch creation.
    - Response example:
      ```json
      {
        "intake_id": "a8adaf8a-ed8e-48d2-9d45-8130e9c164e3",
        "room_name": "intake-1fc2a3b9",
        "dispatch_id": "AD_123...",
        "status": "queued"
      }
      ```
- Future extensions (optional):
  - `GET /intake-calls/{intake_id}` for transcript/status.
  - `POST /intake-calls/{intake_id}/cancel` if LiveKit supports cancelation.

## Deployment Notes
- **Cloud Run**: deploy both services separately.
  - Intake API: scale to zero; configure authentication (service account, API key, or gateway).
  - Worker: set minimum instances to 1 to avoid cold starts; disable HTTP trigger if not required.
- **Configuration**: share required environment variables (LiveKit keys, Supabase, Langfuse). Ensure each service has only the credentials it needs.
- **Logging & Monitoring**: forward container logs to GCP logging; use Langfuse traces for call analytics; consider Cloud Monitoring alerts on health endpoint failures.
- **CI/CD**: build Docker images via Cloud Build or GitHub Actions. Tag versions alongside infrastructure configs.

## Open Questions for Leadership
1. Authentication expectations for the API (API key, OAuth, service-to-service token?).
2. Should `POST /intake-calls` block until SIP dial succeeds, or return immediately after dispatch creation?
3. Desired schema for status polling or webhooks (if app needs real-time updates).
4. Any compliance/logging requirements (PHI handling, audit trails).
5. Target scaling limits (concurrent calls per worker, need for horizontal scaling).

Answering these points will let us finalize the FastAPI implementation and deployment configs.
