# Call Recording Implementation Guide for Backend Team

## Overview

This document explains how to implement call recording storage and playback for ZScribe intake calls.

**Goal**: Store call recordings from Telnyx in Supabase Storage and display them in the ZScribe UI with an audio player.

---

## How It Works (High-Level Flow)

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│ 1. Call     │───▶│ 2. Telnyx   │───▶│ 3. Webhook   │───▶│ 4. Backend   │
│    Happens  │    │    Records  │    │    Fires     │    │    Saves ID  │
└─────────────┘    └─────────────┘    └──────────────┘    └──────────────┘
                                                                    │
                                                                    ▼
┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│ 8. UI Shows │◀───│ 7. Save URL │◀───│ 6. Upload to │◀───│ 5. Fetch from│
│    Player   │    │    to DB    │    │    Supabase  │    │    Telnyx    │
└─────────────┘    └─────────────┘    └──────────────┘    └──────────────┘
```

---

## Complete Step-by-Step Flow

### **Step 1: Call Happens** ✅ (Already Working)

**What happens:**
- User clicks "Make Call" in ZScribe UI
- Backend calls intake API: `POST /make-call`
- Agent makes call to patient via Telnyx
- Call is automatically recorded by Telnyx

**Database state:**
```sql
-- intakes table
id: "uuid-1234"
room_name: "intake-abc123"
patient_id: "patient-uuid"
recording_id: NULL         ❌ Not yet
recording_url: NULL        ❌ Not yet
```

**✅ No action needed - this already works**

---

### **Step 2: Call is Recorded** 🎙️

**What happens:**
- Telnyx automatically records the entire call
- Recording is stored on Telnyx's servers
- We don't need to do anything here

**✅ No action needed - Telnyx handles this automatically**

---

### **Step 3: Call Ends & Recording is Ready** ☎️

**What happens:**
- Call ends
- Telnyx processes the recording (WAV/MP3 conversion)
- **This takes 30 seconds to 2 minutes after call ends**
- Once ready, Telnyx sends a webhook

---

### **Step 4: Telnyx Sends Webhook** 📨

**⚠️ ACTION REQUIRED: You need to implement this**

**What happens:**
Telnyx sends HTTP POST request to your webhook URL with this payload:

```json
{
  "data": {
    "event_type": "call.recording.saved",
    "id": "event-uuid",
    "occurred_at": "2025-11-19T10:34:00.000Z",
    "payload": {
      "recording_id": "d8991cb0-c531-11f0-81a3-02420aef38a0",
      "call_control_id": "v2:T02YXJzaGFsbCBuZXZlciBkaWU",
      "call_session_id": "428c31b6-7082-4aab-1234",
      "call_leg_id": "leg-abc123",
      "from_number": "+19712656795",
      "to_number": "+1234567890",
      "duration_millis": 180000,
      "channels": "single",
      "recording_started_at": "2025-11-19T10:30:00.000Z",
      "recording_ended_at": "2025-11-19T10:33:00.000Z",
      "recording_urls": {
        "wav": "https://storage.telnyx.com/recordings/d8991cb0-c531-11f0-81a3-02420aef38a0.wav",
        "mp3": "https://storage.telnyx.com/recordings/d8991cb0-c531-11f0-81a3-02420aef38a0.mp3"
      },
      "status": "completed"
    },
    "record_type": "event"
  },
  "meta": {
    "attempt": 1,
    "delivered_to": "https://your-backend.com/api/webhooks/telnyx/recording"
  }
}
```

**Key fields you need:**
- `recording_id`: Telnyx's unique ID for this recording
- `to_number`: Patient's phone number (for matching to intake)
- `duration_millis`: Recording duration in milliseconds
- `occurred_at`: When the webhook was sent

---

### **Step 5: Backend Receives Webhook & Saves recording_id**

**⚠️ ACTION REQUIRED: You need to implement this**

**Endpoint to create:**
```
POST /api/webhooks/telnyx/recording
```

**Implementation (Node.js/TypeScript example):**

```typescript
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY! // Use service role key for server-side
);

