# Phone Number Provisioning - Research & Strategy Document

## Executive Summary

This document outlines the research and strategic considerations for implementing automated phone number provisioning for organizations in the ZScribe platform. When an organization registers, they need a dedicated phone number for making outbound intake calls with proper caller ID.

**Key Takeaways:**
- **Provider**: Telnyx (already in use, working with LiveKit)
- **Strategy**: Hybrid Pool Approach (40-number initial pool)
- **Initial Cost**: ~$85/month for 30-40 organizations (~$2.83 per org)
- **Status**: Technical infrastructure ready, awaiting leadership decisions on integration details

---

## Problem Statement

Currently, the ZScribe intake agent makes outbound calls via LiveKit's SIP trunk. However, organizations need:

1. **Dedicated phone numbers** - Each organization should have their own number for caller ID
2. **Automated provisioning** - Numbers should be assigned automatically during registration
3. **Scalability** - System should handle from 10 to 10,000+ organizations
4. **Cost efficiency** - Minimize costs while maintaining good UX
5. **Flexibility** - Organizations may want specific area codes

---

## Current Architecture

### What We Have:
- **LiveKit** for real-time voice agent infrastructure
- **SIP Trunk** (SIP_OUTBOUND_TRUNK_ID) for telephony connectivity
- **Outbound calling** capability via LiveKit's `create_sip_participant`
- **Supabase** database with organizations, patients, templates tables

### What We Need:
- Phone number provider (Telnyx, Twilio, Vonage, or Bandwidth)
- Phone number management system
- Database schema for tracking numbers
- Provisioning logic for automatic assignment
- Integration with LiveKit for caller ID

---

## Current Setup - ZScribe Implementation

### Existing Infrastructure:

**LiveKit Configuration:**
- **SIP Trunk ID**: `ST_Nxq7fztyRozT` (Intake Agent Trunk)
- **SIP URI**: `sip:1b3y46cli5c.sip.livekit.cloud`
- **Provider**: Telnyx (`sip.telnyx.com`)
- **Status**: ✅ Active and working (deployed on Cloud Run)
- **Test Number**: `+17302060073` (used for testing, not for production pool)

**Database Schema:**
- Table: `organizations` (already exists in Supabase)
- Existing phone column: `phone text null` (currently unused)
- **Missing**: Separate `phone_numbers` table for pool management
- **Missing**: Columns for tracking Telnyx phone number IDs

**Current State:**
- ✅ Telnyx account: Active
- ✅ LiveKit integration: Working
- ✅ One test number purchased
- ✅ Intake agent: Deployed and functional on Cloud Run
- ❌ Phone number pool: Not yet created
- ❌ Automated provisioning: Not yet implemented

**Current Registration Flow:**
1. User signs up (doctor/provider)
2. User data is created
3. Provider data is created
4. Organization is **automatically created** and linked to the provider
5. Database endpoint creates organization record
6. _(Phone number assignment will be integrated into this flow)_

### Feature Requirements (ZScribe Specific):

**Confirmed Requirements:**
- ✅ **Voice Calls Only**: No SMS capabilities needed
- ✅ **Outbound Only**: No inbound calling support required
- ✅ **Call Recording**: Already handled by Telnyx (no additional setup needed)
- ✅ **HIPAA Compliance**: Required for medical intake calls (Telnyx supports this)

**Pending Decisions:**
- ⏳ **Area Code Preference**: Should organizations be able to choose their area code, or auto-assign any available number? _(Awaiting leadership decision)_

---

## Database Modifications Required

### Current Schema:

The `organizations` table already has a `phone` column but it's currently unused:

```sql
create table public.organizations (
  id uuid not null default gen_random_uuid(),
  name text not null,
  slug text not null,
  phone text null,  -- Currently unused
  settings jsonb null,
  subscription_status text null,
  -- ... other fields
)
```

### Recommended Changes:

#### Option 1: Simple Approach (Use Existing Column)
Add a new column to track the Telnyx phone number ID:

```sql
ALTER TABLE organizations
ADD COLUMN telnyx_phone_number_id text null;
```

**Pros:**
- Minimal changes
- Quick to implement
- Uses existing `phone` column for storing the number

