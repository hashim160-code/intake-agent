# Dynamic Caller ID Implementation - Technical Guide

## Overview

This document explains how ZScribe implements dynamic caller ID for outbound intake calls. Each organization gets their own dedicated phone number, and when making calls, the system dynamically uses the appropriate organization's number as the caller ID.

---

## The Problem

**Current Setup (Static):**
- One SIP trunk manually created in LiveKit UI (`ST_Nxq7fztyRozT`)
- One test phone number (+17302060073) configured
- Every outbound call uses the SAME number for caller ID
- Works for testing, but NOT scalable for multiple organizations

**What We Need (Dynamic):**
- ONE SIP trunk (reuse existing `ST_Nxq7fztyRozT`)
- MULTIPLE phone numbers (40 initially) assigned to different organizations
- When making a call, **dynamically specify which number to use** as caller ID based on the organization

---

## The Solution: One Trunk, Many Numbers

### Key Insight

**You do NOT need to create a new SIP trunk for each organization!**

You only need:
- ✅ ONE SIP trunk (already created: `ST_Nxq7fztyRozT`)
- ✅ Multiple phone numbers purchased via Telnyx API
- ✅ Pass the organization's phone number dynamically when creating SIP participant

---

## How It Works: Step-by-Step

### **Step 1: Purchase Multiple Numbers via Telnyx API**

All 40 numbers are purchased through Telnyx API and automatically linked to your existing SIP trunk.

```python
import telnyx

# Purchase a phone number
available_numbers = telnyx.AvailablePhoneNumber.list(
    filter={'country_code': 'US', 'limit': 1}
)

number = available_numbers.data[0]

# Purchase and link to your Telnyx connection (which connects to LiveKit trunk)
purchased_number = telnyx.PhoneNumber.create(
    phone_number=number.phone_number,
    connection_id='YOUR_TELNYX_CONNECTION_ID'  # Links to SIP trunk
)

# Store in database
database.phone_numbers.insert({
    'phone_number': '+19712656795',
    'telnyx_phone_number_id': purchased_number.id,
    'status': 'available',
    'organization_id': None  # Not assigned yet
})
```

**Result:** All 40 numbers → Same Telnyx connection → Same LiveKit SIP trunk

---

### **Step 2: Assign Number to Organization**

When an organization registers, assign an available number from the pool:

```python
def assign_phone_number_to_org(organization_id: str):
    # Get an available number from pool
    number = database.phone_numbers.find_one({
        'status': 'available'
    })

    if not number:
        raise Exception("No available phone numbers in pool")

    # Assign to organization
    database.phone_numbers.update(
        {'id': number.id},
        {
            'organization_id': organization_id,
            'status': 'assigned',
            'assigned_at': datetime.now()
        }
    )

    # Update organization record
    database.organizations.update(
        {'id': organization_id},
        {'phone': number.phone_number}
    )

    return number.phone_number
```

**Result:** Organization now has dedicated phone number stored in `organizations.phone`

---

### **Step 3: Make Outbound Call with Dynamic Caller ID**

This is the **KEY PART**! When triggering an intake call, pass the organization's phone number dynamically.

#### **Current Code** (needs modification):

```python
# src/intake_api.py

@app.post("/intake-calls")
async def trigger_intake_call(request: IntakeCallRequest):
    # Current implementation doesn't fetch org phone number

    dispatch = lk_api.sip.create_sip_participant(
        CreateSIPParticipantRequest(
            sip_trunk_id=SIP_OUTBOUND_TRUNK_ID,
            sip_call_to=f"sip:{request.phone_number}@sip.livekit.cloud",
            room_name=room_name,
            # Missing: phone_number parameter!
        )
    )
```

#### **Updated Code** (with dynamic caller ID):

