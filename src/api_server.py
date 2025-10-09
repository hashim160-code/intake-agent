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
    """Fetch a specific template by ID with all fields"""
    try:
        # Query the templates table with all fields
        response = supabase.table("templates").select("*").eq("id", template_id).execute()
        
        if response.data and len(response.data) > 0:
            template = response.data[0]
            return {
                "success": True,
                "template": {
                    "id": template["id"],
                    "template_name": template["template_name"],
                    "structure": template["structure"],
                    "instructions_for_ai": template["instructions_for_ai"],
                    "template_type": template["template_type"],
                    "questions": template["questions"],
                    "organization_id": template["organization_id"],
                    "created_at": template["created_at"],
                    "updated_at": template["updated_at"]
                }
            }
        else:
            return {"success": False, "message": "Template not found"}
            
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)