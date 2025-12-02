# Telnyx Recording Deletion Guide (Node.js/TypeScript)

## Overview
This guide explains how to automatically delete call recordings from Telnyx after they have been successfully stored in Supabase storage.

**Note**: The following processes are already implemented:
- ✅ Telnyx webhook handling (`call.recording.saved`)
- ✅ Recording download from Telnyx
- ✅ Recording upload to Supabase Storage
- ✅ Recording metadata saved to `intakes` table (including `telnyx_recording_id`)

**This guide focuses on**: Adding the final step to delete recordings from Telnyx after successful storage.

---

## Architecture Flow

```
✅ 1. Call Completes → Telnyx generates recording
✅ 2. Telnyx Webhook fires → `call.recording.saved` event
✅ 3. Backend receives webhook → Downloads recording from Telnyx
✅ 4. Backend uploads to Supabase Storage → Stores file
✅ 5. Backend saves metadata to database → `intakes` table (with telnyx_recording_id)
🆕 6. Backend calls Telnyx Delete API → Removes recording from Telnyx
🆕 7. Backend updates database → Records deletion timestamp
```

---

## Prerequisites

### Telnyx API Configuration

**API Token**: `KEY019ADE896E6AC28B815191AA34575E04_xxxxxxxxxxxxxxxx` (contact team lead for actual key)

**API Endpoint**: `https://api.telnyx.com/v2/recordings/{recording_id}`

**Method**: `DELETE`

**Authentication**: Bearer Token in Authorization header

**API Documentation**: https://developers.telnyx.com/api-reference/call-recordings/delete-a-call-recording

---

## Database Updates Needed

Add a column to track when recordings are deleted from Telnyx:

```sql
-- Add deletion timestamp column to intakes table
ALTER TABLE intakes
ADD COLUMN telnyx_recording_deleted_at TIMESTAMPTZ NULL;

-- Add comment for documentation
COMMENT ON COLUMN intakes.telnyx_recording_deleted_at IS 'Timestamp when recording was deleted from Telnyx';
```

---

## Implementation Steps

### Step 1: Install Required Dependencies (if not already installed)

```bash
npm install axios
# or
yarn add axios
```

---

### Step 2: Create Telnyx Deletion Service

Create a new file: `src/services/telnyxRecordingService.ts`

```typescript
import axios, { AxiosError } from 'axios';

const TELNYX_API_KEY = process.env.TELNYX_API_KEY || 'YOUR_TELNYX_API_KEY_HERE';
const TELNYX_API_BASE = 'https://api.telnyx.com/v2';

interface DeleteRecordingResult {
  success: boolean;
  statusCode?: number;
  error?: string;
}

/**
 * Delete recording from Telnyx storage
 *
 * API Documentation: https://developers.telnyx.com/api-reference/call-recordings/delete-a-call-recording
 *
 * @param recordingId - Telnyx recording ID (e.g., "rec_abc123xyz456")
 * @returns Promise<DeleteRecordingResult>
 */
export async function deleteRecordingFromTelnyx(
  recordingId: string
): Promise<DeleteRecordingResult> {
  const url = `${TELNYX_API_BASE}/recordings/${recordingId}`;

  try {
    const response = await axios.delete(url, {
      headers: {
        'Authorization': `Bearer ${TELNYX_API_KEY}`,
        'Content-Type': 'application/json',
      },
      timeout: 10000, // 10 second timeout
      validateStatus: (status) => status < 500, // Don't throw on 4xx errors
    });

    if (response.status === 204) {
      // Success - recording deleted
      console.log(`✅ Recording ${recordingId} deleted from Telnyx`);
      return { success: true, statusCode: 204 };
    } else if (response.status === 404) {
      // Recording already deleted or doesn't exist
      console.warn(`⚠️ Recording ${recordingId} not found (may already be deleted)`);
      return { success: true, statusCode: 404 };
    } else {
      // Other error
      console.error(`❌ Failed to delete recording ${recordingId}: ${response.status} - ${JSON.stringify(response.data)}`);
      return {
        success: false,
        statusCode: response.status,
        error: JSON.stringify(response.data),
      };
    }
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      console.error(`❌ Axios error deleting recording ${recordingId}:`, axiosError.message);
      return {
        success: false,
        statusCode: axiosError.response?.status,
        error: axiosError.message,
      };
    }

    console.error(`❌ Unexpected error deleting recording ${recordingId}:`, error);
    return {
      success: false,
      error: String(error),
    };
  }
}
```