app.post('/api/webhooks/telnyx/recording', async (req, res) => {
  try {
    const event = req.body;

    // Verify this is a recording saved event
    if (event.data.event_type !== 'call.recording.saved') {
      return res.status(200).send('Ignored - not a recording event');
    }

    const payload = event.data.payload;

    // Extract data
    const recordingId = payload.recording_id;
    const toNumber = payload.to_number;
    const duration = Math.floor(payload.duration_millis / 1000); // Convert to seconds
    const occurredAt = event.data.occurred_at;

    console.log(`📞 Recording webhook received for ${toNumber}`);
    console.log(`📝 Recording ID: ${recordingId}`);

    // STEP 1: Find the intake record
    // Match by patient phone number + timestamp (within 10 minutes)
    const tenMinutesAgo = new Date(new Date(occurredAt).getTime() - 10 * 60 * 1000);
    const tenMinutesLater = new Date(new Date(occurredAt).getTime() + 10 * 60 * 1000);

    // First, find patient by phone number
    const { data: patient, error: patientError } = await supabase
      .from('patients')
      .select('id')
      .eq('phone', toNumber)
      .single();

    if (patientError || !patient) {
      console.error(`❌ Patient not found for phone: ${toNumber}`);
      return res.status(200).send('Patient not found');
    }

    // Then find recent intake for this patient
    const { data: intake, error: intakeError } = await supabase
      .from('intakes')
      .select('id, room_name')
      .eq('patient_id', patient.id)
      .gte('created_at', tenMinutesAgo.toISOString())
      .lte('created_at', tenMinutesLater.toISOString())
      .order('created_at', { ascending: false })
      .limit(1)
      .single();

    if (intakeError || !intake) {
      console.error(`❌ Intake not found for patient ${patient.id}`);
      return res.status(200).send('Intake not found');
    }

    console.log(`✅ Matched to intake: ${intake.id}`);

    // STEP 2: Update intake with recording_id
    const { error: updateError } = await supabase
      .from('intakes')
      .update({
        recording_id: recordingId,
        recording_duration: duration,
        updated_at: new Date().toISOString()
      })
      .eq('id', intake.id);

    if (updateError) {
      console.error('❌ Failed to update intake:', updateError);
      return res.status(500).send('Failed to update intake');
    }

    console.log(`✅ Recording ID saved to database`);

    // STEP 3: Trigger background job to fetch & upload recording
    // (Using Bull Queue example - adjust based on your queue system)
    await recordingQueue.add('process-recording', {
      intakeId: intake.id,
      recordingId: recordingId
    });

    console.log(`✅ Background job queued for recording upload`);

    res.status(200).send('OK');
  } catch (error) {
    console.error('❌ Webhook error:', error);
    res.status(500).send('Internal server error');
  }
});
```

**Database after this step:**
```sql
-- intakes table
id: "uuid-1234"
room_name: "intake-abc123"
recording_id: "d8991cb0-c531-11f0-81a3-02420aef38a0"  ✅ SAVED!
recording_duration: 180
recording_url: NULL  ❌ Still processing...
```

---

### **Step 6: Background Job Fetches Recording from Telnyx**

**⚠️ ACTION REQUIRED: You need to implement this**

**Background job processor (Bull Queue example):**

```typescript
import fetch from 'node-fetch';

// Queue definition
const recordingQueue = new Queue('recording-processing', {
  connection: redisConfig
});

// Process jobs
recordingQueue.process('process-recording', async (job) => {
  const { intakeId, recordingId } = job.data;

  console.log(`📥 Processing recording ${recordingId} for intake ${intakeId}`);

  try {
    // STEP 1: Fetch recording from Telnyx API
    const recordingFile = await fetchRecordingFromTelnyx(recordingId);

    console.log(`✅ Recording fetched from Telnyx (${recordingFile.byteLength} bytes)`);

    // STEP 2: Upload to Supabase Storage
    const fileName = `${intakeId}.wav`;
    const { error: uploadError } = await supabase.storage
      .from('call-recordings')
      .upload(fileName, recordingFile, {
        contentType: 'audio/wav',
        upsert: false
      });

    if (uploadError) {
      throw new Error(`Upload failed: ${uploadError.message}`);
    }

    console.log(`✅ Recording uploaded to Supabase Storage: ${fileName}`);

    // STEP 3: Get public URL
    const { data: urlData } = supabase.storage
      .from('call-recordings')
      .getPublicUrl(fileName);

    const publicUrl = urlData.publicUrl;
    console.log(`✅ Public URL: ${publicUrl}`);

    // STEP 4: Update database with recording URL
    const { error: updateError } = await supabase
      .from('intakes')
      .update({
        recording_url: publicUrl,
        recording_migrated_at: new Date().toISOString()
      })
      .eq('id', intakeId);

    if (updateError) {
      throw new Error(`Database update failed: ${updateError.message}`);
    }

    console.log(`✅ Database updated with recording URL`);

    // STEP 5: Delete from Telnyx to save costs (optional)
    await deleteRecordingFromTelnyx(recordingId);
    console.log(`✅ Recording deleted from Telnyx`);

    console.log(`🎉 Recording processing complete!`);
  } catch (error) {
    console.error(`❌ Error processing recording:`, error);
    throw error; // This will trigger job retry
  }
});