```python
# src/intake_api.py

@app.post("/intake-calls")
async def trigger_intake_call(request: IntakeCallRequest):
    # 1. Fetch organization from database
    organization = await fetch_organization_from_api(request.organization_id)

    if not organization:
        raise HTTPException(404, "Organization not found")

    # 2. Get the organization's assigned phone number
    org_phone_number = organization.get("phone")

    if not org_phone_number:
        raise HTTPException(
            400,
            "Organization does not have a phone number assigned. Please assign a number first."
        )

    # 3. Create SIP participant with DYNAMIC phone number
    dispatch = lk_api.sip.create_sip_participant(
        CreateSIPParticipantRequest(
            sip_trunk_id=SIP_OUTBOUND_TRUNK_ID,  # Static trunk: ST_Nxq7fztyRozT
            sip_call_to=f"sip:{request.phone_number}@sip.livekit.cloud",
            room_name=room_name,

            # THIS IS THE KEY: Dynamic caller ID!
            phone_number=org_phone_number,  # e.g., "+19712656795"

            participant_identity=f"sip-participant-{request.intake_id}",
            participant_name="intake-agent",
            participant_metadata=json.dumps(metadata)
        )
    )

    return {
        "status": "queued",
        "dispatch_id": dispatch.sip_dispatch_id,
        "caller_id": org_phone_number  # Return for reference
    }
```

---

## How LiveKit & Telnyx Process This

