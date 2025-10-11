# ZScribe Intake Agent

AI-powered medical intake agent that makes outbound calls and collects patient information using dynamic, template-driven prompts.

## Features
- AI voice agent using Google Gemini, Deepgram STT, and Cartesia TTS
- Dispatch-driven outbound calls through LiveKit SIP integration
- Dynamic prompt generation from Supabase-hosted templates
- Appointment- and patient-aware conversations via metadata payloads
- Fallback defaults for local development and smoke testing

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -e .
   ```
2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with API keys and IDs
   ```
3. **Start the API server (for template/patient/org data)**
   ```bash
   python api_server.py
   ```
4. **Run the intake worker**
   ```bash
   # Uses WorkerOptions.agent_name = "intake-agent"
   python src/calling_agent.py dev
   ```
5. **Dispatch a test call with dynamic metadata**
   ```bash
   python src/make_call.py
   ```

The worker will accept any LiveKit dispatch whose `agent_name` matches `"intake-agent"` and will hydrate the agent with the metadata payload from `make_call.py`.

## Dynamic Metadata Flow

Recent updates make the agent rely on the dispatch metadata instead of hard-coded defaults:

- `src/make_call.py` builds a JSON payload containing `template_id`, `organization_id`, `patient_id`, `appointment_details`, and the destination phone number. This payload is attached to the dispatch request.
- `src/calling_agent.py` registers the worker with `WorkerOptions(agent_name="intake-agent")`. LiveKit routes matching dispatches to this worker and exposes the metadata on `ctx.job.metadata`.
- The entrypoint normalizes metadata types (string, bytes, or dict), falls back to defaults only when the payload is empty, and logs the final IDs before starting the session.
- `IntakeAgent.on_enter` pulls those IDs into `generate_instructions_from_api(...)`, waits for the dynamic prompt, and immediately updates the running session via `await self.update_instructions(...)`.

If you need the worker to accept a different agent name, change both `WorkerOptions(agent_name=...)` and the value passed in `make_call.py` (or expose them via environment variables).

## Environment Variables

Required in `.env`:
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `SIP_OUTBOUND_TRUNK_ID`
- `GOOGLE_API_KEY`
- `DEEPGRAM_API_KEY`
- `CARTESIA_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

Optional overrides:
- `DEFAULT_TEMPLATE_ID`
- `DEFAULT_ORGANIZATION_ID`
- `DEFAULT_PATIENT_ID`

These optional values seed the worker when LiveKit jobs arrive without metadata (for example, when running `python src/calling_agent.py dev` without dispatching a call).

## Project Structure

```
api_server.py                 # FastAPI server exposing template/patient/org data
api_client.py                 # Async client for fetching data from the API server
src/
  calling_agent.py            # Worker entrypoint and IntakeAgent definition
  make_call.py                # Helper script to create dispatches and dial
  prompts.py                  # Prompt assembly from template + metadata
  state.py                    # Conversation state helpers
  tools.py                    # Transcript utilities
  predefined_templates.py     # Legacy static templates (deprecated)
data/
  transcripts/                # Saved conversation transcripts
```

## API Endpoints

- `GET /templates/{template_id}` – Fetch template by ID
- `GET /patients/{patient_id}` – Fetch patient data
- `GET /organizations/{organization_id}` – Fetch organization data
- `GET /health` – Health check
- `GET /debug/templates` – List all templates (debug)

## License

MIT
