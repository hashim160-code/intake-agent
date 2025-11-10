# ZScribe Intake Agent - API Integration Guide

## Overview

The ZScribe Intake Agent is an AI-powered voice agent that conducts medical intake calls via phone. This guide explains how to integrate with the API to trigger automated intake calls.

---

## Base URL

```
https://intake-api-292492747795.us-central1.run.app
```

---

## Authentication

Currently, the API does not require authentication. _(Note: Consider adding authentication for production use)_

---

## Endpoint: Trigger Intake Call

### `POST /intake-calls`

Triggers an automated intake call to a patient's phone number.

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `phone_number` | string | Yes | Patient's phone number in E.164 format (e.g., "+19712656795") |
| `template_id` | string | Yes | UUID of the intake template to use for questions |
| `organization_id` | string | Yes | UUID of the healthcare organization |
| `patient_id` | string | Yes | UUID of the patient receiving the call |
| `intake_id` | string | Yes | UUID of the intake session for tracking |

**Example Request:**

```bash
curl -X POST https://intake-api-292492747795.us-central1.run.app/intake-calls \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+19712656795",
    "template_id": "67c663aa-15ab-4fb0-bf3e-7110405737ef",
    "organization_id": "0da4a59a-275f-4f2d-92f0-5e0c60b0f1da",
    "patient_id": "9092481d-0535-42ca-92ad-7c3a595f9ced",
    "intake_id": "2b24fa8d-d7e0-4515-82aa-83408529c352"
  }'
```

**Example Request (JavaScript/Node.js):**

```javascript
const response = await fetch('https://intake-api-292492747795.us-central1.run.app/intake-calls', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    phone_number: '+19712656795',
    template_id: '67c663aa-15ab-4fb0-bf3e-7110405737ef',
    organization_id: '0da4a59a-275f-4f2d-92f0-5e0c60b0f1da',
    patient_id: '9092481d-0535-42ca-92ad-7c3a595f9ced',
    intake_id: '2b24fa8d-d7e0-4515-82aa-83408529c352'
  })
});

const data = await response.json();
console.log(data);
```

**Example Request (Python):**

```python
import requests

url = "https://intake-api-292492747795.us-central1.run.app/intake-calls"

payload = {
    "phone_number": "+19712656795",
    "template_id": "67c663aa-15ab-4fb0-bf3e-7110405737ef",
    "organization_id": "0da4a59a-275f-4f2d-92f0-5e0c60b0f1da",
    "patient_id": "9092481d-0535-42ca-92ad-7c3a595f9ced",
    "intake_id": "2b24fa8d-d7e0-4515-82aa-83408529c352"
}

response = requests.post(url, json=payload)
print(response.json())
```

#### Response

**Success Response (202 Accepted):**