**Cons:**
- No pool management capability
- Can't track number lifecycle
- Harder to implement number recycling

---

#### Option 2: Dedicated Table (Recommended for Hybrid Pool)
Create a separate `phone_numbers` table for better pool management:

```sql
CREATE TABLE phone_numbers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  phone_number text NOT NULL UNIQUE,
  telnyx_phone_number_id text NOT NULL,
  organization_id uuid REFERENCES organizations(id) NULL,
  status text NOT NULL DEFAULT 'available',
    -- 'available', 'assigned', 'suspended', 'released'
  area_code text NOT NULL,
  country_code text NOT NULL DEFAULT 'US',
  purchased_at timestamp NOT NULL DEFAULT now(),
  assigned_at timestamp NULL,
  released_at timestamp NULL,
  created_at timestamp NOT NULL DEFAULT now(),
  updated_at timestamp NOT NULL DEFAULT now()
);

-- Index for quick pool lookups
CREATE INDEX idx_phone_numbers_status ON phone_numbers(status);
CREATE INDEX idx_phone_numbers_org_id ON phone_numbers(organization_id);

-- Update organizations.phone when a number is assigned (optional)
-- Or query the phone_numbers table with a join
```

**Pros:**
- ✅ Full pool management capability
- ✅ Track number lifecycle (purchased → assigned → released)
- ✅ Support number recycling
- ✅ Query pool health easily
- ✅ Supports future features (multiple numbers per org)

**Cons:**
- ❌ Requires joins when fetching org data
- ❌ More complex implementation

---

### Recommendation:

For the initial 30-40 organizations with a hybrid pool approach, **Option 2 (dedicated table)** is recommended because:

1. You can pre-purchase 40 numbers and track them in the pool
2. Easy to assign available numbers instantly during org registration
3. Can implement auto-replenishment when pool drops below threshold
4. Supports the pending area code selection feature (when decided)
5. Enables number recycling if organizations churn

---

## Telephony Provider: Telnyx

### Overview:
- Modern telecommunications platform
- API-first design
- Strong integration with LiveKit
- Best choice for our use case

### Why Telnyx?

**Pros:**
✅ Most cost-effective (~$1/month per number in US)
✅ Excellent API documentation and SDKs
✅ Official LiveKit support and integration guides
✅ Global coverage (60+ countries)
✅ Instant number provisioning via API
✅ Good for startups and scale-ups
✅ SIP trunk support built-in
✅ Real-time number search and purchase
✅ No hidden fees
✅ HIPAA compliant
✅ No minimum commitments

**Cons:**
❌ Smaller company than Twilio (higher perceived risk)
❌ Less brand recognition
❌ Smaller community/fewer examples online

**Best For:**
- Startups looking for cost-effective solution
- Projects already using LiveKit (like ZScribe)
- Developers who value modern APIs
- Medical/healthcare applications requiring HIPAA compliance

### Pricing (US):
- Number rental: $1.00/month per number
- Outbound calls: $0.01/minute
- Inbound calls: $0.004/minute
- SMS (optional): $0.004/message

### Key Features:
- REST API for number management
- Real-time number search by area code
- Instant provisioning (no waiting period)
- SIP trunk integration included
- Webhook support for call events
- Number porting capabilities
- HIPAA compliant infrastructure
- 24/7 technical support

---

## Provisioning Strategies - Detailed Analysis

### Strategy 1: Shared Number Pool

**How It Works:**
1. Pre-purchase a pool of phone numbers (e.g., 10-50 numbers)
2. Store in database with status: "available" or "assigned"
3. When org registers, assign an available number from pool
4. When org is deleted, mark number as "available" again
5. Reuse numbers for new organizations

**Advantages:**
✅ Lower upfront cost (only pay for pool, not per org)
✅ Instant assignment (no API call during registration)
✅ Numbers can be recycled when orgs churn
✅ Predictable costs
✅ Simple to implement

**Disadvantages:**
❌ May run out of numbers if growth exceeds pool
❌ Organizations can't choose their number/area code
❌ Need to manage pool replenishment
❌ Numbers might have history from previous orgs

**Best For:**
- MVP/early stage
- Predictable growth
- Budget-conscious projects
- Testing and validation

**Cost Example (100 orgs):**
- Pool of 100 numbers: $100/month fixed
- Never changes regardless of org count

