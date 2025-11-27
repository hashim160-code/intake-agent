import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from livekit import api
from src.db_utils import get_organization_phone

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger("make-call")
logger.setLevel(logging.INFO)

# Configuration
outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")

async def make_call(phone_number: str, template_id: str, organization_id: str,
                    patient_id: str, intake_id: str, prefilled_greeting: Optional[str] = None) -> Dict[str, Any]:
    """Create a dispatch and add a SIP participant to call the phone number."""

    # Fetch organization's phone number for caller ID
    org_phone_number = get_organization_phone(organization_id)

    if not org_phone_number:
        error_msg = f"Organization {organization_id} does not have a phone number assigned. Please assign a phone number before making calls."
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"Using caller ID: {org_phone_number} for organization {organization_id}")

    lkapi = api.LiveKitAPI()

    # Create unique room name
    import uuid
    session_id = str(uuid.uuid4())[:8]
    room_name = f"intake-{session_id}"
    agent_name = "intake-agent"
    
    metadata_payload: Dict[str, Any] = {
        "intake_id": intake_id,
        "template_id": template_id,
        "organization_id": organization_id,
        "patient_id": patient_id,
        "phone_number": phone_number,
    }
    if prefilled_greeting:
        metadata_payload["prefilled_greeting"] = prefilled_greeting
    
    metadata = json.dumps(metadata_payload)
    
    logger.info(f"Creating dispatch with metadata: {metadata}")
    
    # Create agent dispatch with metadata
    dispatch = await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name=agent_name,
            room=room_name,
            metadata=metadata
        )
    )
    logger.info(f"Created dispatch: {dispatch}")
    
    # Create SIP participant to make the call
    if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
        logger.error("SIP_OUTBOUND_TRUNK_ID is not set or invalid")
        await lkapi.aclose()
        raise RuntimeError("SIP_OUTBOUND_TRUNK_ID is not set or invalid")
    
    logger.info(f"Dialing {phone_number} to room {room_name}")
    
    try:
        # Create SIP participant to initiate the call
        sip_participant = await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=room_name,  # Use the same unique room name
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity="phone_user",
                sip_number=org_phone_number,  # Dynamic caller ID!
            )
        )
        logger.info(f"Created SIP participant with caller ID {org_phone_number}: {sip_participant}")
    except Exception as e:
        logger.error(f"Error creating SIP participant: {e}")
    
    # Close API connection
    await lkapi.aclose()
    
    dispatch_id = getattr(dispatch, "id", None)
    return {
        "room_name": room_name,
        "dispatch_id": dispatch_id,
        "metadata": metadata_payload,
        "agent_name": agent_name,
    }

async def main():
    # Test data
    phone_number = "+19712656795"
    template_id = "6465cac8-816a-4245-930c-b7bdeb35d595"
    organization_id = "e9e5b6f6-e2bb-4b5f-8650-267f045a1798"
    patient_id = "d744fe25-6961-4111-b0e6-00ad232b2b14"
    intake_id = "14f32316-827e-413e-b655-0a9768b99a57"
    result = await make_call(phone_number, template_id, organization_id, patient_id, intake_id)
    logger.info("Dispatch created: %s", result)

if __name__ == "__main__":
    asyncio.run(main())