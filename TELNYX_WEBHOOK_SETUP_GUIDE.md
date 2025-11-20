# Telnyx Webhook Configuration Guide

Complete step-by-step guide to configure webhooks in Telnyx Mission Control Portal to receive call recording events.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Step-by-Step Configuration](#step-by-step-configuration)
3. [Webhook Event: call.recording.saved](#webhook-event-callrecordingsaved)
4. [Testing Your Webhook](#testing-your-webhook)
5. [Local Development with ngrok](#local-development-with-ngrok)

---

## Prerequisites

Before configuring webhooks, ensure you have:

1. ✅ **Telnyx Account** with access to Mission Control Portal
2. ✅ **Publicly Accessible HTTPS Endpoint** (e.g., `https://yourdomain.com/api/webhooks/telnyx/recording`)
3. ✅ **Call Control Application** or ability to create one
4. ✅ **Backend webhook handler** implemented (see [RECORDING_IMPLEMENTATION_GUIDE.md](./RECORDING_IMPLEMENTATION_GUIDE.md))

---

## Step-by-Step Configuration

### Step 1: Navigate to Voice API Applications

1. Log in to [Telnyx Mission Control Portal](https://portal.telnyx.com/)
2. In the left sidebar, navigate to:
   ```
   Voice > Programmable Voice
   ```
3. Click on the **Call Control / TeXML Applications** tab

### Step 2: Create or Edit Voice Application

**Option A: Create New Application**
1. Click **"Create Voice App"** button
2. Enter a descriptive name (e.g., "ZScribe Intake Agent")
3. Proceed to webhook configuration

**Option B: Edit Existing Application**
1. Find your existing Call Control Application (likely the one used by your SIP trunk)
2. Click the **edit symbol [✎]** next to the application name

### Step 3: Configure Primary Webhook URL

In the webhook delivery section:

1. **Send a webhook to the URL** field:
   ```
   https://yourdomain.com/api/webhooks/telnyx/recording
   ```

   ⚠️ **Important Requirements:**
   - Must use `https://` (not `http://`)
   - Must be publicly accessible
   - Should respond with 2xx HTTP status code (200, 201, 204)

2. **Example Production URL:**
   ```
   https://api.zscribe.com/api/webhooks/telnyx/recording
   ```

### Step 4: Configure Failover URL (Optional but Recommended)

1. **Failover URL** field:
   ```
   https://yourdomain.com/api/webhooks/telnyx/recording-failover
   ```

   This URL will be used if **two consecutive delivery attempts** to the primary URL fail.

### Step 5: Select Webhook API Version

1. **Webhook API Version**: Select **"V2"**

   ✅ **Why V2?**
   - Contains richer feature set
   - V1 will be deprecated in the future
   - Better structured payload format

### Step 6: Configure Retry Behavior (Optional)

1. **Custom webhook retry delay (seconds)**: Leave empty for immediate retries

   Or specify a value (e.g., `5`) to wait 5 seconds between retry attempts.

### Step 7: Configure Timeout Settings (Optional)

1. **Enable hang-up on timeout**: Choose based on your needs
2. **Custom webhook timeout**: Default is usually sufficient (30 seconds)

### Step 8: Save Configuration

1. Click **"Save"** or **"Update"** button
2. Your webhook is now configured! 🎉

---

## Webhook Event: call.recording.saved

When a call recording is ready, Telnyx sends the `call.recording.saved` webhook to your configured URL.

### Example Webhook Payload

```json
{
  "data": {
    "event_type": "call.recording.saved",
    "id": "some-event-id",
    "occurred_at": "2025-01-19T10:30:00.000Z",
    "payload": {
      "call_control_id": "9977677e-85ae-11ec-826d-02420a0d7e70",
      "call_leg_id": "9977677e-85ae-11ec-826d-02420a0d7e70",
      "call_session_id": "99706bb8-85ae-11ec-885c-02420a0d7e70",
      "channels": "single",
      "client_state": null,
      "connection_id": "1684641123236054244",
      "from": "+15551234567",
      "to": "+19712656795",

      "recording_id": "10cd86ac-fef8-4765-b203-0f7511f9fc75",
      "format": "wav",
      "recording_started_at": "2025-01-19T10:28:08.148619Z",
      "recording_ended_at": "2025-01-19T10:30:12.788447Z",

      "recording_urls": {
        "wav": "https://s3.amazonaws.com/telnyx-recordings/..."
      },
      "public_recording_urls": {},

      "start_time": "2025-01-19T10:28:08.148619Z",
      "end_time": "2025-01-19T10:30:12.788447Z",
      "occurred_at": "2025-01-19T10:30:13.508869Z"
    },
    "record_type": "event"
  },
  "meta": {
    "attempt": 1,
    "delivered_to": "https://yourdomain.com/api/webhooks/telnyx/recording"
  }
}
```

### Key Fields You Need

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `recording_id` | UUID | Unique identifier for the recording | `"10cd86ac-fef8-4765-b203-0f7511f9fc75"` |
| `recording_urls.wav` | URL | Temporary download URL (expires after 7 days) | `"https://s3.amazonaws.com/..."` |
| `from` | Phone | Caller's phone number | `"+15551234567"` |
| `to` | Phone | Called phone number | `"+19712656795"` |
| `recording_started_at` | ISO 8601 | When recording started | `"2025-01-19T10:28:08.148619Z"` |
| `recording_ended_at` | ISO 8601 | When recording ended | `"2025-01-19T10:30:12.788447Z"` |
| `channels` | String | "single" or "dual" channel | `"single"` |
| `format` | String | Audio format | `"wav"` or `"mp3"` |

### Important Notes

⚠️ **Recording URL Expiration:**
- The `recording_urls.wav` link expires after **7 days**
- You **MUST** download and store the recording in your own storage (Supabase) before expiration
- This is why the background job is critical!

📝 **Matching Recording to Intake:**
- Use the `to` phone number field (patient's phone)
- Match with timestamp window (±10 minutes)
- See [RECORDING_IMPLEMENTATION_GUIDE.md](./RECORDING_IMPLEMENTATION_GUIDE.md) for matching logic

---

## Testing Your Webhook

### 1. Verify Webhook URL is Reachable

```bash
curl -X POST https://yourdomain.com/api/webhooks/telnyx/recording \
  -H "Content-Type: application/json" \
  -d '{"test": "webhook"}'
```

Expected response: `200 OK` or `204 No Content`

### 2. Check Webhook Logs in Telnyx Portal

1. Go to **Voice > Programmable Voice > Call Control Applications**
2. Click on your application
3. Look for **"Webhook Logs"** or **"Recent Webhooks"** section
4. You should see delivery attempts, status codes, and any errors

### 3. Make a Test Call

1. Use your `make_call.py` script to initiate a test call
2. Have a short conversation (record for 30 seconds)
3. Hang up the call
4. Wait 1-2 minutes for recording processing
5. Check your webhook endpoint logs for the `call.recording.saved` event

### 4. Verify Database Update

After receiving the webhook:

```sql
SELECT intake_id, recording_id, created_at
FROM intakes
WHERE recording_id IS NOT NULL
ORDER BY created_at DESC
LIMIT 5;
```

---

## Local Development with ngrok

For local testing, use ngrok to create a public tunnel to your local server.

### Step 1: Install ngrok

```bash
# Download from https://ngrok.com/download
# Or install via npm
npm install -g ngrok
```

### Step 2: Start Your Local Backend

```bash
# Start your backend server on port 3000
npm run dev
```

### Step 3: Create ngrok Tunnel

```bash
ngrok http 3000
```

Output:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:3000
```

### Step 4: Update Telnyx Webhook URL

Use the ngrok URL in your Telnyx webhook configuration:

```
https://abc123.ngrok.io/api/webhooks/telnyx/recording
```

### Step 5: Monitor Webhook Requests

ngrok provides a web interface to inspect requests:

```
http://localhost:4040
```

You can see all webhook payloads received and your server's responses.

---

## Webhook Security (Best Practices)

### 1. Verify Webhook Signature

Telnyx signs webhooks with your account's public key. Verify the signature to ensure authenticity:

```typescript
import crypto from 'crypto';

function verifyTelnyxSignature(
  payload: string,
  signature: string,
  timestamp: string,
  publicKey: string
): boolean {
  const signedPayload = `${timestamp}|${payload}`;
  const expectedSignature = crypto
    .createHmac('sha256', publicKey)
    .update(signedPayload)
    .digest('base64');

  return signature === expectedSignature;
}

// Use in your webhook handler
app.post('/api/webhooks/telnyx/recording', async (req, res) => {
  const signature = req.headers['telnyx-signature-ed25519'];
  const timestamp = req.headers['telnyx-timestamp'];
  const payload = JSON.stringify(req.body);

  if (!verifyTelnyxSignature(payload, signature, timestamp, TELNYX_PUBLIC_KEY)) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  // Process webhook...
});
```

### 2. Check Timestamp to Prevent Replay Attacks

```typescript
const MAX_TIMESTAMP_AGE = 5 * 60 * 1000; // 5 minutes

function isTimestampValid(timestamp: string): boolean {
  const timestampMs = parseInt(timestamp, 10);
  const now = Date.now();
  return Math.abs(now - timestampMs) < MAX_TIMESTAMP_AGE;
}
```

### 3. Return Response Quickly

Telnyx expects a response within 30 seconds (default timeout). Process webhooks asynchronously:

```typescript
app.post('/api/webhooks/telnyx/recording', async (req, res) => {
  // Validate webhook
  // ...

  // Return 200 immediately
  res.status(200).json({ received: true });

  // Process in background (queue job)
  await jobQueue.add('process-recording', {
    recordingId: req.body.data.payload.recording_id,
    phoneNumber: req.body.data.payload.to,
    recordingUrl: req.body.data.payload.recording_urls.wav
  });
});
```

---

## Troubleshooting

### Webhook Not Receiving Events

**Check 1: Is the webhook URL correct?**
- Must be `https://` (not `http://`)
- Must be publicly accessible
- Test with `curl` from an external machine

**Check 2: Is your server responding with 2xx status code?**
- Telnyx considers 4xx/5xx as failures
- Check your server logs for errors

**Check 3: Is the Call Control Application associated with your SIP trunk?**
- Go to **Voice > Phone Numbers**
- Click on your phone number
- Check that it's connected to the correct Call Control Application

**Check 4: Check Telnyx Webhook Logs**
- Go to your Call Control Application settings
- Look for webhook delivery logs
- Check for error messages

### Recording Not Available

**Issue: Webhook received but `recording_urls` is empty**

This can happen if:
- Recording failed to save (rare)
- Recording is still processing (wait 1-2 minutes)
- Custom storage credentials are misconfigured

**Solution:** Check Telnyx support or logs for recording errors.

### Duplicate Webhooks

**Issue: Receiving the same webhook multiple times**

This is normal behavior! Telnyx may retry webhook delivery if:
- Response took too long (>30 seconds)
- Network issue during response
- Non-2xx status code returned

**Solution:** Make your webhook handler **idempotent**:

```typescript
async function handleRecordingWebhook(recordingId: string, phoneNumber: string) {
  // Check if already processed
  const existing = await db.query(
    'SELECT 1 FROM intakes WHERE recording_id = $1',
    [recordingId]
  );

  if (existing.rows.length > 0) {
    console.log(`Recording ${recordingId} already processed, skipping`);
    return; // Already processed, skip
  }

  // Process recording...
}
```

---

## Next Steps

After configuring webhooks:

1. ✅ **Implement webhook handler** - See [RECORDING_IMPLEMENTATION_GUIDE.md](./RECORDING_IMPLEMENTATION_GUIDE.md)
2. ✅ **Set up background job queue** - To fetch and upload recordings
3. ✅ **Configure Supabase Storage** - Create bucket and set permissions
4. ✅ **Test end-to-end** - Make test call and verify recording appears in UI
5. ✅ **Monitor webhook logs** - Ensure reliable delivery

---

## References

- [Telnyx Webhook Documentation](https://developers.telnyx.com/docs/voice/programmable-voice/receiving-webhooks)
- [Configuring Call Control Applications](https://support.telnyx.com/en/articles/4374050-configuring-call-control-texml-applications-voice-api)
- [Storing Call Recordings](https://developers.telnyx.com/docs/voice/programmable-voice/storing-call-recordings)
- [Telnyx API Reference - Recordings](https://developers.telnyx.com/api/call-recordings/get-recording)

---

## Support

If you encounter issues:

1. **Telnyx Support:** +1.888.980.9750 or support@telnyx.com
2. **Telnyx Developer Slack:** [Join here](https://telnyx-community.slack.com/)
3. **Documentation:** https://developers.telnyx.com/