---

### Strategy 2: On-Demand Provisioning

**How It Works:**
1. When organization registers, immediately call Telnyx API
2. Search for available numbers (optionally filter by area code)
3. Purchase the number in real-time
4. Assign to organization
5. Store in database as permanently assigned
6. Release number back to Telnyx if org is deleted (or keep for reuse)

**Advantages:**
✅ Truly scalable (no pool limits)
✅ Organizations can choose area code/city
✅ Better user experience
✅ No number recycling concerns
✅ Only pay for active organizations

**Disadvantages:**
❌ API call required during registration (adds latency)
❌ Risk of API failure during registration
❌ Slightly higher complexity
❌ Potential for numbers to become unavailable mid-registration
❌ Costs scale directly with org count

**Best For:**
- Scale-ups and growing platforms
- Customer-facing applications
- When UX is priority
- International operations

**Cost Example (100 orgs):**
- 100 numbers: $100/month
- Scales linearly: 1000 orgs = $1000/month

---

### Strategy 3: Hybrid Pool Approach (Recommended)

**How It Works:**
1. Start with initial pool (30-40 numbers)
2. When org registers, assign from pool if available
3. If pool is low (< 5 numbers), auto-purchase 10 more in background
4. If org requests specific area code not in pool, purchase on-demand
5. Track pool health and replenish automatically
6. Recycle numbers back to pool when orgs churn

**Advantages:**
✅ Best of both worlds - speed + flexibility
✅ Cost-efficient at small scale
✅ Scalable to large operations
✅ Organizations can request area codes
✅ No registration delays (pool always ready)
✅ Automatic pool management
✅ Numbers can be recycled efficiently

**Disadvantages:**
❌ Most complex to implement
❌ Requires monitoring and automation
❌ Need to tune pool thresholds
❌ Potential for over-provisioning

**Best For:**
- Production applications
- Growing startups
- Projects with uncertain scale
- ZScribe's use case (Recommended!)

**Initial Setup (30-40 Organizations):**
- Initial pool: 40 numbers = $40/month
- Ready to serve first 40 organizations immediately
- Auto-replenishes as pool depletes below threshold

---

## Database Design Considerations

### Option A: Add Columns to Organizations Table

**Schema:**
```
organizations table:
- id
- name
- email
- phone_number (new)
- phone_number_sid (new - provider ID)
- phone_number_status (new)
- created_at
```

**Pros:**
✅ Simplest approach
✅ Direct relationship
✅ Fewer joins in queries
✅ Easy to understand

**Cons:**
❌ Less flexible (hard to track history)
❌ Can't easily support multiple numbers per org
❌ Harder to implement pool management
❌ Can't track number lifecycle independently

**Best For:** MVP, simple use cases

---

### Option B: Separate Phone Numbers Table (Recommended)

**Schema:**
```
phone_numbers table:
- id
- phone_number
- provider_id (Telnyx ID)
- organization_id (nullable - for pool management)
- status (available, assigned, suspended)
- area_code
- country_code
- purchased_at
- assigned_at
- released_at
```

**Pros:**
✅ More flexible and extensible
✅ Easy pool management
✅ Can track full lifecycle
✅ Supports multiple numbers per org (future)
✅ Can query pool health easily
✅ Historical tracking

**Cons:**
❌ Requires joins
❌ More complex queries
❌ Additional table to manage

**Best For:** Production, scalable applications (Recommended!)

---

## Outstanding Questions for Leadership

### Integration & Implementation Questions:

1. **Which service handles organization creation?**
   - Is it the data-api service that has the organization creation endpoint?
   - Or is there a separate auth/user service?
   - Need to know where to add phone number provisioning logic

2. **What's the organization creation endpoint path?**
   - `POST /organizations`?
   - Or `POST /auth/register` that creates everything?
   - Will determine integration approach

3. **Synchronous or Asynchronous registration flow?**
   - Does the user wait for the entire registration to complete?
   - Or does it return immediately and process in background?
   - Affects how we provision phone numbers

4. **When should the phone number be assigned?**
   - During organization creation (synchronously)?
   - After organization is created (background job)?
   - When they first try to make an intake call?

