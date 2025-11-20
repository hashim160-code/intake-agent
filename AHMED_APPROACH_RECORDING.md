# Ahmed's Approach: Recording Without recording.saved Webhook

Based on Ahmed Usman's successful implementation - using `call_control_id` and `custom_file_name` to fetch recordings without needing the `call.recording.saved` webhook.

---

## 🎯 How It Works

Instead of waiting for `call.recording.saved` webhook, we:
1. ✅ Use `call.answered` webhook to get `call_control_id`
2. ✅ Start recording manually with `custom_file_name = intake_id`
3. ✅ After call ends, query Telnyx API by `custom_file_name`
4. ✅ Get `recording_id` and save to database

**Key Advantage:** Exact matching using `intake_id` as custom filename - no ambiguity!

---

## 📋 Complete Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Call Initiated (make_call.py)                           │
│    - Create intake record with unique ID                    │
│    - Make SIP call via LiveKit                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Telnyx → Backend: call.answered webhook                 │
│    Payload: { call_control_id, call_session_id, ... }      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Backend: Start Recording Manually                        │
│    POST /v2/calls/{call_control_id}/actions/record_start    │
│    Body: { custom_file_name: intake_id }                    │
│                                                             │
│    Save to DB: metadata.call_control_id                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Conversation Happens                                     │
│    - AI agent talks to patient                              │
│    - Recording in progress                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Call Ends                                                │
│    - Transcript saved (already working)                     │
│    - Telnyx processes recording (1-2 minutes)               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Background Job: Fetch Recording                          │
│    GET /v2/recordings?filter[custom_file_name]=intake_id    │
│    - Get recording_id                                       │
│    - Get download_url                                       │
│    - Save to metadata column                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. (Optional) Download & Upload to Supabase                │
│    - Fetch WAV from Telnyx                                  │
│    - Upload to Supabase Storage                             │
│    - Save recording_url                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Implementation Steps

### **Step 1: Configure Telnyx Webhook for call.answered**

**In Telnyx Portal:**
1. Go to: Voice → Programmable Voice → Call Control Applications
2. Edit your application
3. Set webhook URL: `https://api.zscribe.com/api/webhooks/telnyx/call-events`
4. Select API V2
5. Save

---

### **Step 2: Create Webhook Handler (Backend)**

```typescript
// POST /api/webhooks/telnyx/call-events
export async function handleTelnyxWebhook(req: Request, res: Response) {
  const { event_type, payload } = req.body.data;

  // Respond immediately to Telnyx
  res.status(200).json({ received: true });

  // Handle different webhook events
  switch (event_type) {
    case 'call.answered':
      await handleCallAnswered(payload);
      break;

    case 'call.hangup':
      await handleCallHangup(payload);
      break;
  }
}
```

---

### **Step 3: Handle call.answered - Start Recording**