// Helper function: Fetch recording from Telnyx
async function fetchRecordingFromTelnyx(recordingId: string): Promise<Buffer> {
  const TELNYX_API_KEY = process.env.TELNYX_API_KEY;

  // Step 1: Get recording metadata
  const metadataResponse = await fetch(
    `https://api.telnyx.com/v2/recordings/${recordingId}`,
    {
      headers: {
        'Authorization': `Bearer ${TELNYX_API_KEY}`,
        'Accept': 'application/json'
      }
    }
  );

  if (!metadataResponse.ok) {
    throw new Error(`Telnyx API error: ${metadataResponse.statusText}`);
  }

  const metadata = await metadataResponse.json();
  const downloadUrl = metadata.data.recording_urls.wav; // or .mp3

  console.log(`📥 Downloading from: ${downloadUrl}`);

  // Step 2: Download the actual recording file
  const fileResponse = await fetch(downloadUrl);

  if (!fileResponse.ok) {
    throw new Error(`Download failed: ${fileResponse.statusText}`);
  }

  const arrayBuffer = await fileResponse.arrayBuffer();
  return Buffer.from(arrayBuffer);
}

// Helper function: Delete recording from Telnyx
async function deleteRecordingFromTelnyx(recordingId: string): Promise<void> {
  const TELNYX_API_KEY = process.env.TELNYX_API_KEY;

  const response = await fetch(
    `https://api.telnyx.com/v2/recordings/${recordingId}`,
    {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${TELNYX_API_KEY}`
      }
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to delete recording: ${response.statusText}`);
  }
}
```

**Database after this step:**
```sql
-- intakes table
id: "uuid-1234"
room_name: "intake-abc123"
recording_id: "d8991cb0-c531-11f0-81a3-02420aef38a0"
recording_duration: 180
recording_url: "https://qyythlrvpaqfmivcndqv.supabase.co/storage/v1/object/public/call-recordings/uuid-1234.wav"  ✅ SAVED!
recording_migrated_at: "2025-11-19T10:35:00Z"
```

---

### **Step 7: Frontend Displays Audio Player**

**Frontend code (React/Next.js example):**

```typescript
interface Intake {
  id: string;
  recording_url: string | null;
  recording_duration: number | null;
  recording_id: string | null;
}

function RecordingPlayer({ intake }: { intake: Intake }) {
  // Case 1: Recording is available
  if (intake.recording_url) {
    const minutes = Math.floor(intake.recording_duration! / 60);
    const seconds = intake.recording_duration! % 60;

    return (
      <div className="recording-section">
        <h3>Call Recording</h3>
        <audio
          controls
          src={intake.recording_url}
          preload="metadata"
          className="w-full"
        >
          Your browser doesn't support audio playback.
        </audio>
        <p className="text-sm text-gray-600">
          Duration: {minutes}:{String(seconds).padStart(2, '0')}
        </p>
      </div>
    );
  }

  // Case 2: Recording is being processed
  if (intake.recording_id) {
    return (
      <div className="recording-section">
        <p className="text-gray-600">⏳ Recording is being processed...</p>
        <p className="text-sm text-gray-500">This usually takes 1-2 minutes</p>
      </div>
    );
  }

  // Case 3: No recording available
  return (
    <div className="recording-section">
      <p className="text-gray-400">No recording available</p>
    </div>
  );
}
```

**User sees:**
```
┌─────────────────────────────────────────────┐
│ Call Recording                               │
│ ▶️ ━━━━━━━━━━━━━━━━━━━━━━━━━━ 00:00 / 03:00│
│ 🔊 ──────────────────────────── 🔇          │
│ Duration: 3:00                               │
└─────────────────────────────────────────────┘
```

---

## Database Schema Changes Required

```sql
-- Add new columns to intakes table
ALTER TABLE intakes
ADD COLUMN recording_id TEXT,
ADD COLUMN recording_url TEXT,
ADD COLUMN recording_duration INTEGER,
ADD COLUMN recording_migrated_at TIMESTAMPTZ;

