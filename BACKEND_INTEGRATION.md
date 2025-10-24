# Backend Integration Guide - LiveKit Intake Agent

## Overview
This document outlines the integration requirements for the ZScribe Intake Agent with the backend system. The agent handles real-time medical intake calls and needs to store transcripts and generate intake notes after each call.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Webhook Endpoint Requirements](#webhook-endpoint-requirements)
3. [Data Structures](#data-structures)
4. [LangGraph Integration](#langgraph-integration)
5. [Database Schema](#database-schema)
6. [API Endpoints Summary](#api-endpoints-summary)
7. [Security Considerations](#security-considerations)
8. [Error Handling](#error-handling)

---

## Architecture Overview

### Event-Driven Flow

```
┌─────────────────────────────────────────────────────────┐
│  LiveKit Calling Agent                                  │
│  - Conducts medical intake call with patient            │
│  - Collects conversation history                        │
│  - On call end: Sends webhook event                     │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ POST /api/webhooks/call-ended
                 │ {transcript, metadata}
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Backend Webhook Handler                                │
│  - Receives event (returns 200 OK immediately)          │
│  - Queues background task for processing                │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ Background Processing
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Background Task Processor                              │
│  1. Save transcript to database                         │
│  2. Call LangGraph API to generate intake notes         │
│  3. Save intake notes to database                       │
│  4. Update UI/send notifications (optional)             │
└─────────────────────────────────────────────────────────┘
```

### Why Event-Driven?
- **Performance**: Agent doesn't wait for database operations
- **Reliability**: Background tasks can retry on failure
- **Scalability**: Can handle high volume of concurrent calls
- **Decoupling**: Agent and backend are independent

---

## Webhook Endpoint Requirements

### 1. Call Ended Webhook

**Endpoint:** `POST /api/webhooks/call-ended`

**Purpose:** Receives transcript and metadata when a call completes

**Request Headers:**
```
Content-Type: application/json
X-Webhook-Signature: <optional_signature_for_security>
```

**Request Payload:**
```json
{
  "intake_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "room_name": "intake-4ad8e0ec",
  "job_id": "AJ_Ba928qBb6eP9",
  "template_id": "8e86ef66-465f-4a5c-8ad4-ed6fca5c493e",
  "organization_id": "7172216f-0703-4ea8-9c64-39c5d121e0a8",
  "patient_id": "691ca428-4adb-44f8-a66d-aef89027abf0",
  "appointment_details": {
    "appointment_datetime": "07/25/2025 06:38 PM",
    "provider_name": "Dr. Jane Smith"
  },
  "transcript": {
    "items": [
      {
        "id": "item_155ed417fd38",
        "type": "message",
        "role": "assistant",
        "content": ["Hello, this is Sarah..."],
        "interrupted": false
      },
      {
        "id": "item_5d50d8bdc675",
        "type": "message",
        "role": "user",
        "content": ["Yes. This is a good time to talk."],
        "interrupted": false,
        "transcript_confidence": 0.9980469
      }
      // ... more messages
    ]
  },
  "metadata": {
    "call_duration_seconds": 180,
    "timestamp": "2025-10-16T12:30:45.123Z"
  }
}
```

**Expected Response:**
```json
{
  "status": "received",
  "request_id": "req_abc123"
}
```

**Response Time:** < 200ms (immediate acknowledgment)

**Status Codes:**
- `200 OK` - Event received successfully
- `400 Bad Request` - Invalid payload
- `401 Unauthorized` - Invalid signature
- `500 Internal Server Error` - Server error

---

## Data Structures

### Transcript Structure

The transcript follows LiveKit's conversation history format:

```typescript
interface TranscriptItem {
  id: string;                    // Unique message ID
  type: "message";               // Always "message"
  role: "assistant" | "user";    // Speaker role
  content: string[];             // Message content (array of text chunks)
  interrupted: boolean;          // Was this message interrupted?
  transcript_confidence?: number; // STT confidence (0-1, only for user messages)
}

interface Transcript {
  items: TranscriptItem[];
}
```

### Metadata Structure

```typescript
interface CallMetadata {
  intake_id: string;           // REQUIRED: UUID of the intake record to update
  room_name: string;           // LiveKit room identifier
  job_id: string;              // LiveKit job identifier
  template_id: string;         // Intake template used
  organization_id: string;     // Organization UUID
  patient_id: string;          // Patient UUID
  appointment_details: {
    appointment_datetime: string;
    provider_name: string;
  };
  metadata: {
    call_duration_seconds: number;
    timestamp: string;         // ISO 8601 format
  }
}
```

---

## LangGraph Integration

### Overview
After saving the transcript, the backend should call the deployed LangGraph API to generate structured intake notes.

### LangGraph Endpoint

**URL:** `https://<your-langgraph-deployment>/intake_notes/invoke`

**Method:** `POST`

**Headers:**
```
Content-Type: application/json
X-API-Key: <langgraph_api_key>  // If authentication is enabled
```

**Request Payload:**
```json
{
  "input": {
    "transcript_json": {
      "items": [...]  // Same transcript structure from webhook
    }
  }
}
```

**Response:**
```json
{
  "output": {
    "intake_notes": {
      "chief_complaint": "Severe headache on the right side",
      "history_of_present_illness": "Symptoms started 7 days ago...",
      "medical_history": {
        "current_conditions": [],
        "past_conditions": [],
        "surgeries": [],
        "hospitalizations": []
      },
      "medications": {
        "current_medications": ["Panadol - 1 tablet per day"],
        "stopped_medications": []
      },
      "allergies": {
        "drug_allergies": [],
        "food_allergies": [],
        "environmental_allergies": ["Strong smells (vinegar) - triggers severe headache"]
      },
      "family_history": [],
      "social_history": {
        "smoking": null,
        "alcohol": null,
        "recreational_drugs": null,
        "occupation": null
      },
      "review_of_systems": {
        "general": null,
        "cardiovascular": null,
        "respiratory": null,
        "gastrointestinal": null,
        "musculoskeletal": null,
        "neurological": "Severe headache on right side",
        "other": null
      },
      "vital_signs": {
        "blood_pressure": null,
        "heart_rate": null,
        "temperature": null,
        "weight": null,
        "height": null
      },
      "assessment_and_plan": null,
      "additional_notes": null
    }
  }
}
```

**Timeout:** 30 seconds (LLM processing can take time)

---

## Database Schema

### Recommended Approach: Extend Existing `intakes` Table

Since the `intakes` table already represents scheduled intake appointments with `patient_id`, `organization_id`, and `intake_template_id`, we'll add columns to store the transcript and generated notes directly. This avoids table proliferation and maintains a natural 1:1 relationship.

#### Migration SQL

```sql
-- Add transcript and intake notes columns to existing intakes table
ALTER TABLE public.intakes
ADD COLUMN transcript JSONB NULL,
ADD COLUMN intake_notes JSONB NULL;

-- Add status tracking for review workflow
ALTER TABLE public.intakes
ADD COLUMN intake_notes_status VARCHAR(50) DEFAULT 'pending';

-- Add reviewer tracking
ALTER TABLE public.intakes
ADD COLUMN reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN reviewed_at TIMESTAMP;

-- Add indexes for JSONB queries (optional, for searching within JSONB fields)
CREATE INDEX idx_intakes_transcript_gin ON public.intakes USING gin(transcript);
CREATE INDEX idx_intakes_intake_notes_gin ON public.intakes USING gin(intake_notes);

-- Add index for status filtering
CREATE INDEX idx_intakes_notes_status ON public.intakes(intake_notes_status)
WHERE intake_notes_status IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN public.intakes.transcript IS 'LiveKit conversation history in JSONB format';
COMMENT ON COLUMN public.intakes.intake_notes IS 'AI-generated structured intake notes in JSONB format';
COMMENT ON COLUMN public.intakes.intake_notes_status IS 'Status: pending, generated, reviewed, approved';
```

#### Updated `intakes` Table Structure

```sql
create table public.intakes (
  id uuid not null default gen_random_uuid(),
  organization_id uuid not null,
  intake_title text not null,
  patient_id uuid not null,
  intake_template_id uuid not null,
  intake_time timestamp without time zone not null,
  sms_reminder boolean null default false,
  retries integer null default 0,
  additional_instructions_for_ai text null,

  -- NEW: Transcript and intake notes columns
  transcript JSONB NULL,                          -- LiveKit conversation JSON
  intake_notes JSONB NULL,                        -- AI-generated structured notes
  intake_notes_status VARCHAR(50) DEFAULT 'pending',  -- pending, generated, reviewed, approved
  reviewed_by UUID REFERENCES users(id),          -- Who reviewed the notes
  reviewed_at TIMESTAMP,                          -- When reviewed

  -- Existing fields
  created_at timestamp without time zone not null default now(),
  updated_at timestamp without time zone not null default now(),
  created_by uuid null,
  scheduled_at timestamp with time zone null,
  encounter_id uuid null,

  -- Existing constraints (not shown for brevity)
  constraint intakes_pkey primary key (id),
  -- ... other constraints
);
```

### Why This Approach?

**Advantages:**
- ✅ **Natural 1:1 Relationship:** Each intake = one scheduled call = one transcript = one set of notes
- ✅ **Simpler Queries:** No JOINs needed to fetch intake + transcript + notes
- ✅ **Lower Overhead:** Avoids foreign key lookups and multiple table scans
- ✅ **Existing Infrastructure:** Leverages existing triggers, indexes, and cascade deletes
- ✅ **JSONB Efficiency:** PostgreSQL compresses JSONB and uses TOAST storage automatically

**Storage Impact:**
- Transcript: ~20-40 KB per intake (JSONB compressed)
- Intake Notes: ~2-5 KB per intake
- Total: ~25-45 KB per intake (negligible compared to table overhead of separate tables)

---

## API Endpoints Summary

### Backend Endpoints to Implement

#### 1. Webhook Handler
```
POST /api/webhooks/call-ended
- Receives call completion events
- Returns immediate 200 OK
- Queues background processing
```

#### 2. Transcript Endpoints (Optional - for UI)
```
GET /api/transcripts?patient_id={id}
- List all transcripts for a patient

GET /api/transcripts/{transcript_id}
- Get specific transcript details

GET /api/transcripts/{transcript_id}/formatted
- Get human-readable transcript
```

#### 3. Intake Notes Endpoints (Optional - for UI)
```
GET /api/intake-notes?patient_id={id}
- List all intake notes for a patient

GET /api/intake-notes/{note_id}
- Get specific intake note

PATCH /api/intake-notes/{note_id}
- Update/approve intake note
```

---

## Implementation Example (FastAPI)

### Webhook Handler

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import httpx
from typing import List, Dict, Any, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Environment configuration
LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL")
LANGGRAPH_API_KEY = os.getenv("LANGGRAPH_API_KEY")


class TranscriptItem(BaseModel):
    id: str
    type: str
    role: str
    content: List[str]
    interrupted: bool
    transcript_confidence: Optional[float] = None


class Transcript(BaseModel):
    items: List[TranscriptItem]


class AppointmentDetails(BaseModel):
    appointment_datetime: str
    provider_name: str


class CallMetadata(BaseModel):
    call_duration_seconds: int
    timestamp: str


class CallEndedPayload(BaseModel):
    intake_id: str  # REQUIRED: UUID of the intake record to update
    room_name: str
    job_id: str
    template_id: str
    organization_id: str
    patient_id: str
    appointment_details: AppointmentDetails
    transcript: Transcript
    metadata: CallMetadata


@router.post("/webhooks/call-ended")
async def handle_call_ended(
    payload: CallEndedPayload,
    background_tasks: BackgroundTasks
):
    """
    Webhook endpoint for call completion events
    Returns immediately, processes in background
    """
    try:
        # Validate payload
        logger.info(f"Received call-ended event for room: {payload.room_name}")

        # Queue background task
        background_tasks.add_task(
            process_call_ended,
            payload.dict()
        )

        return {
            "status": "received",
            "request_id": payload.job_id
        }

    except Exception as e:
        logger.error(f"Error handling call-ended webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def process_call_ended(data: dict):
    """
    Background task to process call completion
    1. Update intake record with transcript
    2. Generate intake notes via LangGraph
    3. Update intake record with generated notes
    """
    try:
        intake_id = data["intake_id"]

        # Step 1: Update intake record with transcript
        await update_intake_with_transcript(
            intake_id=intake_id,
            transcript=data["transcript"],
            call_duration_seconds=data["metadata"]["call_duration_seconds"]
        )
        logger.info(f"✅ Transcript saved to intake: {intake_id}")

        # Step 2: Generate intake notes via LangGraph
        intake_notes = await generate_intake_notes(data["transcript"])
        logger.info(f"✅ Intake notes generated for intake: {intake_id}")

        # Step 3: Update intake record with generated notes
        await update_intake_with_notes(
            intake_id=intake_id,
            notes=intake_notes
        )
        logger.info(f"✅ Intake notes saved to intake: {intake_id}")

        # Optional: Trigger notifications
        # await notify_patient(data["patient_id"])

    except Exception as e:
        logger.error(f"❌ Failed to process call-ended event: {e}", exc_info=True)
        # TODO: Add to retry queue or alert system


async def update_intake_with_transcript(
    intake_id: str,
    transcript: dict,
    call_duration_seconds: int
) -> None:
    """Update existing intake record with transcript data"""
    # Example with Supabase:
    from supabase import create_client

    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY")
    )

    response = await supabase.table("intakes").update({
        "transcript": transcript,
        "intake_notes_status": "generating",  # Mark as processing
        "updated_at": datetime.now().isoformat()
    }).eq("id", intake_id).execute()

    if not response.data:
        raise Exception(f"Failed to update intake {intake_id} with transcript")

    # Alternative with PostgreSQL directly:
    # await db.execute(
    #     """
    #     UPDATE intakes
    #     SET transcript = $1, intake_notes_status = 'generating', updated_at = NOW()
    #     WHERE id = $2
    #     """,
    #     json.dumps(transcript), intake_id
    # )


async def generate_intake_notes(transcript: dict) -> dict:
    """Call LangGraph API to generate intake notes"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LANGGRAPH_API_URL}/intake_notes/invoke",
            json={
                "input": {
                    "transcript_json": transcript
                }
            },
            headers={
                "Content-Type": "application/json",
                "X-API-Key": LANGGRAPH_API_KEY
            },
            timeout=30.0
        )

        response.raise_for_status()
        result = response.json()

        return result["output"]["intake_notes"]


async def update_intake_with_notes(
    intake_id: str,
    notes: dict
) -> None:
    """Update existing intake record with generated intake notes"""
    # Example with Supabase:
    from supabase import create_client

    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY")
    )

    response = await supabase.table("intakes").update({
        "intake_notes": notes,
        "intake_notes_status": "generated",  # Mark as completed
        "updated_at": datetime.now().isoformat()
    }).eq("id", intake_id).execute()

    if not response.data:
        raise Exception(f"Failed to update intake {intake_id} with notes")

    # Alternative with PostgreSQL directly:
    # await db.execute(
    #     """
    #     UPDATE intakes
    #     SET intake_notes = $1, intake_notes_status = 'generated', updated_at = NOW()
    #     WHERE id = $2
    #     """,
    #     json.dumps(notes), intake_id
    # )
```

---

## Security Considerations

### 1. Webhook Signature Verification

Implement HMAC signature verification to ensure webhooks are from your agent:

```python
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature"""
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)
```

**In Agent Code:**
```python
import hmac
import hashlib

webhook_secret = os.getenv("WEBHOOK_SECRET")
payload_bytes = json.dumps(payload).encode()
signature = hmac.new(
    webhook_secret.encode(),
    payload_bytes,
    hashlib.sha256
).hexdigest()

await client.post(
    webhook_url,
    json=payload,
    headers={"X-Webhook-Signature": signature}
)
```

### 2. API Authentication

- Use API keys or JWT tokens for webhook endpoints
- Implement rate limiting (e.g., 100 requests/minute per IP)
- Use HTTPS only (no HTTP)

### 3. Data Privacy

- Encrypt sensitive data in database (PHI/PII)
- Implement access controls (RBAC)
- Audit logging for all data access
- HIPAA compliance if applicable

---

## Error Handling

### Retry Strategy

Implement exponential backoff for failed LangGraph API calls:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def generate_intake_notes_with_retry(transcript: dict) -> dict:
    """Generate intake notes with automatic retry"""
    return await generate_intake_notes(transcript)
```

### Dead Letter Queue

For failed background tasks, implement a DLQ:

```python
async def process_call_ended(data: dict):
    try:
        # ... processing logic
    except Exception as e:
        logger.error(f"Failed to process call: {e}")

        # Add to dead letter queue for manual review
        await add_to_dlq({
            "event_type": "call_ended",
            "data": data,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
```

---

## Testing

### 1. Webhook Testing

Use this sample payload for testing:

```json
{
  "intake_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "room_name": "test-room-123",
  "job_id": "test-job-456",
  "template_id": "8e86ef66-465f-4a5c-8ad4-ed6fca5c493e",
  "organization_id": "7172216f-0703-4ea8-9c64-39c5d121e0a8",
  "patient_id": "691ca428-4adb-44f8-a66d-aef89027abf0",
  "appointment_details": {
    "appointment_datetime": "07/25/2025 06:38 PM",
    "provider_name": "Dr. Test Doctor"
  },
  "transcript": {
    "items": [
      {
        "id": "item_1",
        "type": "message",
        "role": "assistant",
        "content": ["Hello, this is Sarah."],
        "interrupted": false
      },
      {
        "id": "item_2",
        "type": "message",
        "role": "user",
        "content": ["I have a headache."],
        "interrupted": false,
        "transcript_confidence": 0.99
      }
    ]
  },
  "metadata": {
    "call_duration_seconds": 120,
    "timestamp": "2025-10-16T12:30:45.123Z"
  }
}
```

### 2. Test Commands

```bash
# Test webhook endpoint
curl -X POST http://localhost:8000/api/webhooks/call-ended \
  -H "Content-Type: application/json" \
  -d @test_payload.json

# Expected response
{"status":"received","request_id":"test-job-456"}
```

---

## Environment Variables

Required environment variables for backend:

```bash
# LangGraph Configuration
LANGGRAPH_API_URL=https://your-deployment.langgraph.cloud
LANGGRAPH_API_KEY=your_langgraph_api_key

# Webhook Security
WEBHOOK_SECRET=your_webhook_secret_key

# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Optional: Monitoring
SENTRY_DSN=your_sentry_dsn
```

---

## Monitoring & Observability

### Key Metrics to Track

1. **Webhook Processing**
   - Request rate
   - Error rate
   - Processing time

2. **Background Tasks**
   - Queue length
   - Processing time
   - Failure rate

3. **LangGraph API**
   - Response time
   - Success rate
   - Token usage

4. **Database**
   - Query performance
   - Storage usage

### Logging

Implement structured logging:

```python
logger.info(
    "Call processed",
    extra={
        "job_id": job_id,
        "patient_id": patient_id,
        "duration_seconds": duration,
        "transcript_length": len(transcript["items"])
    }
)
```

---

## Support & Contact

For questions or issues:
- **Agent Team:** [Your contact]
- **LangGraph Deployment:** [Deployment URL]
- **Documentation:** This file

---

## Appendix: Full Example Flow

```
1. Backend creates intake record in `intakes` table:
   - intake_id = "3fa85f64-..."
   - patient_id, organization_id, intake_template_id
   - scheduled_at, intake_time
   - transcript = NULL, intake_notes = NULL, intake_notes_status = 'pending'
   ↓
2. Backend calls make_call() with intake_id in metadata
   ↓
3. LiveKit agent receives call with intake_id in metadata
   ↓
4. Agent conducts intake interview with patient
   ↓
5. Call ends, agent sends webhook:
   POST /api/webhooks/call-ended
   {
     "intake_id": "3fa85f64-...",  // ← CRITICAL: Used to UPDATE existing record
     "transcript": {...},
     ...
   }
   ↓
6. Backend receives webhook (returns 200 OK immediately)
   ↓
7. Background task starts:
   a. UPDATE intakes SET transcript = {...}, intake_notes_status = 'generating'
   b. Call LangGraph API with transcript
   c. Receive intake notes JSON
   d. UPDATE intakes SET intake_notes = {...}, intake_notes_status = 'generated'
   ↓
8. UI queries intakes table:
   - Shows transcript (intake.transcript)
   - Shows intake notes (intake.intake_notes)
   - Shows status (intake.intake_notes_status = 'generated')
   ↓
9. Doctor reviews and approves:
   - UPDATE intakes SET intake_notes_status = 'approved', reviewed_by = doctor_id
```

### Critical Requirements for Agent Code

**The agent MUST receive `intake_id` in metadata and send it back in the webhook!**

Update `src/make_call.py` to include `intake_id`:
```python
metadata = json.dumps({
    "intake_id": intake_id,  # ← ADD THIS
    "template_id": template_id,
    "organization_id": organization_id,
    "patient_id": patient_id,
    "appointment_details": appointment_details,
    "phone_number": phone_number
})
```

---

**Document Version:** 1.0
**Last Updated:** October 20, 2025
**Status:** Ready for Implementation