```json
{
  "status": "queued",
  "room_name": "intake-call-2b24fa8d",
  "dispatch_id": "DP_XxYyZzAaBbCc",
  "metadata": {
    "template_id": "67c663aa-15ab-4fb0-bf3e-7110405737ef",
    "organization_id": "0da4a59a-275f-4f2d-92f0-5e0c60b0f1da",
    "patient_id": "9092481d-0535-42ca-92ad-7c3a595f9ced",
    "intake_id": "2b24fa8d-d7e0-4515-82aa-83408529c352"
  },
  "agent_name": "intake-agent"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Current status of the call (always "queued" initially) |
| `room_name` | string | LiveKit room name for this call session |
| `dispatch_id` | string | Unique identifier for the LiveKit dispatch |
| `metadata` | object | Metadata associated with this call |
| `agent_name` | string | Name of the AI agent handling the call |

**Error Response (400 Bad Request):**

```json
{
  "detail": [
    {
      "loc": ["body", "phone_number"],
      "msg": "ensure this value has at least 7 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

**Error Response (502 Bad Gateway):**

```json
{
  "detail": "Failed to dispatch intake call"
}
```

---

## Phone Number Format

The `phone_number` must be in **E.164 format**:

- **Format:** `+[country code][phone number]`
- **Example (US):** `+19712656795`
- **Example (UK):** `+447700900123`

**Invalid formats:**
- ❌ `9712656795` (missing country code and +)
- ❌ `(971) 265-6795` (contains formatting characters)
- ❌ `+1 971-265-6795` (contains spaces and dashes)

**Valid formats:**
- ✅ `+19712656795`
- ✅ `+447700900123`

---

## Health Check Endpoint

### `GET /health`

Returns the health status of the intake-api service.

**Example Request:**

```bash
curl https://intake-api-292492747795.us-central1.run.app/health
```

**Response:**

```json
{
  "status": "ok"
}
```

---

## Call Flow

1. **Trigger Call**: Your system makes a POST request to `/intake-calls` with patient and template information
2. **Dispatch Created**: The API creates a LiveKit dispatch and queues the outbound call
3. **Call Initiated**: LiveKit dials the patient's phone number via SIP trunk
4. **Agent Answers**: When patient answers, the AI agent greets them with a personalized message
5. **Dynamic Questions**: Agent asks questions from the template with personalized context
6. **Transcript Saved**: After the call, the full transcript is automatically saved to the database

---

## Data Requirements

Before triggering an intake call, ensure the following data exists in your database:

### 1. Template
- Must exist in the `templates` table
- Should contain:
  - `template_name`: Name of the intake form
  - `instructions_for_ai`: Guidance for the AI agent
  - `questions`: Array of questions to ask

### 2. Organization
- Must exist in the `organizations` table
- Should contain:
  - `name`: Organization name (used in greeting)

### 3. Patient
- Must exist in the `patients` table
- Should contain:
  - `full_name`: Patient's name (used in greeting)

### 4. Intake Session
- Create a new record in the `intakes` table with a unique `id`
- This `id` should be passed as `intake_id` in the API request
- The transcript will be saved to this record's `transcription` field after the call

---

## Example Integration Workflow

```javascript
// Step 1: Create intake session in your database
const intake = await db.intakes.create({
  id: generateUUID(),
  patient_id: patient.id,
  organization_id: organization.id,
  template_id: template.id,
  status: 'pending',
  created_at: new Date()
});

// Step 2: Trigger the intake call
const response = await fetch('https://intake-api-292492747795.us-central1.run.app/intake-calls', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    phone_number: patient.phone_number,
    template_id: template.id,
    organization_id: organization.id,
    patient_id: patient.id,
    intake_id: intake.id
  })
});

const result = await response.json();

// Step 3: Update intake session with dispatch info
await db.intakes.update(intake.id, {
  dispatch_id: result.dispatch_id,
  room_name: result.room_name,
  status: 'in_progress'
});

// Step 4: The transcript will be automatically saved to intake.transcription after the call
```

---

## Transcript Storage

After the call completes, the full conversation transcript is automatically saved to the `intakes` table:

```sql
UPDATE intakes
SET transcription = {
  "items": [
    {
      "role": "assistant",
      "content": ["Hello John, this is ZScribe Intake Assistant..."]
    },
    {
      "role": "user",
      "content": ["Yes, this is a good time."]
    },
    ...
  ]
}
WHERE id = '<intake_id>';
```

---

## Error Handling

### Common Error Scenarios

1. **Invalid Phone Number**
   - Status: 400 Bad Request
   - Solution: Ensure phone number is in E.164 format

2. **Missing Required Fields**
   - Status: 422 Unprocessable Entity
   - Solution: Verify all required fields are included

3. **LiveKit Dispatch Failed**
   - Status: 502 Bad Gateway
   - Solution: Check LiveKit credentials and SIP trunk configuration

4. **Template/Patient/Organization Not Found**
   - The call will proceed with default/fallback values
   - Check logs for warnings about missing data

---

## Rate Limits

Currently, there are no rate limits enforced. However, for production use, consider:
- Maximum 10 concurrent calls per organization
- Maximum 100 calls per hour per organization

---

## Support

For technical support or questions about the integration:
- **Documentation**: This file
- **API Endpoint**: `https://intake-api-292492747795.us-central1.run.app`
- **Health Check**: `https://intake-api-292492747795.us-central1.run.app/health`

---

## Changelog

### v0.1.0 (Current)
- Initial API release
- Support for triggering intake calls via POST /intake-calls
- Automatic transcript saving to database
- Dynamic template-based questioning
- Personalized patient greetings
