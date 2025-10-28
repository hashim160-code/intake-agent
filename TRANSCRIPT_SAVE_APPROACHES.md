# Transcript Saving Approaches - Analysis & Solutions

## 🚨 Current Problem

**Error:** `401 Unauthorized - "Your session has expired. Please log in again to continue."`

**Root Cause:** The backend API uses **cookie-based authentication** (session cookies from browser login), but the agent is a **server-side Python script** that:
- ❌ Cannot login through a browser
- ❌ Cannot maintain browser cookies
- ❌ Cannot access user sessions

---

## 📊 Three Approaches to Fix This

### **Approach 1: Supabase Direct (RECOMMENDED - Fastest)**

**What:** Agent saves directly to Supabase database, bypassing the backend API entirely.

**Pros:**
- ✅ Works immediately (no backend changes needed)
- ✅ No authentication issues
- ✅ Faster (no middleware layer)
- ✅ You already have Supabase credentials
- ✅ Simple code (5-10 lines)

**Cons:**
- ⚠️ Bypasses backend validation logic
- ⚠️ Backend team might prefer API approach

**Implementation:**

```python
# In api_client.py
from supabase import create_client
import os

async def save_transcript_to_supabase(intake_id: str, transcript_data: dict) -> bool:
    """Save transcript directly to Supabase"""
    try:
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

        response = supabase.table("intakes").update({
            "transcription": transcript_data
        }).eq("id", intake_id).execute()

        return len(response.data) > 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
```

**Timeline:** 5 minutes to implement

---

### **Approach 2: Backend Creates Separate API Endpoint (Recommended for Production)**

**What:** Backend team creates a **new API endpoint** specifically for the agent, using **API key authentication** (not cookies).

**Pros:**
- ✅ Proper authentication for server-to-server calls
- ✅ Backend controls validation logic
- ✅ Follows best practices
- ✅ Secure (API key can be rotated)

**Cons:**
- ⏳ Requires backend team to implement
- ⏳ Takes 1-2 days

**What Backend Team Needs to Do:**

```typescript
// In backend: src/app/api/agent/transcription/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/libs/db';

export async function POST(req: NextRequest) {
  try {
    // 1. Verify API key
    const apiKey = req.headers.get('x-api-key');
    if (apiKey !== process.env.AGENT_API_KEY) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }

    // 2. Get data
    const { intakeId, transcription } = await req.json();

    // 3. Validate
    if (!intakeId || !transcription) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // 4. Save to database
    await db.intakes.update({
      where: { id: intakeId },
      data: { transcription }
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error saving transcript:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

**Agent Implementation:**

```python
# In api_client.py
async def save_transcript_to_api(intake_id: str, transcript_data: dict) -> bool:
    """Save transcript via dedicated agent API endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/api/agent/transcription",  # New endpoint
                json={
                    "intakeId": intake_id,
                    "transcription": transcript_data
                },
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": os.getenv("AGENT_API_KEY")  # API key auth
                },
                timeout=30.0
            )
            return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
```

**Timeline:** 1-2 days (depends on backend team availability)

---

### **Approach 3: Hybrid (Best of Both Worlds)**

**What:** Use Supabase direct NOW, switch to API later when backend is ready.

**Pros:**
- ✅ Works immediately
- ✅ Can switch to API later (no rework needed)
- ✅ Graceful fallback if API fails

**Cons:**
- Slightly more code

**Implementation:**

```python
# In api_client.py
async def save_transcript_with_fallback(intake_id: str, transcript_data: dict) -> bool:
    """
    Try API first, fallback to Supabase direct if API fails
    """
    # Try API endpoint (when available)
    api_enabled = os.getenv("USE_TRANSCRIPT_API", "false").lower() == "true"

    if api_enabled:
        try:
            success = await save_transcript_to_api(intake_id, transcript_data)
            if success:
                print("✅ Saved via API")
                return True
            else:
                print("⚠️  API failed, trying Supabase direct...")
        except Exception as e:
            print(f"⚠️  API error: {e}, trying Supabase direct...")

    # Fallback to Supabase direct
    return await save_transcript_to_supabase(intake_id, transcript_data)
```

**Environment Variable:**
```bash
# .env
USE_TRANSCRIPT_API=false  # Set to true when backend API is ready
AGENT_API_KEY=your-api-key-here  # For when API is ready
```

**Timeline:** 5 minutes to implement, can switch to API anytime

---

## 🎯 Recommendation

### **For RIGHT NOW (Today):**

**Use Approach 1 (Supabase Direct)**

**Why:**
- Works immediately ✅
- No blockers ✅
- Agent can be deployed ✅
- Transcripts save successfully ✅

**Implementation:**
```python
# Just change one function in api_client.py
async def save_transcript_to_db(intake_id: str, transcript_data: dict) -> bool:
    """Save transcript directly to Supabase"""
    try:
        from supabase import create_client

        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

        response = supabase.table("intakes").update({
            "transcription": transcript_data
        }).eq("id", intake_id).execute()

        if response.data:
            print(f"✅ Transcript saved to database for intake {intake_id}")
            return True
        else:
            print(f"❌ Failed to save transcript")
            return False

    except Exception as e:
        print(f"❌ Error saving transcript: {e}")
        return False
```

---

### **For LATER (Production):**

**Switch to Approach 2 or 3** when:
1. Backend team creates the agent API endpoint
2. They provide you with API key
3. You update `.env` with the key
4. Switch to API-based approach

---

## 📋 Action Items

### **Immediate (You - 5 mins):**
- [ ] Replace `save_transcript_to_db()` with Supabase direct version
- [ ] Test with a call
- [ ] Verify transcript saves in Supabase table
- [ ] Deploy agent ✅

### **Later (Backend Team - 1-2 days):**
- [ ] Backend creates `/api/agent/transcription` endpoint
- [ ] Backend provides `AGENT_API_KEY`
- [ ] Backend deploys endpoint
- [ ] You add API key to `.env`
- [ ] You switch to Approach 2 or 3

---

## 🔐 Why Cookie Auth Doesn't Work for Agents

**Cookie-based authentication flow:**
```
1. User opens browser → Login page
2. User enters credentials
3. Backend creates session cookie
4. Browser stores cookie
5. Browser sends cookie with every request
```

**Why agent can't do this:**
```
Agent (Python script) → NO BROWSER
                      → NO LOGIN PAGE
                      → NO COOKIE STORAGE
                      → NO SESSION
                      → ❌ 401 Unauthorized
```

**Solution:** Use API key authentication (server-to-server)

---

## 📞 Questions for Backend Team

Copy-paste this to your backend team:

```
Hi Backend Team!

The intake agent needs to save transcripts, but the tRPC endpoint uses cookie-based auth which doesn't work for server-side scripts.

Options:
1. Can you create a dedicated API endpoint for the agent with API key auth?
   - Endpoint: POST /api/agent/transcription
   - Auth: x-api-key header
   - Body: { intakeId, transcription }

2. OR should the agent save directly to Supabase for now?

Which approach do you prefer?

Thanks!
```

---

## ✅ Summary

| Approach | Speed | Best For | Timeline |
|----------|-------|----------|----------|
| **1. Supabase Direct** | ⚡ Instant | Development, getting unblocked | 5 mins |
| **2. Dedicated API** | 🐢 Slow | Production, proper architecture | 1-2 days |
| **3. Hybrid** | ⚡ Instant + upgradable | Best of both worlds | 5 mins + upgrade later |

**Recommendation:** Start with **Approach 1** today, upgrade to **Approach 2** later.

---

**Document Version:** 1.0
**Date:** October 28, 2025
**Status:** Ready for Implementation
