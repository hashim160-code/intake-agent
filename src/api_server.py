from fastapi import FastAPI
import uvicorn
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="ZScribe Intake Agent API", version="0.1.0")

@app.get("/")
async def root():
    return {"message": "ZScribe Intake Agent API is running!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Fetch specific template fields by ID"""
    try:
        # Select only required fields
        response = supabase.table("templates").select(
            "id, template_name, instructions_for_ai, questions"
        ).eq("id", template_id).execute()
        
        if response.data and len(response.data) > 0:
            template = response.data[0]
            return {
                "success": True,
                "template": {
                    "id": template["id"],
                    "template_name": template["template_name"],
                    "instructions_for_ai": template["instructions_for_ai"],
                    "questions": template["questions"]
                }
            }
        else:
            return {"success": False, "message": "Template not found"}
            
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

@app.get("/patients/{patient_id}")
async def get_patient(patient_id: str):
    """Fetch patient name by ID"""
    try:
        # Select only full_name
        response = supabase.table("patients").select(
            "id, full_name"
        ).eq("id", patient_id).execute()
        
        if response.data and len(response.data) > 0:
            patient = response.data[0]
            return {
                "success": True,
                "patient": {
                    "id": patient["id"],
                    "full_name": patient["full_name"]
                }
            }
        else:
            return {"success": False, "message": "Patient not found"}
            
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

@app.get("/organizations/{organization_id}")
async def get_organization(organization_id: str):
    """Fetch organization name by ID"""
    try:
        # Select only id and name
        response = supabase.table("organizations").select(
            "id, name"
        ).eq("id", organization_id).execute()
        
        if response.data and len(response.data) > 0:
            organization = response.data[0]
            return {
                "success": True,
                "organization": {
                    "id": organization["id"],
                    "name": organization["name"]
                }
            }
        else:
            return {"success": False, "message": "Organization not found"}
            
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)