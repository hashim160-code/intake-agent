"""
Database utilities for accessing Supabase
"""
import os
import logging
from typing import Optional, Dict
from supabase import create_client, Client

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """
    Get Supabase client instance

    Returns:
        Client: Supabase client
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

    return create_client(supabase_url, supabase_key)


def get_organization_phone(organization_id: str) -> Optional[str]:
    """
    Get organization's phone number from database

    Args:
        organization_id: UUID of the organization

    Returns:
        Phone number string (e.g., "+19712656795") or None if not found/assigned
    """
    try:
        supabase = get_supabase_client()

        # Query organizations table for phone number
        response = supabase.table("organizations").select("phone").eq("id", organization_id).execute()

        # Check if organization exists
        if not response.data or len(response.data) == 0:
            logger.warning("Organization not found: %s", organization_id)
            return None

        org_data = response.data[0]
        phone_number = org_data.get("phone")

        if phone_number:
            logger.info("Found phone number for organization %s: %s", organization_id, phone_number)
        else:
            logger.warning("Organization %s exists but has no phone number assigned", organization_id)

        return phone_number

    except Exception as e:
        logger.error("Error fetching organization phone number: %s", e, exc_info=True)
        return None


# ===================================================================
# Async functions for LiveKit agent (direct Supabase queries)
# ===================================================================

async def fetch_template(template_id: str) -> Optional[Dict]:
    """
    Fetch template data directly from Supabase (async)

    Args:
        template_id: UUID of the template to fetch

    Returns:
        Dict: Template data with id, template_name, instructions_for_ai, questions
              or None if not found
    """
    try:
        supabase = get_supabase_client()

        # Note: Supabase Python client doesn't have native async support yet
        # But the underlying httpx client handles it efficiently
        response = supabase.table("templates").select(
            "id, template_name, instructions_for_ai, questions"
        ).eq("id", template_id).execute()

        if response.data and len(response.data) > 0:
            template = response.data[0]
            logger.info("Fetched template: %s", template_id)
            return {
                "id": template["id"],
                "template_name": template["template_name"],
                "instructions_for_ai": template["instructions_for_ai"],
                "questions": template["questions"]
            }
        else:
            logger.warning("Template not found: %s", template_id)
            return None

    except Exception as e:
        logger.error("Error fetching template %s: %s", template_id, e, exc_info=True)
        return None


async def fetch_patient(patient_id: str) -> Optional[Dict]:
    """
    Fetch patient data directly from Supabase (async)

    Args:
        patient_id: UUID of the patient to fetch

    Returns:
        Dict: Patient data with id and full_name, or None if not found
    """
    try:
        supabase = get_supabase_client()

        response = supabase.table("patients").select(
            "id, full_name"
        ).eq("id", patient_id).execute()

        if response.data and len(response.data) > 0:
            patient = response.data[0]
            logger.info("Fetched patient: %s", patient_id)
            return {
                "id": patient["id"],
                "full_name": patient["full_name"]
            }
        else:
            logger.warning("Patient not found: %s", patient_id)
            return None

    except Exception as e:
        logger.error("Error fetching patient %s: %s", patient_id, e, exc_info=True)
        return None


async def fetch_organization(organization_id: str) -> Optional[Dict]:
    """
    Fetch organization data directly from Supabase (async)

    Args:
        organization_id: UUID of the organization to fetch

    Returns:
        Dict: Organization data with id and name, or None if not found
    """
    try:
        supabase = get_supabase_client()

        response = supabase.table("organizations").select(
            "id, name"
        ).eq("id", organization_id).execute()

        if response.data and len(response.data) > 0:
            organization = response.data[0]
            logger.info("Fetched organization: %s", organization_id)
            return {
                "id": organization["id"],
                "name": organization["name"]
            }
        else:
            logger.warning("Organization not found: %s", organization_id)
            return None

    except Exception as e:
        logger.error("Error fetching organization %s: %s", organization_id, e, exc_info=True)
        return None


async def save_transcript(intake_id: str, transcript_data: Dict) -> bool:
    """
    Save transcript directly to Supabase (async)

    Args:
        intake_id: UUID of the intake record
        transcript_data: Transcript JSON (from session.history.to_dict())

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        supabase = get_supabase_client()

        # Update the intakes table with transcript data
        response = supabase.table("intakes").update({
            "transcription": transcript_data
        }).eq("id", intake_id).execute()

        # Check if successful
        if response.data:
            logger.info("Transcript saved to database for intake: %s", intake_id)
            return True
        else:
            logger.error("Failed to save transcript - no data returned for intake: %s", intake_id)
            return False

    except Exception as e:
        logger.error("Error saving transcript for intake %s: %s", intake_id, e, exc_info=True)
        return False