When you call `create_sip_participant()` with:
- `sip_trunk_id`: `ST_Nxq7fztyRozT` (your static trunk)
- `phone_number`: `+19712656795` (organization's number)
- `sip_call_to`: Patient's number

**LiveKit processes this:**
1. Uses trunk `ST_Nxq7fztyRozT` to connect to Telnyx
2. Tells Telnyx: "Make an outbound call using number `+19712656795` as caller ID"

**Telnyx validates:**
1. ✅ Is `+19712656795` owned by this account? → Yes (you purchased it)
2. ✅ Is it associated with this SIP connection? → Yes (via connection_id)
3. ✅ Make the call with that number as caller ID

**Patient receives call:**
- Caller ID shows: `+1 (971) 265-6795`
- This is the organization's dedicated number
- Professional and consistent caller ID

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Organization Registration                               │
│                                                                  │
│ 1. Doctor signs up → User & Provider data created               │
│ 2. Organization automatically created                            │
│ 3. Phone number assigned from pool: +19712656795                │
│ 4. Stored in organizations.phone field                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Intake Call Trigger                                     │
│                                                                  │
│ POST /intake-calls                                               │
│ {                                                                │
│   "organization_id": "0da4a59a-275f-...",                       │
│   "patient_id": "9092481d-0535-...",                            │
│   "phone_number": "+15551234567"  ← Patient's number            │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Intake-API Logic                                        │
│                                                                  │
│ 1. Fetch organization from database                             │
│    → org.phone = "+19712656795"                                 │
│                                                                  │
│ 2. Call LiveKit API:                                             │
│    create_sip_participant(                                       │
│      sip_trunk_id = "ST_Nxq7fztyRozT",    ← Static trunk        │
│      phone_number = "+19712656795",       ← Dynamic caller ID   │
│      sip_call_to = "sip:+15551234567@..." ← Patient number      │
│    )                                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: LiveKit → Telnyx                                        │
│                                                                  │
│ LiveKit tells Telnyx:                                            │
│ "Make outbound call to: +15551234567"                           │
│ "Use caller ID: +19712656795"                                   │
│ "Via trunk: ST_Nxq7fztyRozT"                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Patient Receives Call                                   │
│                                                                  │
│ Patient's phone rings                                            │
│ Caller ID displays: +1 (971) 265-6795                          │
│                                                                  │
│ ✅ Shows organization's dedicated number                         │
│ ✅ Professional and consistent                                   │
│ ✅ Patient can call back to this number (if inbound enabled)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## What Changes Are Required

### **1. Modify `intake_api.py`** (Day 3 of Implementation)

**Changes needed:**
1. Add logic to fetch organization's phone number from database
2. Validate that organization has a phone number assigned
3. Pass phone number to `create_sip_participant()` as `phone_number` parameter

**Code location:**
- File: `src/intake_api.py`
- Function: `trigger_intake_call()` or POST `/intake-calls` endpoint

### **2. That's It!**

You do **NOT** need to:
- ❌ Create multiple SIP trunks (one per organization)
- ❌ Call any LiveKit API to "register numbers with trunk"
- ❌ Modify LiveKit trunk configuration in UI
- ❌ Update Telnyx settings manually

---

## Important Technical Details

### **Telnyx Connection ID**

When purchasing numbers via Telnyx API, you specify a `connection_id`. This is the link between:
- Your Telnyx account
- Your phone numbers
- Your LiveKit SIP trunk

**Where to find it:**
1. Log into Telnyx dashboard
2. Go to "Voice" → "SIP Connections"
3. Find the connection that's linked to your LiveKit trunk
4. Copy the Connection ID (looks like: `1234567890`)

**Use it when purchasing numbers:**
```python
telnyx.PhoneNumber.create(
    phone_number="+19712656795",
    connection_id="YOUR_CONNECTION_ID"  # This links it to your trunk
)
```

### **Phone Number Validation**

Always validate that the organization has a phone number before making calls:

```python
if not org_phone_number:
    raise HTTPException(
        status_code=400,
        detail="Organization does not have a phone number assigned"
    )
```

This prevents errors when calling `create_sip_participant()` with an invalid number.

### **Error Handling**

If you pass a phone number that:
- Doesn't exist
- Isn't owned by your Telnyx account
- Isn't linked to the connection

LiveKit/Telnyx will **reject the call** with an error. Always validate before calling.

---

## Frequently Asked Questions

### **Q: Do I need to configure anything in Telnyx UI after purchasing numbers?**
**A:** No! When you purchase via API with the correct `connection_id`, numbers are automatically configured and ready to use.

### **Q: What if I use a phone number that doesn't exist?**
**A:** LiveKit/Telnyx will reject the call with an error. That's why we validate `org.phone` exists before calling `create_sip_participant()`.

### **Q: Can two organizations share the same phone number?**
**A:** Technically yes, but our pool management system ensures each organization gets their own unique number for consistency and professionalism.

### **Q: Do I need to "register" numbers with the LiveKit trunk?**
**A:** No! As long as the number is purchased via Telnyx API with the correct `connection_id`, it automatically works with your trunk.

### **Q: What about the test number I created manually (+17302060073)?**
**A:** You can keep it for testing or remove it. It won't interfere with the pool system. You might want to keep it as a fallback number.

### **Q: Can I see all numbers linked to my trunk?**
**A:** Yes, in the Telnyx dashboard under "Numbers" you'll see all purchased numbers and their associated connection.

### **Q: What if an organization changes their number?**
**A:** Simply update `organizations.phone` field in the database. Next time they make a call, it will use the new number automatically.

---

## Testing the Implementation

### **Test Scenario 1: Different Organizations, Different Caller IDs**

```python
# Organization A (org_id: 123) has phone: +19712656795
# Organization B (org_id: 456) has phone: +19713334444

# Call from Organization A
POST /intake-calls
{
  "organization_id": "123",
  "patient_id": "...",
  "phone_number": "+15551111111"
}
# Patient sees caller ID: +1 (971) 265-6795

# Call from Organization B
POST /intake-calls
{
  "organization_id": "456",
  "patient_id": "...",
  "phone_number": "+15552222222"
}
# Patient sees caller ID: +1 (971) 333-4444
```

✅ Different organizations → Different caller IDs automatically!

### **Test Scenario 2: Organization Without Phone Number**

```python
# Organization C (org_id: 789) has phone: null

POST /intake-calls
{
  "organization_id": "789",
  "patient_id": "...",
  "phone_number": "+15553333333"
}

# Expected Response: 400 Bad Request
{
  "detail": "Organization does not have a phone number assigned"
}
```

✅ Proper error handling prevents invalid calls

---

## Summary

### **Architecture:**
- ✅ One SIP trunk (`ST_Nxq7fztyRozT`)
- ✅ Multiple phone numbers (purchased via Telnyx API)
- ✅ Dynamic caller ID (specified per call)

### **Implementation:**
- ✅ Minimal code changes (only `intake_api.py`)
- ✅ No LiveKit configuration needed
- ✅ No manual Telnyx setup needed

### **Benefits:**
- ✅ Scalable (support hundreds of organizations)
- ✅ Simple (one trunk, not one per org)
- ✅ Professional (each org has dedicated number)
- ✅ Maintainable (all managed via code/database)

---

## Next Steps

1. **Day 1:** Purchase 40 numbers via Telnyx API
2. **Day 2:** Build phone number assignment service
3. **Day 3:** Modify `intake_api.py` to use dynamic caller ID
4. **Day 4:** Test with multiple organizations
5. **Day 5:** Deploy to production

Refer to the main **PHONE_NUMBER_RESEARCH.md** document for full implementation timeline and details.
