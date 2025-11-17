"""
Database utilities for accessing Supabase
"""
import os
from typing import Optional
from supabase import create_client, Client


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
            print(f"❌ Organization not found: {organization_id}")
            return None

        org_data = response.data[0]
        phone_number = org_data.get("phone")

        if phone_number:
            print(f"✅ Found phone number for organization {organization_id}: {phone_number}")
        else:
            print(f"⚠️  Organization {organization_id} exists but has no phone number assigned")

        return phone_number

    except Exception as e:
        print(f"❌ Error fetching organization phone number: {e}")
        return None
