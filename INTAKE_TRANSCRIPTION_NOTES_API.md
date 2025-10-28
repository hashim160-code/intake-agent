# Intake Transcription and Notes API

This document describes the API endpoints for managing transcription and notes data for intakes.

## Database Schema Changes

Two new columns have been added to the `intakes` table:

- `transcription` (JSONB, nullable) - Stores transcription data from intake calls
- `intake_notes` (JSONB, nullable) - Stores intake notes and additional information

## API Endpoints

### 1. Insert Transcription or Notes

**Endpoint:** `intakes.insertTranscriptionOrNotes`

**Method:** Mutation

**Description:** Insert or replace transcription and/or intake notes for a specific intake.

#### Request Body

```typescript
{
  intakeId: string; // UUID of the intake
  transcription?: any; // Optional JSONB data for transcription
  intakeNotes?: any; // Optional JSONB data for intake notes
}
```

#### Request Example

```json
{
  "intakeId": "123e4567-e89b-12d3-a456-426614174000",
  "transcription": {
    "items": [
      {
        "id": "item_21b10a6a55c7",
        "type": "message",
        "role": "assistant",
        "content": [
          "Hello, this is Sarah calling from Ali's Organization. I'm calling to collect some information for your upcoming Initial Consultation with Dr. Jane Smith on 07/25/2025 at 06:38 PM. Is this a good time to talk for a few minutes?"
        ],
        "interrupted": false
      },
      {
        "id": "item_96a070ccf619",
        "type": "message",
        "role": "user",
        "content": [
          "Yes."
        ],
        "interrupted": false,
        "transcript_confidence": 0.7270508
      }
    ]
  },
  "intakeNotes": {
    "summary": "Patient reported flu symptoms with chest congestion",
    "symptoms": ["cough", "chest congestion", "shortness of breath"],
    "duration": "10 days",
    "allergies": ["food", "smell", "dust"],
    "family_history": ["mother: liver cancer", "father: high blood pressure"],
    "past_surgery": "lower back surgery"
  }
}
```

#### Response Example

```json
{
  "success": true,
  "message": "Successfully updated intake transcription/notes",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "organization_id": "456e7890-e89b-12d3-a456-426614174001",
    "intake_title": "Intake 1",
    "patient_id": "789e0123-e89b-12d3-a456-426614174002",
    "intake_template_id": "012e3456-e89b-12d3-a456-426614174003",
    "intake_time": "2025-01-15T10:30:00Z",
    "sms_reminder": false,
    "retries": 0,
    "additional_instructions_for_ai": null,
    "created_at": "2025-01-15T10:00:00Z",
    "updated_at": "2025-01-15T10:35:00Z",
    "created_by": "345e6789-e89b-12d3-a456-426614174004",
    "scheduled_at": "2025-01-15T10:30:00Z",
    "encounter_id": null,
    "transcription": {
      "items": [
        {
          "id": "item_21b10a6a55c7",
          "type": "message",
          "role": "assistant",
          "content": [
            "Hello, this is Sarah calling from Ali's Organization..."
          ],
          "interrupted": false
        }
      ]
    },
    "intake_notes": {
      "summary": "Patient reported flu symptoms with chest congestion",
      "symptoms": ["cough", "chest congestion", "shortness of breath"],
      "duration": "10 days",
      "allergies": ["food", "smell", "dust"],
      "family_history": ["mother: liver cancer", "father: high blood pressure"],
      "past_surgery": "lower back surgery"
    }
  }
}
```

### 2. Update Transcription or Notes

**Endpoint:** `intakes.updateTranscriptionOrNotes`

**Method:** Mutation

**Description:** Update existing transcription and/or intake notes for a specific intake. This method merges new data with existing data for objects, or replaces for primitive values.

#### Request Body

```typescript
{
  intakeId: string; // UUID of the intake
  transcription?: any; // Optional JSONB data for transcription
  intakeNotes?: any; // Optional JSONB data for intake notes
}
```

#### Request Example

```json
{
  "intakeId": "123e4567-e89b-12d3-a456-426614174000",
  "transcription": {
    "additional_metadata": {
      "call_duration": "15 minutes",
      "quality_score": 0.95
    }
  },
  "intakeNotes": {
    "follow_up_required": true,
    "priority": "high"
  }
}
```

#### Response Example

```json
{
  "success": true,
  "message": "Successfully updated intake transcription/notes",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "organization_id": "456e7890-e89b-12d3-a456-426614174001",
    "intake_title": "Intake 1",
    "patient_id": "789e0123-e89b-12d3-a456-426614174002",
    "intake_template_id": "012e3456-e89b-12d3-a456-426614174003",
    "intake_time": "2025-01-15T10:30:00Z",
    "sms_reminder": false,
    "retries": 0,
    "additional_instructions_for_ai": null,
    "created_at": "2025-01-15T10:00:00Z",
    "updated_at": "2025-01-15T10:40:00Z",
    "created_by": "345e6789-e89b-12d3-a456-426614174004",
    "scheduled_at": "2025-01-15T10:30:00Z",
    "encounter_id": null,
    "transcription": {
      "items": [
        {
          "id": "item_21b10a6a55c7",
          "type": "message",
          "role": "assistant",
          "content": [
            "Hello, this is Sarah calling from Ali's Organization..."
          ],
          "interrupted": false
        }
      ],
      "additional_metadata": {
        "call_duration": "15 minutes",
        "quality_score": 0.95
      }
    },
    "intake_notes": {
      "summary": "Patient reported flu symptoms with chest congestion",
      "symptoms": ["cough", "chest congestion", "shortness of breath"],
      "duration": "10 days",
      "allergies": ["food", "smell", "dust"],
      "family_history": ["mother: liver cancer", "father: high blood pressure"],
      "past_surgery": "lower back surgery",
      "follow_up_required": true,
      "priority": "high"
    }
  }
}
```

## Error Responses

### 404 Not Found
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Intake not found"
  }
}
```

### 403 Forbidden
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Access denied to this intake"
  }
}
```

### 500 Internal Server Error
```json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "Failed to update intake transcription/notes"
  }
}
```

## Usage Notes

1. **Flexible Updates**: Both endpoints allow updating either `transcription`, `intakeNotes`, or both fields.

2. **Data Merging**: The `updateTranscriptionOrNotes` endpoint merges object data with existing data, while `insertTranscriptionOrNotes` replaces the entire field.

3. **JSONB Support**: Both fields support any valid JSON structure, making them highly flexible for different data formats.

4. **Organization Access**: Users can only update intakes within their selected organization.

5. **Validation**: The `intakeId` must be a valid UUID and the intake must exist in the user's organization.

## Sample Transcription Data Structure

Based on the provided sample, transcription data typically includes:

```json
{
  "items": [
    {
      "id": "unique_item_id",
      "type": "message",
      "role": "assistant" | "user",
      "content": ["message content"],
      "interrupted": boolean,
      "transcript_confidence": number // for user messages
    }
  ]
}
```

## Sample Intake Notes Data Structure

Intake notes can include various structured information:

```json
{
  "summary": "Brief summary of the intake",
  "symptoms": ["symptom1", "symptom2"],
  "duration": "duration description",
  "allergies": ["allergy1", "allergy2"],
  "family_history": ["condition1", "condition2"],
  "past_surgery": "surgery description",
  "follow_up_required": boolean,
  "priority": "high" | "medium" | "low",
  "additional_notes": "any additional information"
}
```