-- Add indexes for better performance
CREATE INDEX idx_intakes_recording_id ON intakes(recording_id);

-- Add comments for documentation
COMMENT ON COLUMN intakes.recording_id IS 'Telnyx recording UUID';
COMMENT ON COLUMN intakes.recording_url IS 'Supabase Storage public URL for playback';
COMMENT ON COLUMN intakes.recording_duration IS 'Recording duration in seconds';
COMMENT ON COLUMN intakes.recording_migrated_at IS 'Timestamp when recording was uploaded to Supabase';
```

---

## Supabase Storage Setup

### **Step 1: Create Storage Bucket**

Go to Supabase Dashboard → Storage → New Bucket

**Settings:**
- Name: `call-recordings`
- Public: `false` (recordings should be private)
- File size limit: `50 MB`
- Allowed MIME types: `audio/wav, audio/mp3, audio/mpeg`

**Or via API:**
```typescript
const { data, error } = await supabase.storage.createBucket('call-recordings', {
  public: false,
  fileSizeLimit: 52428800, // 50MB
  allowedMimeTypes: ['audio/wav', 'audio/mp3', 'audio/mpeg']
});
```

### **Step 2: Set up RLS Policies**

```sql
-- Allow authenticated users to read recordings from their own organization
CREATE POLICY "Users can access their org's recordings"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'call-recordings' AND
  auth.role() = 'authenticated' AND
  EXISTS (
    SELECT 1 FROM intakes
    WHERE recording_url LIKE '%' || name || '%'
    AND organization_id = (auth.jwt() ->> 'organization_id')::uuid
  )
);
```

---

## Telnyx Webhook Setup

### **Step 1: Configure Webhook in Telnyx Portal**

1. Login to [Telnyx Portal](https://portal.telnyx.com)
2. Go to **Developer → Webhooks**
3. Click **Add Webhook**
4. Configure:
   ```
   URL: https://your-backend.com/api/webhooks/telnyx/recording
   Events: ✅ Call Recording Saved
   HTTP Method: POST
   Failover URL: (optional backup URL)
   ```
5. Save

### **Step 2: Verify Webhook Signature (Recommended)**

```typescript
import crypto from 'crypto';

function verifyTelnyxSignature(req: Request): boolean {
  const signature = req.headers['telnyx-signature-ed25519'];
  const timestamp = req.headers['telnyx-timestamp'];
  const body = JSON.stringify(req.body);

  const WEBHOOK_SECRET = process.env.TELNYX_WEBHOOK_SECRET;

  const signedPayload = `${timestamp}|${body}`;
  const expectedSignature = crypto
    .createHmac('sha256', WEBHOOK_SECRET)
    .update(signedPayload)
    .digest('hex');

  return signature === expectedSignature;
}

// Use in webhook endpoint
app.post('/api/webhooks/telnyx/recording', (req, res) => {
  if (!verifyTelnyxSignature(req)) {
    return res.status(401).send('Invalid signature');
  }
  // ... rest of webhook logic
});
```

---

## Environment Variables Required

Add these to your `.env` file:

```bash
# Telnyx API
TELNYX_API_KEY=your_telnyx_api_key_here
TELNYX_WEBHOOK_SECRET=your_webhook_secret_here

