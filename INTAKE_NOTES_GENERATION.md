# Intake Notes Generation - Complete Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Options Comparison](#options-comparison)
4. [Recommended Approach: Backend Asynchronous](#recommended-approach-backend-asynchronous)
5. [Complete Flow Timeline](#complete-flow-timeline)
6. [Implementation Guide](#implementation-guide)
7. [File Structure](#file-structure)
8. [Code Implementation](#code-implementation)
9. [Database Schema](#database-schema)
10. [API Endpoints](#api-endpoints)
11. [Template Structure](#template-structure)
12. [Testing](#testing)
13. [Deployment](#deployment)
14. [Troubleshooting](#troubleshooting)

---

## Overview

**Purpose:** Automatically generate structured medical intake notes from conversation transcripts using AI/LLM.

**Input:**
- Conversation transcript (patient-agent dialogue)
- Template (structure/format for notes)
- Prompt (instructions for LLM)

**Output:**
- Structured medical intake notes (formatted document)

**Key Benefits:**
- ✅ Saves time for medical staff
- ✅ Consistent formatting
- ✅ Automated data extraction
- ✅ Reduces human error
- ✅ Searchable and structured data

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         COMPLETE FLOW                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────┐
│   Patient   │ ──► Makes call
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Your App   │ ──► Creates call, Displays results
│ (Frontend)  │
└──────┬──────┘
       │
       │ (1) Create call request
       ▼
┌─────────────────┐
│  Your Backend   │ ──► Main API Server
│      API        │     - Receives transcripts
└──────┬──────────┘     - Manages database
       │                - Generates notes
       │
       │ (2) Create LiveKit room
       ▼
┌─────────────────┐
│   LiveKit       │ ──► Voice call platform
│     Room        │
└──────┬──────────┘
       │
       │ (3) Agent joins room
       ▼
┌─────────────────┐
│ Intake Agent    │ ──► calling_agent.py
│ (This Project)  │     - Talks to patient
└──────┬──────────┘     - Collects info
       │                - Sends transcript
       │
       │ (4) Send transcript after call
       ▼
┌─────────────────┐
│  Backend API    │ ──► Saves transcript
│  (Again)        │     Triggers note generation
└──────┬──────────┘
       │
       │ (5) Background task
       ▼
┌─────────────────┐
│ Notes Generator │ ──► Uses LLM (OpenAI/Vertex)
│   (Background)  │     Generates structured notes
└──────┬──────────┘
       │
       │ (6) Save notes
       ▼
┌─────────────────┐
│    Database     │ ──► Stores:
│  (MongoDB/PG)   │     - Transcripts
└─────────────────┘     - Notes
                        - Status
```

---

## Options Comparison

### Option 1: Real-Time in Agent
Generate notes **immediately** when call ends, in the agent code.

**Pros:**
- ✅ Notes ready immediately
- ✅ Simple implementation
- ✅ Everything in one place

**Cons:**
- ❌ Slows down call completion
- ❌ If generation fails, call is affected
- ❌ Hard to retry
- ❌ Blocks agent from handling next call

**Best for:** Simple prototypes, low-volume systems

---

### Option 2: Backend Asynchronous (RECOMMENDED)
Generate notes **in background** after transcript is saved.

**Pros:**
- ✅ Fast call completion
- ✅ Reliable (transcript saved even if notes fail)
- ✅ Can retry generation
- ✅ Better error handling
- ✅ Scalable
- ✅ Doesn't block agent

**Cons:**
- ⚠️ Notes have 10-20 second delay
- ⚠️ Requires backend implementation

**Best for:** Production systems, scalable applications

---

### Option 3: On-Demand
Generate notes **only when user clicks a button**.

**Pros:**
- ✅ Maximum control
- ✅ Can use different templates
- ✅ Can regenerate anytime
- ✅ No wasted API calls

**Cons:**
- ❌ User must wait
- ❌ Extra manual step
- ❌ Notes not automatic

**Best for:** Custom workflows, multiple template options

---

## Recommended Approach: Backend Asynchronous

**Why?** Best balance of speed, reliability, and scalability for production.

---

## Complete Flow Timeline

### Step-by-Step Execution

| Time | Event | Component | Details |
|------|-------|-----------|---------|
| **0:00** | Call starts | LiveKit + Agent | Patient connected, agent joins room |
| **0:00-5:00** | Conversation | Agent ↔ Patient | Agent asks questions, patient responds |
| **5:00** | Call ends | Agent | Patient hangs up, cleanup begins |
| **5:01** | Extract transcript | Agent | `session.history.to_dict()` called |
| **5:02** | Send to backend | Agent → Backend | HTTP POST to `/api/transcripts` |
| **5:03** | Save transcript | Backend | Saved to database, status = "processing" |
| **5:04** | Schedule background task | Backend | `background_tasks.add_task()` |
| **5:04** | Agent exits | Agent | ✅ Agent cleanup complete |
| **5:05** | Fetch template | Background Worker | Get template from database |
| **5:06** | Build prompt | Background Worker | Combine transcript + template |
| **5:07** | Call LLM | Background Worker | OpenAI/Vertex API called |
| **5:07-5:17** | LLM processing | LLM Service | Generating notes (~10 seconds) |
| **5:18** | Notes received | Background Worker | LLM returns generated notes |
| **5:19** | Save notes | Background Worker | Update database with notes |
| **5:20** | Complete | Database | Status = "completed" ✅ |
| **5:30+** | User views | Frontend | User can see transcript + notes |

**Total time:** Call ends at 5:00, notes ready at 5:20 (20 seconds)

---

## Implementation Guide

### Prerequisites

- Python 3.11+
- FastAPI (for backend)
- MongoDB or PostgreSQL (database)
- OpenAI API key OR Google Vertex AI credentials
- Existing LiveKit agent (calling_agent.py)

### High-Level Steps

1. **Modify agent** to send transcript to backend (minimal changes)
2. **Create backend API** to receive transcripts
3. **Implement notes generator** service
4. **Set up database** to store transcripts and notes
5. **Configure environment** variables
6. **Test the flow** end-to-end
7. **Deploy** backend and agent

---

## File Structure

```
your_project/
├── src/
│   ├── calling_agent.py          # Agent code (MINIMAL CHANGES)
│   ├── prompts.py                 # Existing file
│   └── ...
│
├── backend/                        # NEW - Backend API
│   ├── main.py                    # Main FastAPI application
│   ├── services/
│   │   └── notes_generator.py    # Notes generation logic
│   ├── models/
│   │   └── transcript.py         # Data models
│   ├── config.py                  # Database configuration
│   └── requirements.txt           # Backend dependencies
│
├── templates/                      # NEW - Note templates
│   └── default_intake_template.md
│
├── .env                           # Environment variables (UPDATE)
├── README.md
├── INTAKE_NOTES_GENERATION.md     # This file
└── requirements.txt               # Agent dependencies
```

---

## Code Implementation

### 1. Agent Changes (src/calling_agent.py)

**Location:** Lines 147-157 (the `save_transcript` callback)

**BEFORE (saves to file):**
```python
async def save_transcript():
    try:
        os.makedirs("transcripts", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"transcripts/transcript_{ctx.room.name}_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(session.history.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Transcript saved: {filename}")
```

**AFTER (sends to backend):**
```python
async def save_transcript():
    try:
        import aiohttp

        transcript_data = session.history.to_dict()

        # Send to backend API
        async with aiohttp.ClientSession() as http_session:
            response = await http_session.post(
                f"{os.getenv('BACKEND_API_URL')}/api/transcripts",
                json={
                    "patient_id": patient_id,
                    "organization_id": organization_id,
                    "template_id": template_id,
                    "room_name": ctx.room.name,
                    "transcript": transcript_data,
                    "appointment_details": appointment_details,
                    "call_ended_at": datetime.now().isoformat()
                },
                headers={
                    "Authorization": f"Bearer {os.getenv('API_SECRET_KEY')}"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            )

            if response.status == 200:
                logger.info("✅ Transcript sent to backend")
            else:
                logger.error(f"❌ Backend error: {response.status}")
                # Fallback: save locally
                os.makedirs("transcripts", exist_ok=True)
                with open(f"transcripts/backup_{ctx.room.name}.json", 'w') as f:
                    json.dump(transcript_data, f, indent=2)

    except Exception as e:
        logger.error(f"❌ Failed to send transcript: {e}", exc_info=True)
        # Always save locally as backup
        try:
            os.makedirs("transcripts", exist_ok=True)
            with open(f"transcripts/backup_{ctx.room.name}.json", 'w') as f:
                json.dump(session.history.to_dict(), f, indent=2)
        except:
            pass

ctx.add_shutdown_callback(save_transcript)
```

**Add import at top of file:**
```python
import aiohttp  # Add this line around line 8
```

---

### 2. Backend API (backend/main.py)

```python
"""
Backend API for ZScribe Intake Agent
Handles transcript reception and notes generation
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
from dotenv import load_dotenv

from services.notes_generator import generate_and_save_notes
from models.transcript import TranscriptCreate, TranscriptResponse
from config import get_database

load_dotenv()

app = FastAPI(
    title="ZScribe Intake API",
    description="API for managing medical intake transcripts and notes",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
db = get_database()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "zscribe-intake-api"}


@app.post("/api/transcripts", response_model=TranscriptResponse)
async def receive_transcript(
    data: TranscriptCreate,
    background_tasks: BackgroundTasks,
    authorization: str = Header(None)
):
    """
    Receive transcript from agent after call ends.
    Saves transcript and schedules background task for notes generation.

    Args:
        data: Transcript data from agent
        background_tasks: FastAPI background tasks
        authorization: Bearer token for authentication

    Returns:
        TranscriptResponse with transcript ID and status
    """
    # Verify API key
    expected_key = f"Bearer {os.getenv('API_SECRET_KEY')}"
    if authorization != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Save transcript to database
        transcript_record = {
            "patient_id": data.patient_id,
            "organization_id": data.organization_id,
            "template_id": data.template_id,
            "room_name": data.room_name,
            "transcript": data.transcript,
            "appointment_details": data.appointment_details,
            "status": "processing",  # Initial status
            "intake_notes": None,    # Will be filled by background task
            "created_at": datetime.now(),
            "notes_generated_at": None,
            "error": None
        }

        result = await db.transcripts.insert_one(transcript_record)
        transcript_id = str(result.inserted_id)

        print(f"✅ Transcript saved: {transcript_id}")

        # Schedule background task for notes generation
        background_tasks.add_task(
            generate_and_save_notes,
            transcript_id=transcript_id,
            transcript=data.transcript,
            template_id=data.template_id,
            organization_id=data.organization_id,
            db=db
        )

        print(f"🔄 Background task scheduled for {transcript_id}")

        return {
            "success": True,
            "transcript_id": transcript_id,
            "status": "processing",
            "message": "Transcript saved, notes generation in progress"
        }

    except Exception as e:
        print(f"❌ Error saving transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transcripts/{transcript_id}")
async def get_transcript(transcript_id: str):
    """
    Get transcript and notes by ID.

    Args:
        transcript_id: Database ID of transcript

    Returns:
        Complete transcript record including notes if ready
    """
    from bson import ObjectId

    try:
        transcript = await db.transcripts.find_one({"_id": ObjectId(transcript_id)})

        if not transcript:
            raise HTTPException(status_code=404, detail="Transcript not found")

        # Convert ObjectId to string for JSON serialization
        transcript["_id"] = str(transcript["_id"])

        return transcript

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/patients/{patient_id}/transcripts")
async def get_patient_transcripts(patient_id: str, limit: int = 100):
    """
    Get all transcripts for a specific patient.

    Args:
        patient_id: Patient ID
        limit: Maximum number of transcripts to return

    Returns:
        List of transcripts for the patient
    """
    try:
        transcripts = await db.transcripts.find(
            {"patient_id": patient_id}
        ).sort("created_at", -1).to_list(limit)

        # Convert ObjectIds to strings
        for t in transcripts:
            t["_id"] = str(t["_id"])

        return {"transcripts": transcripts, "count": len(transcripts)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transcripts/{transcript_id}/retry-notes")
async def retry_notes_generation(
    transcript_id: str,
    background_tasks: BackgroundTasks
):
    """
    Retry notes generation if it failed.

    Args:
        transcript_id: Database ID of transcript
        background_tasks: FastAPI background tasks

    Returns:
        Success message
    """
    from bson import ObjectId

    try:
        transcript = await db.transcripts.find_one({"_id": ObjectId(transcript_id)})

        if not transcript:
            raise HTTPException(status_code=404, detail="Transcript not found")

        # Update status to processing
        await db.transcripts.update_one(
            {"_id": ObjectId(transcript_id)},
            {"$set": {"status": "processing", "error": None}}
        )

        # Schedule background task
        background_tasks.add_task(
            generate_and_save_notes,
            transcript_id=transcript_id,
            transcript=transcript["transcript"],
            template_id=transcript["template_id"],
            organization_id=transcript["organization_id"],
            db=db
        )

        return {
            "success": True,
            "message": "Notes generation restarted"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/templates/{template_id}")
async def get_template(template_id: str, organization_id: str):
    """
    Get template by ID.

    Args:
        template_id: Template ID
        organization_id: Organization ID

    Returns:
        Template content
    """
    try:
        template = await db.templates.find_one({
            "id": template_id,
            "organization_id": organization_id
        })

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        template["_id"] = str(template["_id"])
        return template

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

### 3. Notes Generator Service (backend/services/notes_generator.py)

```python
"""
Service for generating intake notes from transcripts using LLM
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Choose your LLM provider
import openai  # For OpenAI
# OR
# import google.generativeai as genai  # For Vertex AI

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize LLM client
openai.api_key = os.getenv("OPENAI_API_KEY")


async def generate_and_save_notes(
    transcript_id: str,
    transcript: Dict[str, Any],
    template_id: str,
    organization_id: str,
    db
):
    """
    Background task to generate intake notes from transcript.

    This function:
    1. Fetches the template from database
    2. Builds a prompt with transcript + template
    3. Calls LLM to generate notes
    4. Saves notes back to database

    Args:
        transcript_id: Database ID of the transcript
        transcript: The conversation transcript (dict)
        template_id: ID of the template to use
        organization_id: Organization ID
        db: Database connection
    """
    from bson import ObjectId

    logger.info(f"🤖 Starting note generation for transcript {transcript_id}")

    try:
        # Step 1: Fetch template from database
        template = await db.templates.find_one({
            "id": template_id,
            "organization_id": organization_id
        })

        if not template:
            logger.error(f"❌ Template {template_id} not found")
            await mark_as_failed(db, transcript_id, "Template not found")
            return

        logger.info(f"📋 Using template: {template.get('name', 'Unknown')}")

        # Step 2: Build prompt for LLM
        prompt = build_intake_notes_prompt(
            transcript=transcript,
            template_content=template.get('content', get_default_template())
        )

        logger.info(f"📝 Calling LLM to generate notes (prompt length: {len(prompt)} chars)")

        # Step 3: Call LLM to generate notes
        notes = await call_llm_for_notes(prompt)

        logger.info(f"✅ Notes generated ({len(notes)} characters)")

        # Step 4: Save notes to database
        await db.transcripts.update_one(
            {"_id": ObjectId(transcript_id)},
            {
                "$set": {
                    "intake_notes": notes,
                    "notes_generated_at": datetime.now(),
                    "status": "completed"
                }
            }
        )

        logger.info(f"💾 Notes saved for transcript {transcript_id}")

    except Exception as e:
        logger.error(f"❌ Failed to generate notes: {e}", exc_info=True)
        await mark_as_failed(db, transcript_id, str(e))


def build_intake_notes_prompt(transcript: Dict[str, Any], template_content: str) -> str:
    """
    Build the prompt for the LLM to generate intake notes.

    Args:
        transcript: Conversation transcript
        template_content: Template structure

    Returns:
        Complete prompt string for LLM
    """
    # Format transcript messages into readable text
    conversation = []

    messages = transcript.get("messages", [])
    if not messages:
        # Try alternative structure
        messages = transcript.get("conversation", [])

    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")

        # Clean up role names
        if role == "ASSISTANT":
            role = "AGENT"
        elif role == "USER":
            role = "PATIENT"

        conversation.append(f"{role}: {content}")

    conversation_text = "\n\n".join(conversation)

    # Build comprehensive prompt
    prompt = f"""You are a medical documentation specialist tasked with generating structured medical intake notes from a conversation transcript.

INSTRUCTIONS:
1. Follow the template structure exactly
2. Extract all relevant medical information from the conversation
3. Use appropriate medical terminology
4. If information is not mentioned in the conversation, write "Not mentioned" or "N/A"
5. Be concise but thorough
6. Format the output in clean markdown
7. Pay special attention to:
   - Chief complaint
   - Symptoms (onset, duration, severity, location)
   - Medical history
   - Current medications
   - Allergies
8. Maintain professional medical documentation standards

TEMPLATE STRUCTURE:
{template_content}

CONVERSATION TRANSCRIPT:
{conversation_text}

Now generate the complete intake notes following the template structure above:"""

    return prompt


async def call_llm_for_notes(prompt: str) -> str:
    """
    Call LLM API to generate notes from prompt.

    Args:
        prompt: Complete prompt for LLM

    Returns:
        Generated intake notes as string
    """
    try:
        # Using OpenAI GPT
        response = openai.chat.completions.create(
            model="gpt-4o-mini",  # or "gpt-4" for higher quality
            messages=[
                {
                    "role": "system",
                    "content": "You are a medical documentation specialist who creates accurate, concise, and well-structured intake notes from patient conversations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for more consistent output
            max_tokens=2500,   # Adjust based on your needs
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )

        notes = response.choices[0].message.content
        return notes

    except Exception as e:
        logger.error(f"❌ LLM API error: {e}")
        raise


async def mark_as_failed(db, transcript_id: str, error_message: str):
    """
    Mark transcript notes generation as failed.

    Args:
        db: Database connection
        transcript_id: Transcript ID
        error_message: Error description
    """
    from bson import ObjectId

    await db.transcripts.update_one(
        {"_id": ObjectId(transcript_id)},
        {
            "$set": {
                "status": "failed",
                "error": error_message,
                "failed_at": datetime.now()
            }
        }
    )
    logger.info(f"❌ Marked transcript {transcript_id} as failed: {error_message}")


def get_default_template() -> str:
    """
    Default intake notes template if none found in database.

    Returns:
        Default template string
    """
    return """
# MEDICAL INTAKE NOTES

## PATIENT INFORMATION
- Full Name:
- Date of Birth:
- Contact Number:
- Email:

## APPOINTMENT DETAILS
- Provider Name:
- Appointment Date/Time:
- Reason for Visit:

## CHIEF COMPLAINT
[Primary reason for visit in patient's own words]

## HISTORY OF PRESENT ILLNESS
- Onset: [When symptoms started]
- Duration: [How long symptoms have lasted]
- Severity: [Mild/Moderate/Severe - scale if applicable]
- Location: [Body part/area affected]
- Quality: [Description of symptoms - sharp, dull, throbbing, etc.]
- Associated Symptoms: [Related symptoms]
- Aggravating Factors: [What makes it worse]
- Relieving Factors: [What makes it better]

## MEDICAL HISTORY
- Previous Conditions:
- Previous Surgeries:
- Previous Hospitalizations:
- Chronic Conditions:

## CURRENT MEDICATIONS
[List all medications with dosage and frequency]

## ALLERGIES
- Medication Allergies:
- Food Allergies:
- Environmental Allergies:
- Reaction Type:

## FAMILY HISTORY
[Relevant family medical history]

## SOCIAL HISTORY
- Smoking: [Yes/No/Former - pack years if applicable]
- Alcohol: [Frequency and amount]
- Drug Use: [If applicable]
- Exercise: [Frequency and type]
- Occupation:

## REVIEW OF SYSTEMS
[Any additional symptoms mentioned across body systems]

## ADDITIONAL NOTES
[Any other relevant information from the conversation]

## CALL QUALITY METRICS
- Call Duration:
- Patient Cooperation: [Good/Fair/Poor]
- Information Completeness: [Complete/Partial/Incomplete]
- Follow-up Needed: [Yes/No - what information is missing]
"""
```

---

### 4. Data Models (backend/models/transcript.py)

```python
"""
Pydantic models for API request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class TranscriptCreate(BaseModel):
    """Model for creating a new transcript"""
    patient_id: str = Field(..., description="Patient ID")
    organization_id: str = Field(..., description="Organization ID")
    template_id: str = Field(..., description="Template ID for notes generation")
    room_name: str = Field(..., description="LiveKit room name")
    transcript: Dict[str, Any] = Field(..., description="Conversation transcript")
    appointment_details: Optional[Dict[str, Any]] = Field(None, description="Appointment details")
    call_ended_at: Optional[str] = Field(None, description="Call end timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "691ca428-4adb-44f8-a66d-aef89027abf0",
                "organization_id": "7172216f-0703-4ea8-9c64-39c5d121e0a8",
                "template_id": "bd9a2e9e-cdab-44d6-9882-58fc75ea9cda",
                "room_name": "intake-2c799b83",
                "transcript": {
                    "messages": [
                        {"role": "assistant", "content": "Hello..."},
                        {"role": "user", "content": "Hi..."}
                    ]
                },
                "appointment_details": {
                    "appointment_datetime": "07/25/2025 06:38 PM",
                    "provider_name": "Dr. Jane Smith"
                }
            }
        }


class TranscriptResponse(BaseModel):
    """Model for transcript API response"""
    success: bool = Field(..., description="Whether operation succeeded")
    transcript_id: str = Field(..., description="Database ID of saved transcript")
    status: str = Field(..., description="Current status (processing/completed/failed)")
    message: str = Field(..., description="Human-readable message")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "transcript_id": "64f1a2b3c4d5e6f7g8h9i0j1",
                "status": "processing",
                "message": "Transcript saved, notes generation in progress"
            }
        }
```

---

### 5. Database Config (backend/config.py)

```python
"""
Database configuration
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

_db_client = None
_database = None


def get_database():
    """
    Get database connection (singleton pattern).

    Returns:
        Motor AsyncIO MongoDB database instance
    """
    global _db_client, _database

    if _database is None:
        # MongoDB connection string
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        db_name = os.getenv("DB_NAME", "zscribe")

        print(f"Connecting to MongoDB: {mongo_url}")
        print(f"Database: {db_name}")

        _db_client = AsyncIOMotorClient(mongo_url)
        _database = _db_client[db_name]

        print("✅ Database connection established")

    return _database


async def close_database():
    """Close database connection"""
    global _db_client

    if _db_client:
        _db_client.close()
        print("Database connection closed")
```

---

### 6. Backend Requirements (backend/requirements.txt)

```txt
# FastAPI and server
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6

# Database
motor==3.3.2
pymongo==4.6.1

# Data validation
pydantic==2.5.3
pydantic-settings==2.1.0

# LLM providers (choose one or both)
openai==1.12.0
google-generativeai==0.3.2

# Utilities
python-dotenv==1.0.0
aiohttp==3.9.1

# Optional: for better logging
rich==13.7.0
```

---

### 7. Environment Variables (.env)

Update your existing `.env` file:

```env
# ===== EXISTING LIVEKIT VARIABLES =====
LIVEKIT_URL=wss://zscribe-uryls55n.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# ===== EXISTING AGENT VARIABLES =====
DEFAULT_TEMPLATE_ID=bd9a2e9e-cdab-44d6-9882-58fc75ea9cda
DEFAULT_ORGANIZATION_ID=7172216f-0703-4ea8-9c64-39c5d121e0a8
DEFAULT_PATIENT_ID=691ca428-4adb-44f8-a66d-aef89027abf0

# ===== NEW BACKEND VARIABLES =====
# Backend API Configuration
BACKEND_API_URL=http://localhost:8000
API_SECRET_KEY=your_random_secret_key_change_in_production_12345

# Database Configuration
MONGODB_URL=mongodb://localhost:27017
DB_NAME=zscribe

# LLM Configuration (choose one)
# Option 1: OpenAI
OPENAI_API_KEY=sk-proj-...your_openai_key

# Option 2: Google Vertex AI
# GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
# GOOGLE_CLOUD_PROJECT=your-project-id
# GOOGLE_CLOUD_REGION=us-central1
```

---

## Database Schema

### Transcripts Collection

```javascript
{
  "_id": ObjectId("64f1a2b3c4d5e6f7g8h9i0j1"),
  "patient_id": "691ca428-4adb-44f8-a66d-aef89027abf0",
  "organization_id": "7172216f-0703-4ea8-9c64-39c5d121e0a8",
  "template_id": "bd9a2e9e-cdab-44d6-9882-58fc75ea9cda",
  "room_name": "intake-2c799b83",
  "transcript": {
    "messages": [
      {
        "role": "assistant",
        "content": "Hello, this is the medical intake agent...",
        "timestamp": "2025-10-13T23:00:00Z"
      },
      {
        "role": "user",
        "content": "Hi, yes this is Ali",
        "timestamp": "2025-10-13T23:00:05Z"
      }
    ]
  },
  "appointment_details": {
    "appointment_datetime": "07/25/2025 06:38 PM",
    "provider_name": "Dr. Jane Smith"
  },
  "status": "completed",  // processing | completed | failed
  "intake_notes": "# MEDICAL INTAKE NOTES\n\n## PATIENT INFORMATION...",
  "created_at": ISODate("2025-10-13T23:05:03Z"),
  "notes_generated_at": ISODate("2025-10-13T23:05:20Z"),
  "error": null,
  "failed_at": null
}
```

### Templates Collection

```javascript
{
  "_id": ObjectId("64f1a2b3c4d5e6f7g8h9i0j2"),
  "id": "bd9a2e9e-cdab-44d6-9882-58fc75ea9cda",
  "organization_id": "7172216f-0703-4ea8-9c64-39c5d121e0a8",
  "name": "General Medical Intake",
  "description": "Standard template for general medical intake calls",
  "content": "# MEDICAL INTAKE NOTES\n\n## PATIENT INFORMATION...",
  "created_at": ISODate("2025-01-01T00:00:00Z"),
  "updated_at": ISODate("2025-01-01T00:00:00Z"),
  "active": true
}
```

---

## API Endpoints

### 1. POST /api/transcripts
**Purpose:** Receive transcript from agent after call ends

**Request:**
```json
{
  "patient_id": "691ca428-4adb-44f8-a66d-aef89027abf0",
  "organization_id": "7172216f-0703-4ea8-9c64-39c5d121e0a8",
  "template_id": "bd9a2e9e-cdab-44d6-9882-58fc75ea9cda",
  "room_name": "intake-2c799b83",
  "transcript": {...},
  "appointment_details": {...}
}
```

**Response:**
```json
{
  "success": true,
  "transcript_id": "64f1a2b3c4d5e6f7g8h9i0j1",
  "status": "processing",
  "message": "Transcript saved, notes generation in progress"
}
```

---

### 2. GET /api/transcripts/{transcript_id}
**Purpose:** Get transcript and notes by ID

**Response:**
```json
{
  "_id": "64f1a2b3c4d5e6f7g8h9i0j1",
  "patient_id": "691ca428-4adb-44f8-a66d-aef89027abf0",
  "status": "completed",
  "transcript": {...},
  "intake_notes": "# MEDICAL INTAKE NOTES\n\n...",
  "created_at": "2025-10-13T23:05:03Z",
  "notes_generated_at": "2025-10-13T23:05:20Z"
}
```

---

### 3. GET /api/patients/{patient_id}/transcripts
**Purpose:** Get all transcripts for a patient

**Response:**
```json
{
  "transcripts": [
    {
      "_id": "64f1a2b3c4d5e6f7g8h9i0j1",
      "room_name": "intake-2c799b83",
      "status": "completed",
      "created_at": "2025-10-13T23:05:03Z"
    }
  ],
  "count": 1
}
```

---

### 4. POST /api/transcripts/{transcript_id}/retry-notes
**Purpose:** Retry notes generation if failed

**Response:**
```json
{
  "success": true,
  "message": "Notes generation restarted"
}
```

---

## Template Structure

Example medical intake template:

```markdown
# MEDICAL INTAKE NOTES

## PATIENT INFORMATION
- Full Name: [Extract from conversation]
- Date of Birth: [Extract if mentioned]
- Contact Number: [Extract if mentioned]
- Email: [Extract if mentioned]

## APPOINTMENT DETAILS
- Provider Name: [Extract]
- Appointment Date/Time: [Extract]
- Reason for Visit: [Extract chief complaint]

## CHIEF COMPLAINT
[Primary reason for visit in patient's own words]

## HISTORY OF PRESENT ILLNESS
- Onset: [When did symptoms start]
- Duration: [How long symptoms have lasted]
- Severity: [Mild/Moderate/Severe - rate 1-10 if mentioned]
- Location: [Body part/area affected]
- Quality: [Sharp/Dull/Throbbing/Burning/Aching]
- Associated Symptoms: [Related symptoms]
- Aggravating Factors: [What makes it worse]
- Relieving Factors: [What makes it better]

## MEDICAL HISTORY
- Previous Conditions: [List any mentioned chronic conditions]
- Previous Surgeries: [List if any with dates]
- Previous Hospitalizations: [List if any with dates]
- Ongoing Treatments: [Current medical care]

## CURRENT MEDICATIONS
[List all medications with:
- Name
- Dosage
- Frequency
- Route of administration]

## ALLERGIES
- Medication Allergies: [List with reaction]
- Food Allergies: [List with reaction]
- Environmental Allergies: [List]
- Latex Allergy: [Yes/No]

## FAMILY HISTORY
- Heart Disease: [Yes/No - who]
- Diabetes: [Yes/No - who]
- Cancer: [Yes/No - type and who]
- Other Significant Conditions: [List]

## SOCIAL HISTORY
- Smoking Status: [Never/Former/Current - pack years if applicable]
- Alcohol Use: [Never/Occasional/Frequent - drinks per week]
- Drug Use: [Yes/No - type and frequency]
- Exercise: [Type and frequency]
- Occupation: [Current job]
- Living Situation: [Alone/With family/Assisted living]

## REVIEW OF SYSTEMS
- Constitutional: [Fever, chills, weight changes]
- HEENT: [Headaches, vision, hearing]
- Cardiovascular: [Chest pain, palpitations]
- Respiratory: [Shortness of breath, cough]
- Gastrointestinal: [Nausea, vomiting, diarrhea]
- Musculoskeletal: [Joint pain, muscle pain]
- Neurological: [Dizziness, numbness]
- Psychiatric: [Anxiety, depression]

## ADDITIONAL NOTES
[Any other relevant information from the conversation]

## CALL QUALITY METRICS
- Call Duration: [Minutes]
- Patient Cooperation: [Good/Fair/Poor]
- Information Completeness: [Complete/Partial/Incomplete]
- Technical Issues: [Yes/No - describe]
- Follow-up Needed: [Yes/No - what information is missing]
```

---

## Testing

### 1. Test Agent → Backend Connection

```bash
# Start backend
cd backend
python main.py

# In another terminal, test with curl
curl -X POST http://localhost:8000/api/transcripts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_secret_key" \
  -d '{
    "patient_id": "test123",
    "organization_id": "org123",
    "template_id": "template123",
    "room_name": "test-room",
    "transcript": {
      "messages": [
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "Hi"}
      ]
    }
  }'
```

### 2. Test Notes Generation

Check logs for:
```
✅ Transcript saved: 64f1a2b3...
🔄 Background task scheduled
🤖 Starting note generation
📋 Using template: General Medical Intake
📝 Calling LLM
✅ Notes generated
💾 Notes saved
```

### 3. Test Complete Flow

1. Start backend: `python backend/main.py`
2. Start agent: `python src/calling_agent.py dev`
3. Make a test call through LiveKit
4. Check backend logs for note generation
5. Query API: `GET /api/transcripts/{id}`

---

## Deployment

### Deploy Backend

**Option 1: Docker**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Option 2: Railway / Render / Heroku**
- Push `backend/` folder
- Set environment variables
- Deploy

### Deploy Agent

Keep agent deployment as is - just update `.env` with production `BACKEND_API_URL`

---

## Troubleshooting

### Issue: Notes not generating

**Check:**
1. Backend is running (`http://localhost:8000`)
2. Agent can reach backend (check `BACKEND_API_URL`)
3. API key is correct (`API_SECRET_KEY`)
4. LLM API key is valid (`OPENAI_API_KEY`)
5. Database is running (MongoDB)

**Logs to check:**
```
Agent: "✅ Transcript sent to backend"
Backend: "✅ Transcript saved: {id}"
Backend: "🔄 Background task scheduled"
Backend: "🤖 Starting note generation"
```

---

### Issue: Agent can't connect to backend

**Check:**
1. Backend URL is correct in `.env`
2. Backend is accessible from agent server
3. Firewall allows connection
4. Authorization header is correct

---

### Issue: LLM API errors

**Check:**
1. API key is valid
2. API has sufficient quota/credits
3. Model name is correct (`gpt-4o-mini` for OpenAI)
4. Network can reach LLM API

---

## Summary

**What you built:**
- ✅ Agent sends transcripts to backend automatically
- ✅ Backend saves transcripts to database
- ✅ Background task generates notes using LLM
- ✅ Notes saved and retrievable via API
- ✅ Can retry if generation fails
- ✅ Complete audit trail with timestamps

**Time to notes:** ~20 seconds after call ends

**Scalability:** Can handle multiple calls simultaneously

**Reliability:** Transcript saved even if notes fail

---

## Next Steps

1. ✅ Implement frontend to display transcripts and notes
2. ✅ Add webhook notifications when notes are ready
3. ✅ Implement custom templates per organization
4. ✅ Add notes editing capability
5. ✅ Export notes as PDF
6. ✅ Analytics dashboard for call metrics

---

## Support

For questions or issues:
- Check logs first (agent + backend)
- Review this documentation
- Test each component separately
- Check environment variables

---

**End of Documentation**
