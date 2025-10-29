import asyncio
import os
import logging
import json
from pathlib import Path
from dotenv import load_dotenv
from livekit import api

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger("make-call")
logger.setLevel(logging.INFO)

# Configuration
room_name = "my-room"
outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")

async def make_call(phone_number: str, template_id: str, organization_id: str,
                   patient_id: str, intake_id: str):
    """Create a dispatch and add a SIP participant to call the phone number"""
    lkapi = api.LiveKitAPI()
    
    # Create unique room name
    import uuid
    session_id = str(uuid.uuid4())[:8]
    room_name = f"intake-{session_id}"
    
    # Use agent_name to pass data (more professional)
    agent_name = "intake-agent"
    
    # Store data in metadata
    metadata = json.dumps({
    "intake_id": intake_id,
    "template_id": template_id,
    "organization_id": organization_id,
    "patient_id": patient_id,
    "phone_number": phone_number
})
    
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
        return
    
    logger.info(f"Dialing {phone_number} to room {room_name}")
    
    try:
        # Create SIP participant to initiate the call
        sip_participant = await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=room_name,  # Use the same unique room name
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity="phone_user",
            )
        )
        logger.info(f"Created SIP participant: {sip_participant}")
    except Exception as e:
        logger.error(f"Error creating SIP participant: {e}")
    
    # Close API connection
    await lkapi.aclose()

async def main():
    # Test data
    phone_number = "+19712656795"
    template_id = "8e86ef66-465f-4a5c-8ad4-ed6fca5c493e"
    organization_id = "0da4a59a-275f-4f2d-92f0-5e0c60b0f1da"
    patient_id = "4b3a1edb-76c5-46f4-ad0f-3c164348202b"
    intake_id = "a8adaf8a-ed8e-48d2-9d45-8130e9c164e3"
    await make_call(phone_number, template_id, organization_id, patient_id, intake_id)

if __name__ == "__main__":
    asyncio.run(main())