# Supabase
SUPABASE_URL=https://qyythlrvpaqfmivcndqv.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# Redis (for queue)
REDIS_URL=redis://localhost:6379
```

---

## Testing

### **Test 1: Webhook Reception**

```bash
# Simulate Telnyx webhook with curl
curl -X POST http://localhost:3000/api/webhooks/telnyx/recording \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "event_type": "call.recording.saved",
      "occurred_at": "2025-11-19T10:34:00Z",
      "payload": {
        "recording_id": "test-recording-id",
        "to_number": "+1234567890",
        "duration_millis": 180000,
        "recording_urls": {
          "wav": "https://example.com/test.wav"
        }
      }
    }
  }'
```

### **Test 2: Recording Upload**

```typescript
// Test Telnyx API connection
async function testTelnyxAPI() {
  const response = await fetch('https://api.telnyx.com/v2/recordings', {
    headers: {
      'Authorization': `Bearer ${process.env.TELNYX_API_KEY}`
    }
  });
  console.log('Telnyx API Status:', response.status);
}
```

### **Test 3: Supabase Upload**

```typescript
// Test Supabase Storage
async function testSupabaseUpload() {
  const testFile = Buffer.from('test audio data');
  const { error } = await supabase.storage
    .from('call-recordings')
    .upload('test.wav', testFile);

  if (error) {
    console.error('Upload failed:', error);
  } else {
    console.log('✅ Upload successful');
  }
}
```

---

## Error Handling & Retry Logic

### **Webhook Failures**

Telnyx will retry failed webhooks:
- Retry 1: After 1 minute
- Retry 2: After 5 minutes
- Retry 3: After 15 minutes

Make sure your webhook endpoint returns:
- `200 OK` for successful processing
- `500` or timeout for failures (will trigger retry)

### **Background Job Retries**

```typescript
recordingQueue.process('process-recording', async (job) => {
  // Configure retries
  job.attemptsMade; // Current attempt number

  // Retry up to 3 times with exponential backoff
  if (job.attemptsMade < 3) {
    // Retry logic
  } else {
    // Send alert - manual intervention needed
    await sendAlert(`Recording processing failed after 3 attempts: ${job.data.recordingId}`);
  }
});
```

---

## Monitoring & Logging

### **Key Metrics to Track**

1. **Webhook success rate**
   - How many webhooks received vs expected
2. **Processing time**
   - Time from webhook to recording URL available
3. **Storage costs**
   - Supabase storage usage
4. **Failed recordings**
   - Recordings that couldn't be processed

### **Logging Example**

```typescript
// Use structured logging
logger.info('Recording webhook received', {
  recordingId,
  intakeId,
  patientPhone: toNumber,
  duration: duration,
  timestamp: new Date().toISOString()
});

logger.error('Recording processing failed', {
  recordingId,
  intakeId,
  error: error.message,
  attempt: job.attemptsMade
});
```

---

## Timeline Estimate

| Task | Estimated Time | Status |
|------|---------------|--------|
| Database migration | 30 minutes | ⏳ Todo |
| Supabase bucket setup | 15 minutes | ⏳ Todo |
| Webhook endpoint | 2-3 hours | ⏳ Todo |
| Background job processor | 3-4 hours | ⏳ Todo |
| Testing & debugging | 2-3 hours | ⏳ Todo |
| Frontend integration | 1-2 hours | ⏳ Todo |
| **Total** | **~10-14 hours** | |

---

## Summary - What You Need to Build

### **Backend Tasks:**

1. ☐ **Database Migration**
   - Add `recording_id`, `recording_url`, `recording_duration`, `recording_migrated_at` columns

2. ☐ **Supabase Storage**
   - Create `call-recordings` bucket
   - Set up RLS policies

3. ☐ **Webhook Endpoint**
   - Create `/api/webhooks/telnyx/recording`
   - Match webhook to intake by phone + timestamp
   - Save `recording_id` to database
   - Queue background job

4. ☐ **Background Job**
   - Fetch recording from Telnyx API
   - Upload to Supabase Storage
   - Save `recording_url` to database
   - Delete from Telnyx (optional)

5. ☐ **Configure Telnyx**
   - Set up webhook in Telnyx portal

### **Frontend Tasks:**

1. ☐ **Audio Player Component**
   - Display audio player if `recording_url` exists
   - Show "Processing..." if only `recording_id` exists
   - Show "No recording" if neither exists

---

## Questions?

**Contact:** Your AI Agent Team

**Last Updated:** November 19, 2025