5. **Who needs to see the phone number?**
   - Does the doctor/provider see it in their dashboard?
   - Or is it just used internally for caller ID?
   - Affects UI/UX requirements

---

### Business & Strategy Questions:

1. **Area Code Preference** _(Priority Decision)_
   - Should organizations be able to choose their area code?
   - Or auto-assign any available number from the pool?
   - Impacts: UX complexity, pool management strategy, costs

2. **What happens to numbers when organization churns?**
   - Recycle immediately back to pool?
   - Hold for grace period (30-90 days)?
   - Release back to Telnyx to avoid costs?

3. **What's our budget for telephony?**
   - Initial phase (30-40 orgs): ~$85/month estimated
   - Growth phase (100 orgs): ~$255/month estimated
   - Need confirmation this aligns with budget expectations

4. **What's our expected growth trajectory?**
   - 30-40 orgs in 3 months? (current target)
   - 100 orgs in 6 months?
   - 1000 orgs in 1 year?
   - Determines pool sizing and auto-replenishment thresholds

5. **Who manages phone number issues?**
   - Customer support team?
   - Admin dashboard needed for phone number management?
   - Self-service for organizations?

6. **International requirements?**
   - US only initially?
   - Plan for international expansion?
   - Different pricing and regulations per country

---

## Implementation Timeline

### Recommended Timeline: 5 Days (6 hours/day)

**Assumptions:**
- ~6 hours of focused development per day
- Leadership decisions are made before starting
- Telnyx API credentials are available
- Access to Supabase database

---

#### **Day 1: Database & Pool Setup (6 hours)**

**Tasks:**
- Create `phone_numbers` table in Supabase (30 minutes)
- Set up Telnyx SDK and test API connection (1 hour)
- Write script to purchase initial 40 numbers (2 hours)
- Run the purchase script and populate database (30 minutes)
- Test queries and verify pool health (2 hours)

**Deliverable:** 40 numbers purchased and stored in database, ready to assign

---

#### **Day 2: Phone Number Service (6 hours)**

**Tasks:**
- Build phone number assignment service/function (3 hours)
  - Get available number from pool
  - Assign to organization
  - Update database with assignment
  - Handle edge cases (pool empty, etc.)
- Write pool monitoring logic (1.5 hours)
- Write auto-replenishment background job (1.5 hours)

**Deliverable:** Core phone number service working with assignment and monitoring

---

#### **Day 3: Integration with Registration (6 hours)**

**Tasks:**
- Identify organization creation endpoint in data-api (1 hour)
- Integrate phone number assignment into registration flow (3 hours)
- Add error handling and rollback logic (1 hour)
- Update `organizations.phone` field when assigned (1 hour)

**Deliverable:** Phone numbers automatically assigned during organization registration

---

#### **Day 4: Testing & Fixes (6 hours)**

**Tasks:**
- Test full registration flow end-to-end (2 hours)
- Create and test 5-10 test organizations (2 hours)
- Fix any bugs or edge cases discovered (2 hours)

**Deliverable:** Stable, tested implementation ready for production

---

#### **Day 5: Deployment & Monitoring (3-4 hours)**

**Tasks:**
- Deploy to Cloud Run (1 hour)
- Set up monitoring/alerts for pool health (1 hour)
- Create admin queries for viewing pool status (1 hour)
- Final production testing (1 hour)

**Deliverable:** Live in production, ready for first real organizations

---

### Aggressive Timeline: 3 Days (Minimal Viable Implementation)

**If timeline is critical**, you can implement in 3 days by skipping auto-replenishment initially:

**Day 1:** Database setup + Purchase 40 numbers (6 hours)
**Day 2:** Build assignment service + integrate with registration (6 hours)
**Day 3:** Testing + deployment (6 hours)

**Trade-off:** No auto-replenishment means you'll need to manually purchase more numbers when the pool runs low (around 30-35 organizations). Auto-replenishment can be added later when approaching capacity.

---

### Critical Dependencies (Must Have Before Starting):

**Required Information:**
1. ✅ Which service handles organization creation? (data-api vs auth service)
2. ✅ Organization creation endpoint path
3. ✅ Area code preference decision (affects Day 1 purchase strategy)

