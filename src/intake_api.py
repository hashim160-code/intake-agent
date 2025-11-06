import logging
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from src.make_call import make_call

logger = logging.getLogger("intake-api")


class IntakeCallRequest(BaseModel):
    phone_number: str = Field(..., min_length=7, description="Destination phone number in E.164 format")
    template_id: str
    organization_id: str
    patient_id: str
    intake_id: str
    greeting_override: Optional[str] = Field(None, description="Optional pre-composed greeting already delivered to the patient.")


class IntakeCallResponse(BaseModel):
    status: str = "queued"
    room_name: str
    dispatch_id: Optional[str] = None
    metadata: Dict[str, Any]
    agent_name: str


app = FastAPI(title="ZScribe Intake Call API", version="0.1.0")


@app.get("/health", response_model=Dict[str, str])
async def health() -> Dict[str, str]:
    """Simple readiness endpoint."""
    return {"status": "ok"}


@app.post(
    "/intake-calls",
    response_model=IntakeCallResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def schedule_intake_call(payload: IntakeCallRequest) -> IntakeCallResponse:
    """Trigger an intake call via LiveKit dispatch."""
    try:
        dispatch_info = await make_call(
            phone_number=payload.phone_number,
            template_id=payload.template_id,
            organization_id=payload.organization_id,
            patient_id=payload.patient_id,
            intake_id=payload.intake_id,
            prefilled_greeting=payload.greeting_override,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to dispatch intake call for %s", payload.intake_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to dispatch intake call",
        ) from exc

    return IntakeCallResponse(**dispatch_info, status="queued")


def main() -> None:
    import uvicorn

    host = os.getenv("INTAKE_API_HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("INTAKE_API_PORT", "8080"))
    uvicorn.run("src.intake_api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