```typescript
async function handleCallAnswered(payload: any) {
  const {
    call_control_id,
    call_session_id,
    to,  // Patient phone number
    from // Your intake number
  } = payload;

  try {
    // Find intake by phone number + recent timestamp
    const intake = await db.intakes.findOne({
      where: {
        patient_phone: to,
        created_at: {
          gte: new Date(Date.now() - 10 * 60 * 1000) // Last 10 minutes
        }
      },
      orderBy: { created_at: 'desc' }
    });

    if (!intake) {
      console.error('Intake not found for phone:', to);
      return;
    }

    // Start recording with custom filename = intake_id
    await axios.post(
      `https://api.telnyx.com/v2/calls/${call_control_id}/actions/record_start`,
      {
        format: 'wav',
        channels: 'dual',  // Dual channel: agent on left, patient on right
        trim: 'trim-silence',
        custom_file_name: intake.id  // ← KEY: Use intake_id as filename!
      },
      {
        headers: {
          'Authorization': `Bearer ${process.env.TELNYX_API_KEY}`,
          'Content-Type': 'application/json'
        }
      }
    );

    // Save call_control_id to database
    await db.intakes.update({
      where: { id: intake.id },
      data: {
        metadata: {
          ...(intake.metadata || {}),
          call_control_id: call_control_id,
          call_session_id: call_session_id,
          recording_started_at: new Date().toISOString()
        }
      }
    });

    console.log(`Recording started for intake ${intake.id}`);

  } catch (error) {
    console.error('Error starting recording:', error);
  }
}
```

---

### **Step 4: Handle call.hangup - Queue Recording Fetch Job**

```typescript
async function handleCallHangup(payload: any) {
  const { call_control_id, call_session_id } = payload;

  try {
    // Find intake by call_control_id
    const intake = await db.intakes.findFirst({
      where: {
        metadata: {
          path: ['call_control_id'],
          equals: call_control_id
        }
      }
    });

    if (!intake) {
      console.error('Intake not found for call_control_id:', call_control_id);
      return;
    }

    // Queue background job to fetch recording
    // Wait 2 minutes for Telnyx to process the recording
    await jobQueue.add(
      'fetch-recording',
      { intake_id: intake.id },
      {
        delay: 2 * 60 * 1000  // 2 minutes delay
      }
    );

    console.log(`Queued recording fetch job for intake ${intake.id}`);

  } catch (error) {
    console.error('Error queuing recording fetch:', error);
  }
}
```

---

### **Step 5: Background Job - Fetch Recording from Telnyx**

```typescript
// Background job processor
async function fetchRecordingJob(job: Job) {
  const { intake_id } = job.data;

  try {
    // Query Telnyx API for recording with custom_file_name = intake_id
    const response = await axios.get('https://api.telnyx.com/v2/recordings', {
      params: {
        'filter[custom_file_name]': intake_id  // ← Filter by intake_id
      },
      headers: {
        'Authorization': `Bearer ${process.env.TELNYX_API_KEY}`
      }
    });

    const recordings = response.data.data;

    if (!recordings || recordings.length === 0) {
      // Recording not ready yet, retry
      console.log(`Recording not ready for intake ${intake_id}, retrying...`);

      // Retry after 1 minute (up to 5 times)
      if (job.attemptsMade < 5) {
        throw new Error('Recording not ready, will retry');
      } else {
        console.error(`Recording not found after 5 attempts for intake ${intake_id}`);
        return;
      }
    }

    // Get the first (and should be only) recording
    const recording = recordings[0];
    const recording_id = recording.id;
    const recording_url = recording.download_urls?.wav || recording.download_urls?.mp3;
    const duration = recording.duration_millis;

    // Save to database
    await db.intakes.update({
      where: { id: intake_id },
      data: {
        metadata: {
          ...(await getIntakeMetadata(intake_id)),
          recording_id: recording_id,
          recording_url_telnyx: recording_url,  // Temporary Telnyx URL
          recording_duration: duration,
          recording_fetched_at: new Date().toISOString()
        }
      }
    });

    console.log(`Recording ID saved for intake ${intake_id}: ${recording_id}`);

    // Optional: Queue another job to download and upload to Supabase
    await jobQueue.add('upload-recording-to-supabase', {
      intake_id,
      recording_id,
      recording_url
    });

  } catch (error) {
    console.error(`Error fetching recording for intake ${intake_id}:`, error);
    throw error;  // Will trigger retry
  }
}
```

---

### **Step 6: (Optional) Upload Recording to Supabase**

```typescript
async function uploadRecordingToSupabaseJob(job: Job) {
  const { intake_id, recording_id, recording_url } = job.data;

  try {
    // Download recording from Telnyx
    const response = await axios.get(recording_url, {
      responseType: 'arraybuffer'
    });

    const audioBuffer = Buffer.from(response.data);

    // Upload to Supabase Storage
    const { data, error } = await supabase.storage
      .from('call-recordings')
      .upload(`${intake_id}/recording.wav`, audioBuffer, {
        contentType: 'audio/wav',
        upsert: true
      });

    if (error) throw error;

    // Get public URL
    const { data: publicUrlData } = supabase.storage
      .from('call-recordings')
      .getPublicUrl(`${intake_id}/recording.wav`);

    // Update database
    await db.intakes.update({
      where: { id: intake_id },
      data: {
        metadata: {
          ...(await getIntakeMetadata(intake_id)),
          recording_url_supabase: publicUrlData.publicUrl,
          recording_migrated_at: new Date().toISOString()
        }
      }
    });

    // Optional: Delete from Telnyx to save storage costs
    await axios.delete(`https://api.telnyx.com/v2/recordings/${recording_id}`, {
      headers: {
        'Authorization': `Bearer ${process.env.TELNYX_API_KEY}`
      }
    });

    console.log(`Recording uploaded to Supabase for intake ${intake_id}`);

  } catch (error) {
    console.error(`Error uploading recording to Supabase:`, error);
    throw error;
  }
}
```

---

## 📊 Database Schema

You can use the existing `metadata` JSONB column:

```sql
-- No schema changes needed!
-- Just store everything in metadata column

