import asyncio
from typing import Dict, List, Optional
from datetime import datetime

# Import your existing models and logic
from src.models.call import Call, CallStatus, EmergencyType, SeverityLevel
from src.models.operator import Operator, OperatorStatus
from src.agents.call_agent import AICallAgent
from src.core.priority_ranker import PriorityRanker

class CallOrchestrator:
    def __init__(self):
        # --- STATE MANAGEMENT (PRESERVED) ---
        self.active_calls: Dict[str, Call] = {}
        self.call_queue: List[str] = []  # IDs of calls waiting for humans
        self.operators: Dict[str, dict] = {} # {op_id: {'model': Operator, 'ws': WebSocket, 'current_call': str}}
        
        # --- AI & LOGIC ENGINES (PRESERVED) ---
        self.ai_agent = AICallAgent()
        self.ranker = PriorityRanker()
        
        # --- BACKGROUND TASKS (PRESERVED) ---
        self.is_running = False
        self._queue_task = None

    async def start(self):
        """Start the background queue processor"""
        self.is_running = True
        self._queue_task = asyncio.create_task(self._process_queue_loop())
        print("🚀 Orchestrator Started: Priority Queue Active")

    async def stop(self):
        self.is_running = False
        if self._queue_task:
            self._queue_task.cancel()

    # =========================================================================
    #  PART 1: CALL LIFECYCLE (Merged)
    # =========================================================================

    async def create_incoming_call(self, caller_phone: str) -> Call:
        """Called when a victim connects via WebSocket"""
        # 1. Create Call Object (Standard)
        call = Call(caller={"phone_number": caller_phone})
        self.active_calls[call.id] = call
        print(f"📞 New Call Created: {call.id} ({caller_phone})")

        # 2. Initial Routing: Try Human First, then AI
        # (This preserves your logic of "Operators First", but falls back to AI)
        assigned_op_id = await self._find_available_operator(call)
        
        if assigned_op_id:
            await self._assign_call(call.id, assigned_op_id)
        else:
            print(f"🤖 No operators available. Assigning {call.id} to AI Agent.")
            call.assigned_to = "AI_AGENT"
            call.status = CallStatus.IN_PROGRESS
            self.call_queue.append(call.id) # Add to queue for future humans
            
        return call

    async def handle_caller_message(self, call_id: str, text: str) -> Optional[str]:
        """
        Process text from STT (Speech-to-Text).
        Crucial: Updates transcript, recalculates priority, and gets AI response.
        """
        call = self.active_calls.get(call_id)
        if not call: return None

        # 1. Update Transcript & Extract Info (Passive AI)
        # We ALWAYS run this, even if human is talking, to keep the Dashboard updated.
        ai_response = await self.ai_agent.handle_caller_message(call, text)
        
        # 2. Dynamic Priority Re-Ranking (PRESERVED FEATURE)
        old_score = call.severity_score
        new_score = self.ranker.calculate_score(call)
        call.severity_score = new_score
        
        # If score spikes (e.g. "Gunshot"), re-sort the queue immediately
        if new_score > old_score + 10:
            print(f"🔥 Priority Escalation for {call_id}: {old_score} -> {new_score}")
            self._sort_queue()

        # 3. Return AI Response ONLY if AI is the active agent
        if call.assigned_to == "AI_AGENT":
            return ai_response
        
        return None  # If human assigned, AI stays silent

    # =========================================================================
    #  PART 2: OPERATOR MANAGEMENT (The New Portal Logic)
    # =========================================================================

    async def register_operator(self, operator_id: str, websocket):
        """Operator joins via /ws/operator/{id}"""
        op = Operator(id=operator_id, name=f"Officer {operator_id}", status=OperatorStatus.AVAILABLE)
        
        self.operators[operator_id] = {
            'model': op,
            'ws': websocket,
            'current_call': None
        }
        print(f"👨‍💼 Operator {operator_id} joined pool.")
        
        # Immediate check: Is there a high-priority call waiting?
        await self._process_queue_once()

    async def unregister_operator(self, operator_id: str):
        """Operator disconnects"""
        if operator_id in self.operators:
            # Safe Cleanup: If they had a call, dump it back to AI
            current_call_id = self.operators[operator_id]['current_call']
            if current_call_id:
                print(f"⚠️ Operator {operator_id} lost. Returning {current_call_id} to AI.")
                call = self.active_calls.get(current_call_id)
                if call:
                    call.assigned_to = "AI_AGENT"
                    self.call_queue.insert(0, call.id) # Prioritize this abandoned call
            
            del self.operators[operator_id]
            print(f"👨‍💼 Operator {operator_id} left.")

    # =========================================================================
    #  PART 3: AUDIO ROUTING (The Switchboard)
    # =========================================================================

    async def route_audio_victim_to_operator(self, call_id: str, audio_bytes: bytes):
        """Relay Audio: Victim -> Assigned Operator"""
        call = self.active_calls.get(call_id)
        if not call or not call.assigned_to or call.assigned_to == "AI_AGENT":
            return

        op_data = self.operators.get(call.assigned_to)
        if op_data and op_data['ws']:
            try:
                await op_data['ws'].send_bytes(audio_bytes)
            except Exception as e:
                print(f"Audio Routing Error (V->O): {e}")

    async def route_audio_operator_to_victim(self, operator_id: str, audio_bytes: bytes, manager):
        """Relay Audio: Operator -> Victim"""
        op_data = self.operators.get(operator_id)
        if not op_data or not op_data['current_call']:
            return

        call_id = op_data['current_call']
        # Use ConnectionManager to find victim socket
        if manager:
            await manager.send_audio_to_victim(call_id, audio_bytes)

    # =========================================================================
    #  PART 4: QUEUE & ASSIGNMENT LOGIC (The Brain)
    # =========================================================================

    async def _process_queue_loop(self):
        """Continuous background loop (PRESERVED)"""
        while self.is_running:
            await self._process_queue_once()
            await asyncio.sleep(2) 

    async def _process_queue_once(self):
        """Check queue and assign to available operators"""
        if not self.call_queue: return

        # 1. Sort queue by priority (Critical first)
        self._sort_queue()
        
        # 2. Try to assign top calls
        for call_id in list(self.call_queue): 
            call = self.active_calls.get(call_id)
            if not call: 
                self.call_queue.remove(call_id)
                continue

            # Find op
            op_id = await self._find_available_operator(call)
            if op_id:
                await self._assign_call(call.id, op_id)
                self.call_queue.remove(call_id)
            else:
                break # No operators left

    async def _find_available_operator(self, call: Call) -> Optional[str]:
        """Simple First-Available strategy"""
        for op_id, data in self.operators.items():
            if data['model'].status == OperatorStatus.AVAILABLE:
                return op_id
        return None

    async def _assign_call(self, call_id: str, operator_id: str):
        """Execute Assignment: Updates State & Notifies Frontend"""
        op_data = self.operators.get(operator_id)
        call = self.active_calls.get(call_id)
        if not op_data or not call: return

        # Update State
        call.assigned_to = operator_id
        call.status = CallStatus.IN_PROGRESS
        
        op_data['current_call'] = call_id
        op_data['model'].status = OperatorStatus.BUSY

        # Notify Operator Frontend (The "Ring" logic)
        msg = {
            "type": "new_assignment",
            "caller_id": call.caller.phone_number,
            "location": call.location.address if call.location else "Unknown",
            "severity": f"{call.severity_level.value} ({call.severity_score})",
            "summary": call.summary
        }
        await op_data['ws'].send_json(msg)
        print(f"🔗 ASSIGNED: Call {call_id} -> Operator {operator_id}")

    def _sort_queue(self):
        """Sort call queue: Highest Severity Score first (PRESERVED)"""
        self.call_queue.sort(
            key=lambda cid: self.active_calls[cid].severity_score if cid in self.active_calls else 0, 
            reverse=True
        )

    # =========================================================================
    #  PART 5: API ACTIONS (For Dashboard Buttons)
    # =========================================================================

    async def force_assign_operator(self, call_id: str, operator_id: str):
        """
        Manual Override: Dashboard 'Switch' button.
        Allows Operator to 'Steal' a high-priority call from the AI.
        """
        op_data = self.operators.get(operator_id)
        if not op_data: return False

        # 1. If Operator is busy, put their OLD victim back to AI
        current_call_id = op_data['current_call']
        if current_call_id:
            old_call = self.active_calls.get(current_call_id)
            if old_call:
                old_call.assigned_to = "AI_AGENT"
                self.call_queue.insert(0, current_call_id) # Put back in queue
        
        # 2. Assign NEW call to Operator
        if call_id in self.call_queue:
            self.call_queue.remove(call_id)
            
        await self._assign_call(call_id, operator_id)
        return True

    async def complete_call(self, operator_id: str):
        """Operator clicks 'Complete'"""
        op_data = self.operators.get(operator_id)
        if not op_data or not op_data['current_call']: return

        call_id = op_data['current_call']
        call = self.active_calls.get(call_id)
        
        if call:
            call.status = CallStatus.COMPLETED
            call.completed_at = datetime.now()
            print(f"✅ COMPLETED: Call {call_id} by {operator_id}")

        # Free up operator
        op_data['current_call'] = None
        op_data['model'].status = OperatorStatus.AVAILABLE
        
        await op_data['ws'].send_json({"type": "call_ended"})

        # Check queue immediately to see if anyone is waiting
        await self._process_queue_once()