"""
API client for fetching templates from database
"""

import httpx
import os
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "http://localhost:3000"

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

async def test_api_connection() -> bool:
    """Test if the API is running"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/health")
            return response.status_code == 200
    except:
        return False