**Required Access:**
1. ✅ Telnyx API credentials (API Key and Profile ID)
2. ✅ Supabase database access with create table permissions
3. ✅ Access to organization registration code repository

**Can Be Decided Later:**
- Dashboard/admin tools (can build in Month 2)
- Number recycling policy (can implement when needed)
- Advanced monitoring and alerting

---

## Implementation Approaches

### Approach A: Synchronous Provisioning

**Flow:**
1. User creates organization
2. Backend immediately calls Telnyx API
3. Waits for number purchase
4. Returns organization with phone number
5. User sees complete org profile

**Pros:**
✅ Simple to implement
✅ User immediately sees their number
✅ No background jobs needed
✅ Clear error handling

**Cons:**
❌ Slower registration (API latency)
❌ Risk of partial failure
❌ User waits during API call
❌ Poor UX if API is slow

---

### Approach B: Asynchronous Provisioning

**Flow:**
1. User creates organization
2. Backend creates org without phone number
3. Returns immediately to user
4. Background job provisions number
5. Email/notification when ready

**Pros:**
✅ Fast user experience
✅ Handles API failures gracefully
✅ Can retry on failures
✅ Better scalability

**Cons:**
❌ More complex (requires job queue)
❌ User doesn't immediately have number
❌ Need notification system
❌ Organization temporarily incomplete

---

### Approach C: Hybrid (Pre-provisioned Pool) - Recommended

**Flow:**
1. Background system maintains pool of numbers
2. User creates organization
3. Backend assigns from pool instantly
4. Returns immediately with number
5. Background job replenishes pool

**Pros:**
✅ Fast user experience (instant)
✅ Reliable (no API dependency at registration)
✅ Can still handle area code requests
✅ Pool auto-manages in background

**Cons:**
❌ Need background job system
❌ Must monitor pool health
❌ Initial pool purchase required
❌ Small overhead of unused numbers

---

## Cost Analysis with Telnyx

### Initial Phase (30-40 Organizations)

**Setup Costs:**
- Initial pool purchase: 40 numbers × $1 = $40/month
- No setup fees with Telnyx
- **Total Setup: $40/month**

**Monthly Operating Costs (at 30 orgs):**
- Numbers: 40 × $1 = $40/month (pool with buffer)
- Estimated calls: ~1,500 calls/mo × 3 min avg × $0.01 = $45/month
- **Total Monthly: $85/month**

**Per Organization Cost:**
- $85 ÷ 30 organizations = **~$2.83/org/month**

---

### Growth Phase (40-100 Organizations)

**Monthly Operating Costs (at 100 orgs):**
- Numbers: 105 × $1 = $105/month (with 5% buffer)
- Estimated calls: ~5,000 calls/mo × 3 min avg × $0.01 = $150/month
- **Total Monthly: $255/month**

**Per Organization Cost:**
- $255 ÷ 100 organizations = **~$2.55/org/month**

---

### Cost Breakdown Components

**Fixed Costs:**
- Phone number rental: $1/number/month
- Buffer numbers (5-10% extra): ~$2-10/month

**Variable Costs:**
- Outbound calling: $0.01/minute
- Average call duration: 3-5 minutes
- Average calls per org: 50/month
- **Estimated per-org call cost: $1.50-2.50/month**

**Total Cost Per Organization:**
- Number rental: $1.00/month
- Call minutes: $1.50-2.50/month
- **Average: $2.50-3.50/org/month**

---

## Risks & Mitigation

### Risk 1: Provider API Downtime

**Impact:** Can't provision numbers during registration

**Mitigation:**
- Use pool approach (numbers ready in advance)
- Implement retry logic with exponential backoff
- Have manual provisioning fallback
- Monitor provider status pages

---

### Risk 2: Running Out of Numbers

**Impact:** Can't assign numbers to new organizations

**Mitigation:**
- Automated pool monitoring and alerts
- Auto-replenishment when below threshold
- Emergency manual purchase procedure
- Buffer numbers (10% extra)

---

### Risk 3: Number Recycling Issues

**Impact:** Patient calls old org's number, reaches new org

**Mitigation:**
- Grace period before recycling (30-90 days)
- Monitor incoming calls to recycled numbers
- Option to permanently retire high-traffic numbers
- Clear communication to patients about number changes

---