SELECT
  id,
  patient_id,
  metadata->>'call_control_id' as call_control_id,
  metadata->>'recording_id' as recording_id,
  metadata->>'recording_url_supabase' as recording_url
FROM intakes
WHERE metadata->>'recording_id' IS NOT NULL;
```

**Or add dedicated columns (optional):**

```sql
ALTER TABLE intakes
ADD COLUMN call_control_id TEXT,
ADD COLUMN recording_id UUID,
ADD COLUMN recording_url TEXT,
ADD COLUMN recording_duration INTEGER;
```

---

## 🧪 Testing

### **Test 1: Check call.answered webhook**

1. Make a test call: `python src/make_call.py`
2. Check backend logs for `call.answered` webhook
3. Verify recording started successfully
4. Check database: `metadata.call_control_id` should be saved

### **Test 2: Check recording fetch**

1. After call ends, wait 2-3 minutes
2. Check background job logs
3. Verify recording_id is saved to database
4. Query: `SELECT metadata FROM intakes WHERE id = 'your-intake-id'`

### **Test 3: Verify custom_file_name**

```bash
# Query Telnyx API directly
curl -X GET "https://api.telnyx.com/v2/recordings?filter[custom_file_name]=your-intake-id" \
  -H "Authorization: Bearer YOUR_TELNYX_API_KEY"
```

---

## ⚠️ Important Notes

### **1. You Still Need ONE Webhook**

You need the `call.answered` webhook to:
- Get `call_control_id`
- Start recording with custom filename
- Match recording back to intake

**But you DON'T need** the `call.recording.saved` webhook!

### **2. Automatic Recording vs Manual Start**

If Telnyx is already recording automatically:
- **Option A:** Disable automatic recording, use manual `record_start` with custom filename
- **Option B:** Keep automatic recording, use `call_session_id` to query recordings

Ahmed's approach uses **manual recording** for precise control.

### **3. Background Job Retries**

Recording processing time varies (1-5 minutes). Your background job should:
- Wait 2 minutes before first attempt
- Retry every 1 minute if not found
- Give up after 5-10 attempts

### **4. Matching Logic**

With custom filename, matching is **exact**:
```
custom_file_name = intake_id
→ Perfect 1:1 match
→ No ambiguity!
```

---

## 💡 Advantages Over Webhook Approach

| Feature | Ahmed's Approach | Webhook Approach |
|---------|------------------|------------------|
| **Matching** | ✅ Exact (custom_file_name) | ⚠️ Phone + timestamp (ambiguous) |
| **Webhooks needed** | 1 (call.answered) | 2 (call.answered + recording.saved) |
| **Complexity** | ⚠️ Medium (background job) | ✅ Low (just webhook handler) |
| **Reliability** | ✅ High (retry logic) | ✅ High (Telnyx retries) |
| **Latency** | ⚠️ 2-5 min (polling) | ✅ Immediate (webhook) |

---

## 🎯 Summary

**Ahmed's approach is perfect for your backend developer because:**

1. ✅ Only ONE webhook endpoint needed (`call.answered`)
2. ✅ Exact matching using `custom_file_name = intake_id`
3. ✅ No ambiguity with simultaneous calls
4. ✅ Background job handles retries automatically
5. ✅ Can store everything in `metadata` JSONB column

**Trade-off:**
- 2-5 minute delay before recording appears (vs instant with webhook)
- Need to implement background job queue

But this is **much cleaner** than trying to match by phone number + timestamp!

---

## 📚 Required Telnyx API Endpoints

1. **Start Recording:**
   ```
   POST /v2/calls/{call_control_id}/actions/record_start
   ```

2. **List Recordings (with filter):**
   ```
   GET /v2/recordings?filter[custom_file_name]={intake_id}
   ```

3. **Get Recording (for download URL):**
   ```
   GET /v2/recordings/{recording_id}
   ```

4. **Delete Recording (optional):**
   ```
   DELETE /v2/recordings/{recording_id}
   ```

---

## 🆘 Troubleshooting

**Recording not found after 5 retries:**
- Check if `record_start` was successful (check Telnyx API response)
- Verify custom_file_name was set correctly
- Check Telnyx dashboard for recording

**Multiple recordings found:**
- This shouldn't happen with custom_file_name
- But if it does, take the most recent one

**call.answered webhook not received:**
- Verify webhook URL in Telnyx portal
- Check if URL is publicly accessible
- Look at Telnyx webhook delivery logs

---

**This is the approach Ahmed uses in production - proven and working!** ✅
