import asyncio
from typing import Dict, Optional, List
from datetime import datetime

from src.models.call import Call, CallerInfo
from src.models.enums import CallStatus
from src.core.queue_manager import QueueManager
from src.agents.call_agent import AICallAgent
from src.ranking.priority_ranker import PriorityRanker
# NEW: Import the PatternDetector service
from src.services.pattern_detector import PatternDetector

class CallOrchestrator:
    """
    Central orchestrator for managing all calls
    Routes calls to operators or AI, manages queue, handles state
    """
    
    def __init__(self):
        # Active calls {call_id: Call}
        self.active_calls: Dict[str, Call] = {}
        
        # Operator status {operator_id: call_id or None}
        self.operators: Dict[str, Optional[str]] = {
            "operator_1": None  # One operator for demo
        }
        
        # Queue manager
        self.queue_manager = QueueManager()
        
        # AI agent
        self.ai_agent = AICallAgent()
        
        # Priority ranker
        self.ranker = PriorityRanker()

        # NEW: Initialize Pattern Detector
        self.pattern_detector = PatternDetector()
        
        # Call counter for display numbers
        self.call_counter = 0
        
        # WebSocket broadcast function (set externally)
        self.broadcast_func = None
    
    def set_broadcast_function(self, func):
        """Set the WebSocket broadcast function"""
        self.broadcast_func = func
    
    async def create_incoming_call(self, caller_phone: str) -> Call:
        """
        Create a new incoming call
        
        Args:
            caller_phone: Caller's phone number
            
        Returns:
            New Call object
        """
        self.call_counter += 1
        
        call = Call(
            call_number=self.call_counter,
            caller=CallerInfo(phone_number=caller_phone),
            status=CallStatus.INCOMING,
            created_at=datetime.now()
        )
        
        self.active_calls[call.id] = call
        
        # Broadcast update
        await self._broadcast_state()
        
        # Route the call
        await self._route_call(call)
        
        return call
    
    async def _route_call(self, call: Call):
        """
        Route call to operator or AI
        
        Args:
            call: Call to route
        """
        # Check if operator available
        available_operator = self._get_available_operator()
        
        if available_operator:
            # Route to human operator
            call.status = CallStatus.OPERATOR_HANDLING
            call.assigned_to = available_operator
            call.answered_at = datetime.now()
            self.operators[available_operator] = call.id
            
            await self._broadcast_state()
        else:
            # Route to AI agent
            call.status = CallStatus.AI_HANDLING
            call.assigned_to = "ai_agent"
            call.answered_at = datetime.now()
            
            await self._broadcast_state()
            
            # AI will handle conversation
            # (Actual conversation happens via handle_caller_message)
    
    def _get_available_operator(self) -> Optional[str]:
        """Find an available operator"""
        for op_id, current_call in self.operators.items():
            if current_call is None:
                return op_id
        return None
    
    async def handle_caller_message(self, call_id: str, caller_text: str) -> str:
        """
        Process message from caller (for AI-handled calls)
        
        Args:
            call_id: ID of the call
            caller_text: What caller said
            
        Returns:
            AI's response
        """
        call = self.active_calls.get(call_id)
        if not call:
            return "Call not found"
        if call.status != CallStatus.AI_HANDLING:
            return ""
        
        # AI processes message
        ai_response = await self.ai_agent.handle_caller_message(call, caller_text)
        
        # Check if we have enough info to queue
        if self.ai_agent.has_sufficient_info(call):
            await self._move_call_to_queue(call)
        
        await self._broadcast_state()
        
        return ai_response
    
    async def _move_call_to_queue(self, call: Call):
        """Move call from AI handling to queue"""
        # Calculate severity
        self.ranker.calculate_and_update_call(call)
        
        # Change status
        call.status = CallStatus.QUEUED
        
        # Add to queue
        self.queue_manager.add_to_queue(call.id)
        
        # Re-rank entire queue
        self.queue_manager.rerank_queue(self.active_calls)
        
        await self._broadcast_state()
    
    async def operator_completes_call(self, operator_id: str):
        """
        Operator finishes their current call
        
        Args:
            operator_id: ID of operator finishing call
        """
        # Mark current call as complete
        current_call_id = self.operators[operator_id]
        if current_call_id and current_call_id in self.active_calls:
            self.active_calls[current_call_id].status = CallStatus.COMPLETED
            self.active_calls[current_call_id].completed_at = datetime.now()
        
        # Free operator
        self.operators[operator_id] = None
        
        # Assign next call from queue
        next_call_id = self.queue_manager.get_next_call()
        if next_call_id:
            self.queue_manager.remove_from_queue(next_call_id)
            next_call = self.active_calls[next_call_id]
            
            next_call.status = CallStatus.OPERATOR_HANDLING
            next_call.assigned_to = operator_id
            self.operators[operator_id] = next_call_id
        
        await self._broadcast_state()
    
    def get_state(self) -> dict:
        """Get current system state for broadcasting"""
        # Get active calls (not completed)
        active = [
            c.model_dump(mode='json') 
            for c in self.active_calls.values() 
            if c.status != CallStatus.COMPLETED
        ]
        
        # Get queued calls
        queued = [
            self.active_calls[cid].model_dump(mode='json')
            for cid in self.queue_manager.queue
            if cid in self.active_calls
        ]
        
        # Calculate stats
        stats = {
            "total_active": len(active),
            "ai_handled": len([c for c in active if c.get("assigned_to") == "ai_agent"]),
            "queued": len(queued),
            "completed_today": len([c for c in self.active_calls.values() if c.status == CallStatus.COMPLETED])
        }

        # NEW: Detect widespread patterns/alerts
        all_calls_list = list(self.active_calls.values())
        system_alerts = self.pattern_detector.detect_patterns(all_calls_list)
        
        return {
            "active_calls": active,
            "queue": queued,
            "operators": self.operators,
            "stats": stats,
            "alerts": system_alerts  # NEW: Include alerts in state
        }
    
    async def _broadcast_state(self):
        """Broadcast current state via WebSocket"""
        if self.broadcast_func:
            state = self.get_state()
            await self.broadcast_func(state)