### Risk 4: Cost Overruns

**Impact:** Phone number costs exceed budget

**Mitigation:**
- Set pool size limits
- Monitor costs in real-time
- Alerts when approaching budget
- Automatic cleanup of unused numbers
- Consider releasing numbers after org churn

---

### Risk 5: Compliance/Regulatory Issues

**Impact:** Legal issues with automated calling

**Mitigation:**
- Use HIPAA-compliant provider
- Implement proper consent mechanisms
- Maintain call logs for audit
- Follow TCPA guidelines
- Regular compliance reviews

---

## Success Metrics

### Technical Metrics:
- **Number Assignment Success Rate**: Target 99.9%
- **Assignment Latency**: Target < 500ms (with pool)
- **Pool Health**: Never drop below threshold
- **API Reliability**: Track Telnyx uptime
- **Cost per Organization**: Monitor and optimize

### Business Metrics:
- **Customer Satisfaction**: Do orgs like their numbers?
- **Number Portability Requests**: How many want specific numbers?
- **Churn Impact**: Do numbers affect retention?
- **Support Tickets**: Phone number related issues

---

## Recommendations Summary

### Immediate Decisions:

1. **Provider**: Use **Telnyx**
   - Best cost-to-value ratio
   - Proven LiveKit compatibility
   - Modern API

2. **Strategy**: Implement **Hybrid Pool Approach**
   - Start with 40-number pool (for initial 30-40 organizations)
   - Auto-replenish at threshold
   - Support on-demand area code requests (if leadership approves)

3. **Database**: Use **Separate Phone Numbers Table**
   - More flexible and scalable
   - Better pool management
   - Track full lifecycle

4. **Provisioning**: **Pre-provisioned Pool with Background Jobs**
   - Instant assignment UX
   - Reliable and scalable
   - Graceful handling of edge cases

### Next Steps:

**Completed:**
1. ✅ Confirm current SIP trunk provider - **Telnyx** (ST_Nxq7fztyRozT)
2. ✅ Telnyx account active with test number (+17302060073)
3. ✅ LiveKit integration working and deployed on Cloud Run

**Pending Leadership Decisions:**
- ⏳ Area code preference (auto-assign vs organization choice)
- ⏳ Which service handles organization creation (data-api vs auth service)
- ⏳ When to assign phone numbers (during registration vs background job)
- ⏳ Budget confirmation (~$85/month for 30-40 orgs)
- ⏳ Number recycling policy when organizations churn

**Ready to Implement (After Decisions):**
1. ⬜ Create `phone_numbers` table in Supabase
2. ⬜ Purchase initial pool of 40 numbers via Telnyx API
3. ⬜ Build phone number assignment service
4. ⬜ Integrate with organization registration endpoint
5. ⬜ Implement pool monitoring and auto-replenishment
6. ⬜ Test with pilot organizations
7. ⬜ Roll out to first 30-40 organizations

---

## Conclusion

The phone number provisioning system is critical for the ZScribe platform's success. By choosing **Telnyx** as our telephony provider with a **hybrid pool approach**, we optimize for cost, user experience, and scalability.

### Why This Approach Works for ZScribe:

1. **Initial Scale (30-40 orgs):**
   - Purchase 40-number pool upfront = $40/month
   - Instant number assignment during org registration
   - Total cost ~$85/month including calls
   - Cost per organization: ~$2.83/month

2. **Cost-Effective:**
   - Telnyx pricing is 40-50% cheaper than alternatives
   - No hidden fees or minimum commitments
   - Predictable monthly costs

3. **Scalable:**
   - Auto-replenishment ensures pool never runs dry
   - Can grow from 40 to 400+ organizations seamlessly
   - On-demand provisioning for specific area codes

4. **User Experience:**
   - Organizations get numbers instantly during registration (no waiting)
   - Can request preferred area codes (if approved by leadership)
   - Professional caller ID for outbound calls
   - Seamless integration with current registration flow

5. **Technical Simplicity:**
   - Works with existing LiveKit SIP infrastructure
   - REST API for easy integration
   - HIPAA compliant for medical use case

This strategy positions ZScribe for sustainable growth from initial 30-40 organizations to hundreds or thousands, with minimal technical debt and manageable costs.