**Expected Response:**
- **Success**: HTTP 204 No Content (empty body)
- **Not Found**: HTTP 404 (recording already deleted or doesn't exist) - treat as success
- **Error**: HTTP 4xx/5xx with error message

---

### Step 3: Update Database After Deletion

Add this function to your database service or create `src/services/intakeService.ts`:

```typescript
import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_KEY!;
const supabase: SupabaseClient = createClient(supabaseUrl, supabaseKey);

interface MarkRecordingDeletedResult {
  success: boolean;
  error?: string;
}

/**
 * Mark recording as deleted from Telnyx in database
 *
 * @param intakeId - UUID of the intake record
 * @returns Promise<MarkRecordingDeletedResult>
 */
export async function markRecordingDeleted(
  intakeId: string
): Promise<MarkRecordingDeletedResult> {
  try {
    const { error } = await supabase
      .from('intakes')
      .update({
        telnyx_recording_deleted_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq('id', intakeId);

    if (error) {
      console.error(`❌ Failed to mark recording as deleted for intake ${intakeId}:`, error);
      return { success: false, error: error.message };
    }

    console.log(`✅ Marked recording as deleted for intake ${intakeId}`);
    return { success: true };
  } catch (error) {
    console.error(`❌ Exception marking recording as deleted for intake ${intakeId}:`, error);
    return { success: false, error: String(error) };
  }
}
```

---

### Step 4: Add to Existing Webhook Handler

Update your existing webhook handler that processes `call.recording.saved` events:

```typescript
import { Request, Response } from 'express';
import { deleteRecordingFromTelnyx } from './services/telnyxRecordingService';
import { markRecordingDeleted } from './services/intakeService';

/**
 * Handle Telnyx recording webhook
 * This should be called AFTER recording is already saved to Supabase
 */
export async function handleRecordingSavedWebhook(
  intakeId: string,
  telnyxRecordingId: string
): Promise<void> {
  try {
    console.log(`Processing recording deletion for intake ${intakeId}, recording ${telnyxRecordingId}`);

    // NEW: Delete recording from Telnyx
    const deleteResult = await deleteRecordingFromTelnyx(telnyxRecordingId);

    if (deleteResult.success) {
      // NEW: Update database with deletion timestamp
      console.log(`Marking recording as deleted in database`);
      const markResult = await markRecordingDeleted(intakeId);

      if (!markResult.success) {
        console.error(`Failed to mark recording as deleted in database, but recording was deleted from Telnyx`);
      }
    } else {
      // Log error but don't fail - recording is safe in Supabase
      console.error(
        `Failed to delete recording ${telnyxRecordingId} from Telnyx, but recording is safe in Supabase`,
        deleteResult.error
      );
    }
  } catch (error) {
    console.error(`Error in recording deletion flow:`, error);
    // Don't throw - recording is already safely stored in Supabase
  }
}

/**
 * Example webhook endpoint (add to your existing webhook router)
 */
export async function telnyxWebhookHandler(req: Request, res: Response): Promise<void> {
  try {
    const payload = req.body;

    // Validate event type
    const eventType = payload?.data?.event_type;
    if (eventType !== 'call.recording.saved') {
      res.status(200).json({ status: 'ignored', reason: 'not a recording.saved event' });
      return;
    }

    // Extract recording data
    const eventPayload = payload?.data?.payload;
    const recordingId = eventPayload?.recording_id;
    const callSessionId = eventPayload?.call_session_id;

    if (!recordingId) {
      res.status(400).json({ error: 'Missing recording_id' });
      return;
    }

    // TODO: Get intake_id from call_session_id or room metadata
    // This depends on how you're tracking the mapping
    const intakeId = 'YOUR_INTAKE_ID_HERE'; // ← Map from call_session_id

    // Your existing code: download recording, upload to Supabase, save metadata
    // ... (already implemented) ...

    // NEW: After recording is saved to Supabase, delete from Telnyx
    await handleRecordingSavedWebhook(intakeId, recordingId);

    res.status(200).json({
      status: 'success',
      recording_id: recordingId,
      intake_id: intakeId,
    });
  } catch (error) {
    console.error('Error processing recording webhook:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}
```

---

## Environment Variables

Add to your `.env` file:

```bash
# Telnyx Configuration
TELNYX_API_KEY=YOUR_TELNYX_API_KEY_HERE
TELNYX_API_BASE_URL=https://api.telnyx.com/v2

# Supabase Configuration (should already exist)
SUPABASE_URL=https://nmefeljjgslggutiquqg.supabase.co
SUPABASE_KEY=your_supabase_service_role_key_here
```

---

## TypeScript Type Definitions

Add these types to your project (e.g., `src/types/telnyx.ts`):

```typescript
export interface TelnyxWebhookPayload {
  data: {
    event_type: string;
    id: string;
    occurred_at: string;
    payload: {
      call_control_id: string;
      call_leg_id: string;
      call_session_id: string;
      recording_id: string;
      recording_urls: {
        mp3?: string;
        wav?: string;
      };
      recording_started_at: string;
      recording_ended_at: string;
    };
  };
}

export interface IntakeRecord {
  id: string;
  telnyx_recording_id: string | null;
  telnyx_recording_deleted_at: string | null;
  recording_url: string | null;
  created_at: string;
  updated_at: string;
}
```

---

## Error Handling Strategy

### Scenario 1: Telnyx Deletion Fails
- **Action**: Log error but DO NOT fail the webhook
- **Reason**: Recording is safely stored in Supabase (most important)
- **Recovery**: Implement background job to retry deletion later (see Manual Deletion Script below)

### Scenario 2: Database Update Fails (deletion timestamp)
- **Action**: Log error and alert team
- **Reason**: Data inconsistency - need to track what was deleted
- **Recovery**: Manual database update required

### Scenario 3: 404 from Telnyx
- **Action**: Log as warning and treat as success
- **Reason**: Recording already deleted (idempotent operation)
- **Result**: Update database with deletion timestamp

---

## Testing

### 1. Test Telnyx Deletion API

```bash
# Test with a real recording ID from your Telnyx account
curl -X DELETE https://api.telnyx.com/v2/recordings/YOUR_RECORDING_ID \
  -H "Authorization: Bearer YOUR_TELNYX_API_KEY_HERE"

# Expected Response:
# HTTP 204 No Content (empty body) = Success
```

### 2. Unit Test Example

Create `src/services/telnyxRecordingService.test.ts`:

```typescript
import { deleteRecordingFromTelnyx } from './telnyxRecordingService';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('deleteRecordingFromTelnyx', () => {
  it('should return success for 204 response', async () => {
    mockedAxios.delete.mockResolvedValue({ status: 204, data: {} });

    const result = await deleteRecordingFromTelnyx('rec_test123');

    expect(result.success).toBe(true);
    expect(result.statusCode).toBe(204);
  });

  it('should treat 404 as success', async () => {
    mockedAxios.delete.mockResolvedValue({ status: 404, data: {} });

    const result = await deleteRecordingFromTelnyx('rec_test123');

    expect(result.success).toBe(true);
    expect(result.statusCode).toBe(404);
  });

  it('should handle errors gracefully', async () => {
    mockedAxios.delete.mockRejectedValue(new Error('Network error'));

    const result = await deleteRecordingFromTelnyx('rec_test123');

    expect(result.success).toBe(false);
    expect(result.error).toBeDefined();
  });
});
```

### 3. Verify Database Updates

```sql
-- Check recordings with deletion timestamps
SELECT
    id,
    telnyx_recording_id,
    telnyx_recording_deleted_at,
    recording_url,
    created_at
FROM intakes
WHERE telnyx_recording_id IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;

-- Count deleted vs pending
SELECT
    COUNT(*) FILTER (WHERE telnyx_recording_deleted_at IS NOT NULL) as deleted_count,
    COUNT(*) FILTER (WHERE telnyx_recording_deleted_at IS NULL) as pending_count
FROM intakes
WHERE telnyx_recording_id IS NOT NULL;
```

---

## Manual Deletion Script (For Backlog)

Create `scripts/deleteBacklogRecordings.ts`:

```typescript
import { createClient } from '@supabase/supabase-js';
import { deleteRecordingFromTelnyx } from '../src/services/telnyxRecordingService';
import { markRecordingDeleted } from '../src/services/intakeService';

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

/**
 * Manually delete recordings from Telnyx for intakes where:
 * - telnyx_recording_id is set (recording was saved)
 * - telnyx_recording_deleted_at is NULL (deletion not done yet)
 */
async function deleteBacklogRecordings(): Promise<void> {
  try {
    console.log('Fetching recordings pending deletion...');

    // Get all intakes with pending deletions
    const { data: pending, error } = await supabase
      .from('intakes')
      .select('id, telnyx_recording_id')
      .not('telnyx_recording_id', 'is', null)
      .is('telnyx_recording_deleted_at', null);

    if (error) {
      console.error('Error fetching pending deletions:', error);
      return;
    }

    if (!pending || pending.length === 0) {
      console.log('No recordings pending deletion');
      return;
    }

    console.log(`Found ${pending.length} recordings pending deletion from Telnyx`);

    let successCount = 0;
    let failCount = 0;

    for (const record of pending) {
      const { id: intakeId, telnyx_recording_id: recordingId } = record;

      console.log(`Processing ${recordingId} for intake ${intakeId}...`);

      // Delete from Telnyx
      const deleteResult = await deleteRecordingFromTelnyx(recordingId);

      if (deleteResult.success) {
        // Update database
        const markResult = await markRecordingDeleted(intakeId);
        if (markResult.success) {
          successCount++;
        } else {
          console.error(`Failed to mark ${recordingId} as deleted in database`);
          failCount++;
        }
      } else {
        console.error(`Failed to delete ${recordingId} from Telnyx`);
        failCount++;
      }

      // Rate limit: wait 100ms between deletions
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    console.log(`✅ Manual deletion complete: ${successCount} succeeded, ${failCount} failed`);
  } catch (error) {
    console.error('Error in deleteBacklogRecordings:', error);
  }
}

// Run the script
deleteBacklogRecordings()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error('Script failed:', error);
    process.exit(1);
  });
```

**Run the script:**
```bash
npx ts-node scripts/deleteBacklogRecordings.ts
```

**When to Use This:**
- After initial implementation (to clean up backlog)
- After any outage where deletion failed
- For compliance audits (ensure all recordings deleted)

---

## Monitoring & Alerts

### Key Metrics to Track:

1. **Deletion Success Rate**: % of recordings successfully deleted from Telnyx
2. **Deletion Latency**: Time from recording saved to deletion
3. **Pending Deletions**: Count of recordings with `telnyx_recording_id` but no deletion timestamp

### Recommended Alert Queries:

```typescript
// Example monitoring function
async function checkRecordingDeletionHealth(): Promise<{
  oldRecordings: number;
  recentFailureRate: number;
}> {
  // Check for recordings older than 24 hours without deletion
  const { count: oldRecordings } = await supabase
    .from('intakes')
    .select('id', { count: 'exact', head: true })
    .not('telnyx_recording_id', 'is', null)
    .is('telnyx_recording_deleted_at', null)
    .lt('created_at', new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString());

  // Check deletion failure rate in last hour
  const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();

  const { count: totalRecent } = await supabase
    .from('intakes')
    .select('id', { count: 'exact', head: true })
    .not('telnyx_recording_id', 'is', null)
    .gte('created_at', oneHourAgo);

  const { count: failedRecent } = await supabase
    .from('intakes')
    .select('id', { count: 'exact', head: true })
    .not('telnyx_recording_id', 'is', null)
    .is('telnyx_recording_deleted_at', null)
    .gte('created_at', oneHourAgo);

  const recentFailureRate = totalRecent ? (failedRecent / totalRecent) * 100 : 0;

  return {
    oldRecordings: oldRecordings || 0,
    recentFailureRate,
  };
}
```

---

## Troubleshooting

### Issue: 404 Error when deleting from Telnyx
**Symptom**: API returns 404 Not Found
**Cause**: Recording already deleted or invalid recording_id
**Solution**: This is normal! Treat as success (idempotent operation)
**Action**: Still update `telnyx_recording_deleted_at` in database

### Issue: 401 Unauthorized
**Symptom**: API returns 401
**Cause**: Invalid or expired API key
**Solution**:
1. Verify `TELNYX_API_KEY` environment variable is correct
2. Check API key is active in Telnyx portal
3. Ensure API key has `recordings:delete` permission

### Issue: TypeScript compilation errors
**Symptom**: Build fails with type errors
**Solution**:
1. Install types: `npm install -D @types/node`
2. Ensure `tsconfig.json` has proper settings
3. Check all imports are correct

---

## Deployment Checklist

Before deploying to production:

- [ ] Database migration run (add `telnyx_recording_deleted_at` column)
- [ ] Environment variable `TELNYX_API_KEY` set in production
- [ ] Code deployed with deletion functions
- [ ] Test deletion with sample recording
- [ ] Verify database updates work
- [ ] Set up monitoring alerts
- [ ] Document in team wiki/runbook
- [ ] Run manual deletion script for existing recordings (if needed)

---

## Summary

### What to Implement:

1. **Add Database Column**: Run SQL to add `telnyx_recording_deleted_at`
2. **Create Service File**: `src/services/telnyxRecordingService.ts`
3. **Create DB Service**: `src/services/intakeService.ts` (or add to existing)
4. **Update Webhook Handler**: Add deletion call after recording saved
5. **Add Environment Variable**: `TELNYX_API_KEY`
6. **Add Types**: Create TypeScript type definitions
7. **Test**: Make test call and verify deletion

### Expected Result:

- ✅ Recordings automatically deleted from Telnyx after Supabase upload
- ✅ Database tracks deletion timestamps
- ✅ Audit trail maintained
- ✅ Compliance requirement met (data minimization)
- ✅ Type-safe implementation with TypeScript

---

## Additional Resources

- **Telnyx API Docs**: https://developers.telnyx.com/api-reference
- **Telnyx Node SDK**: https://github.com/team-telnyx/telnyx-node (optional, can use axios instead)
- **Supabase JS Docs**: https://supabase.com/docs/reference/javascript

---

**Created**: December 1, 2025
**Last Updated**: December 1, 2025
**Version**: 3.0 (Node.js/TypeScript Implementation)
