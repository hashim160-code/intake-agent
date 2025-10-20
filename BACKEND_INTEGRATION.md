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

### Recommended Tables

#### 1. `call_transcripts` Table

```sql
CREATE TABLE call_transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_name VARCHAR(255) NOT NULL,
    job_id VARCHAR(255) NOT NULL UNIQUE,
    patient_id UUID NOT NULL REFERENCES patients(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    template_id UUID NOT NULL REFERENCES intake_templates(id),

    -- Transcript data (JSONB for flexible querying)
    transcript JSONB NOT NULL,

    -- Metadata
    call_duration_seconds INTEGER,
    appointment_datetime TIMESTAMP,
    provider_name VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Indexes for common queries
    INDEX idx_patient_id (patient_id),
    INDEX idx_organization_id (organization_id),
    INDEX idx_created_at (created_at)
);
```

#### 2. `intake_notes` Table

```sql
CREATE TABLE intake_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id UUID NOT NULL REFERENCES call_transcripts(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Intake notes data (JSONB for structured medical data)
    notes JSONB NOT NULL,

    -- Status tracking
    status VARCHAR(50) DEFAULT 'generated', -- generated, reviewed, approved
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Indexes
    INDEX idx_patient_id (patient_id),
    INDEX idx_transcript_id (transcript_id),
    INDEX idx_status (status)
);
```

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
    1. Save transcript to database
    2. Generate intake notes via LangGraph
    3. Save intake notes to database
    """
    try:
        # Step 1: Save transcript
        transcript_id = await save_transcript_to_db(data)
        logger.info(f"✅ Transcript saved: {transcript_id}")

        # Step 2: Generate intake notes
        intake_notes = await generate_intake_notes(data["transcript"])
        logger.info(f"✅ Intake notes generated for transcript: {transcript_id}")

        # Step 3: Save intake notes
        notes_id = await save_intake_notes_to_db(
            transcript_id=transcript_id,
            patient_id=data["patient_id"],
            organization_id=data["organization_id"],
            notes=intake_notes
        )
        logger.info(f"✅ Intake notes saved: {notes_id}")

        # Optional: Trigger notifications
        # await notify_patient(data["patient_id"])

    except Exception as e:
        logger.error(f"❌ Failed to process call-ended event: {e}", exc_info=True)
        # TODO: Add to retry queue or alert system


async def save_transcript_to_db(data: dict) -> str:
    """Save transcript to database"""
    # Implementation depends on your database
    # Example with SQLAlchemy or your ORM:

    transcript_record = {
        "room_name": data["room_name"],
        "job_id": data["job_id"],
        "patient_id": data["patient_id"],
        "organization_id": data["organization_id"],
        "template_id": data["template_id"],
        "transcript": data["transcript"],
        "call_duration_seconds": data["metadata"]["call_duration_seconds"],
        "appointment_datetime": data["appointment_details"]["appointment_datetime"],
        "provider_name": data["appointment_details"]["provider_name"]
    }

    # Insert into database
    # result = await db.call_transcripts.insert(transcript_record)
    # return result.id

    return "transcript_uuid_here"  # Replace with actual implementation


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


async def save_intake_notes_to_db(
    transcript_id: str,
    patient_id: str,
    organization_id: str,
    notes: dict
) -> str:
    """Save intake notes to database"""
    notes_record = {
        "transcript_id": transcript_id,
        "patient_id": patient_id,
        "organization_id": organization_id,
        "notes": notes,
        "status": "generated"
    }

    # Insert into database
    # result = await db.intake_notes.insert(notes_record)
    # return result.id

    return "notes_uuid_here"  # Replace with actual implementation
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
1. Patient calls intake number
   ↓
2. LiveKit routes to agent
   ↓
3. Agent conducts intake interview
   ↓
4. Call ends, agent sends webhook:
   POST /api/webhooks/call-ended
   {
     "room_name": "intake-4ad8e0ec",
     "transcript": {...},
     ...
   }
   ↓
5. Backend receives webhook (returns 200 OK immediately)
   ↓
6. Background task starts:
   a. Save transcript to call_transcripts table
   b. Call LangGraph API with transcript
   c. Receive intake notes JSON
   d. Save to intake_notes table
   ↓
7. UI updates showing:
   - Call transcript available
   - Intake notes generated (pending review)
   ↓
8. Doctor reviews and approves intake notes
```

---

**Document Version:** 1.0
**Last Updated:** October 20, 2025
**Status:** Ready for Implementation
