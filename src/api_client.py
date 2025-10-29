"""
API client for fetching data from database
"""

import httpx
import os
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "http://localhost:4000"

async def fetch_template_from_api(template_id: str) -> Optional[Dict]:
    """
    Fetch template data from the API
    
    Args:
        template_id (str): The UUID of the template to fetch
        
    Returns:
        Dict: Template data or None if not found
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/templates/{template_id}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("template")
                else:
                    print(f"API Error: {data.get('message')}")
                    return None
            else:
                print(f"HTTP Error: {response.status_code}")
                return None
                
    except Exception as e:
        print(f"Error fetching template: {e}")
        return None

async def fetch_patient_from_api(patient_id: str) -> Optional[Dict]:
    """
    Fetch patient data from the API
    
    Args:
        patient_id (str): The UUID of the patient to fetch
        
    Returns:
        Dict: Patient data or None if not found
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/patients/{patient_id}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("patient")
                else:
                    print(f"API Error: {data.get('message')}")
                    return None
            else:
                print(f"HTTP Error: {response.status_code}")
                return None
                
    except Exception as e:
        print(f"Error fetching patient: {e}")
        return None

async def fetch_organization_from_api(organization_id: str) -> Optional[Dict]:
    """
    Fetch organization data from the API
    
    Args:
        organization_id (str): The UUID of the organization to fetch
        
    Returns:
        Dict: Organization data or None if not found
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/organizations/{organization_id}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("organization")
                else:
                    print(f"API Error: {data.get('message')}")
                    return None
            else:
                print(f"HTTP Error: {response.status_code}")
                return None
                
    except Exception as e:
        print(f"Error fetching organization: {e}")
        return None

async def test_api_connection() -> bool:
    """Test if the API is running"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/health")
            return response.status_code == 200
    except:
        return False


# for storing the transcript in db
async def save_transcript_to_db(intake_id: str, transcript_data: dict) -> bool:
    """
    Save transcript directly to Supabase database

    Args:
        intake_id: UUID of the intake record
        transcript_data: Transcript JSON (from session.history.to_dict())

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from supabase import create_client

        # Create Supabase client
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

        # Update the intakes table with transcript data
        response = supabase.table("intakes").update({
            "transcription": transcript_data
        }).eq("id", intake_id).execute()

        # Check if successful
        if response.data:
            print(f"Transcript saved to database for intake {intake_id}")
            return True
        else:
            print(f"Failed to save transcript - no data returned")
            return False

    except Exception as e:
        print(f"Error saving transcript to database: {e}")
        return False