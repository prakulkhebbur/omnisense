from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from src.core.orchestrator import CallOrchestrator
from src.models.call import Call

router = APIRouter(prefix="/api/calls", tags=["calls"])

# Request/Response models
class CreateCallRequest(BaseModel):
    caller_phone: str

class CallResponse(BaseModel):
    call_id: str
    call_number: int
    status: str
    message: str

class MessageRequest(BaseModel):
    text: str

# This will be set by main.py
orchestrator: Optional[CallOrchestrator] = None

def set_orchestrator(orch: CallOrchestrator):
    """Set the orchestrator instance"""
    global orchestrator
    orchestrator = orch

@router.post("/create", response_model=CallResponse)
async def create_call(request: CreateCallRequest):
    """
    Create a new incoming call
    
    Simulates a caller dialing in
    """
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    # Create incoming call
    call = await orchestrator.create_incoming_call(request.caller_phone)
    
    return CallResponse(
        call_id=call.id,
        call_number=call.call_number,
        status=call.status.value,
        message=f"Call #{call.call_number} created and routed"
    )

@router.post("/{call_id}/message")
async def send_message(call_id: str, request: MessageRequest):
    """
    Send a message from caller (for AI-handled calls)
    
    Simulates caller speaking
    """
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    if call_id not in orchestrator.active_calls:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Process caller message
    ai_response = await orchestrator.handle_caller_message(call_id, request.text)
    
    return {
        "call_id": call_id,
        "ai_response": ai_response,
        "call_status": orchestrator.active_calls[call_id].status.value
    }

@router.get("/{call_id}")
async def get_call(call_id: str):
    """Get details of a specific call"""
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    if call_id not in orchestrator.active_calls:
        raise HTTPException(status_code=404, detail="Call not found")
    
    call = orchestrator.active_calls[call_id]
    return call.model_dump(mode='json')

@router.get("/")
async def get_all_calls():
    """Get all active calls"""
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    return {
        "calls": [c.model_dump(mode='json') for c in orchestrator.active_calls.values()]
    }

@router.delete("/{call_id}")
async def delete_call(call_id: str):
    """Delete/end a call"""
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    if call_id not in orchestrator.active_calls:
        raise HTTPException(status_code=404, detail="Call not found")
    
    del orchestrator.active_calls[call_id]
    
    return {"message": f"Call {call_id} deleted"}