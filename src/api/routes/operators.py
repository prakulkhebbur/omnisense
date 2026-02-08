from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.core.orchestrator import CallOrchestrator

router = APIRouter(prefix="/api/operators", tags=["operators"])

orchestrator: Optional[CallOrchestrator] = None

def set_orchestrator(orch: CallOrchestrator):
    """Set the orchestrator instance"""
    global orchestrator
    orchestrator = orch

class CompleteCallRequest(BaseModel):
    operator_id: str

@router.post("/complete-call")
async def complete_call(request: CompleteCallRequest):
    """
    Mark operator's current call as complete
    Auto-assigns next call from queue if available
    """
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    if request.operator_id not in orchestrator.operators:
        raise HTTPException(status_code=404, detail="Operator not found")
    
    # Complete call and assign next
    await orchestrator.operator_completes_call(request.operator_id)
    
    # Get operator's new call (if any)
    new_call_id = orchestrator.operators[request.operator_id]
    
    return {
        "operator_id": request.operator_id,
        "new_call_id": new_call_id,
        "message": "Call completed" + (f" and assigned call {new_call_id}" if new_call_id else "")
    }

@router.get("/{operator_id}/current-call")
async def get_current_call(operator_id: str):
    """Get operator's current call"""
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    if operator_id not in orchestrator.operators:
        raise HTTPException(status_code=404, detail="Operator not found")
    
    call_id = orchestrator.operators[operator_id]
    
    if not call_id:
        return {"operator_id": operator_id, "current_call": None}
    
    call = orchestrator.active_calls.get(call_id)
    
    return {
        "operator_id": operator_id,
        "current_call": call.model_dump(mode='json') if call else None
    }

@router.get("/")
async def get_all_operators():
    """Get all operators and their status"""
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    operators_status = []
    for op_id, call_id in orchestrator.operators.items():
        operators_status.append({
            "operator_id": op_id,
            "status": "busy" if call_id else "available",
            "current_call_id": call_id
        })
    
    return {"operators": operators_status}