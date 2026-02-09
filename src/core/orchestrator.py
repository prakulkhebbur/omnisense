import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from src.models.call import Call, CallStatus, EmergencyType, SeverityLevel
from src.models.operator import Operator, OperatorStatus
from src.agents.call_agent import AICallAgent
from src.ranking.priority_ranker import PriorityRanker

class CallOrchestrator:
    def __init__(self):
        # 1. Initialize State correctly
        self.active_calls: Dict[str, Call] = {}
        self.call_queue: List[str] = []
        self.operators: Dict[str, dict] = {} 
        
        self.ai_agent = AICallAgent()
        self.ranker = PriorityRanker()
        
        self.is_running = False
        self._queue_task = None
        self.broadcast_func = None

    def set_broadcast_function(self, broadcast_func):
        self.broadcast_func = broadcast_func

    async def _broadcast_update(self):
        # --- FIX 1: DASHBOARD (Convert Queue IDs to Objects) ---
        queue_objects = []
        for cid in self.call_queue:
            if cid in self.active_calls:
                queue_objects.append(self.active_calls[cid].dict())

        # Send to Dashboard
        state = {
            "active_calls": [c.dict() for c in self.active_calls.values()],
            "queue": queue_objects, # <--- Fix: Sends Objects, not Strings
            "operators": {op_id: op['current_call'] for op_id, op in self.operators.items()},
            "stats": {"total_active": len(self.active_calls), "queued": len(self.call_queue)}
        }
        if self.broadcast_func:
            await self.broadcast_func(state)

        # --- FIX 2: OPERATOR (Send Waiting List) ---
        ai_calls = []
        for cid in self.call_queue:
            call = self.active_calls.get(cid)
            if call:
                # --- SAFETY CHECK: Handle Caller as Object or Dict ---
                # This prevents "AttributeError: 'dict' object has no attribute 'phone_number'"
                phone = "Unknown"
                try:
                    if isinstance(call.caller, dict):
                        phone = call.caller.get("phone_number", "Unknown")
                    else:
                        phone = call.caller.phone_number
                except:
                    phone = "Unknown"
                # -----------------------------------------------------

                ai_calls.append({
                    "id": call.id,
                    "phone": phone,
                    "severity": f"{call.severity_level.value} ({call.severity_score})",
                    "summary": call.summary
                })
        
        op_msg = {"type": "queue_update", "calls": ai_calls}
        
        # Broadcast to all connected operators
        for op in self.operators.values():
            if op.get('ws'):
                try:
                    await op['ws'].send_json(op_msg)
                except: pass

    async def start(self):
        self.is_running = True
        self._queue_task = asyncio.create_task(self._process_queue_loop())
        print("🚀 Orchestrator Started")

    async def stop(self):
        self.is_running = False
        if self._queue_task:
            self._queue_task.cancel()

    # --- CALL HANDLING ---
    async def create_incoming_call(self, caller_phone: str) -> Call:
        call = Call(caller={"phone_number": caller_phone})
        self.active_calls[call.id] = call
        print(f"📞 New Call: {call.id}")

        assigned_op_id = await self._find_available_operator(call)
        
        if assigned_op_id:
            await self._assign_call(call.id, assigned_op_id)
        else:
            print(f"🤖 Assigning {call.id} to AI Agent.")
            call.assigned_to = "AI_AGENT"
            call.status = CallStatus.IN_PROGRESS
            self.call_queue.append(call.id)
            
        await self._broadcast_update()
        return call

    async def handle_caller_message(self, call_id: str, text: str) -> Optional[str]:
        call = self.active_calls.get(call_id)
        if not call: return None

        ai_response = await self.ai_agent.handle_caller_message(call, text)
        
        old_score = call.severity_score
        new_score = self.ranker.calculate_score(call)
        call.severity_score = new_score
        
        if new_score > old_score + 10:
            self._sort_queue()

        await self._broadcast_update()

        if call.assigned_to == "AI_AGENT":
            return ai_response
        return None

    # --- OPERATORS ---
    async def register_operator(self, operator_id: str, websocket):
        op = Operator(id=operator_id, name=f"Officer {operator_id}", status=OperatorStatus.AVAILABLE)
        self.operators[operator_id] = {'model': op, 'ws': websocket, 'current_call': None}
        print(f"👨‍💼 Operator {operator_id} joined.")
        await self._process_queue_once()
        await self._broadcast_update()

    async def unregister_operator(self, operator_id: str):
        if operator_id in self.operators:
            current_call_id = self.operators[operator_id]['current_call']
            if current_call_id:
                call = self.active_calls.get(current_call_id)
                if call:
                    call.assigned_to = "AI_AGENT"
                    self.call_queue.insert(0, call.id)
            
            del self.operators[operator_id]
            print(f"👨‍💼 Operator {operator_id} left.")
            await self._broadcast_update()

    # --- AUDIO ROUTING ---
    async def route_audio_victim_to_operator(self, call_id: str, audio_bytes: bytes):
        call = self.active_calls.get(call_id)
        if not call or not call.assigned_to or call.assigned_to == "AI_AGENT": return

        op_data = self.operators.get(call.assigned_to)
        if op_data and op_data.get('ws'):
            try:
                await op_data['ws'].send_bytes(audio_bytes)
            except: pass

    async def route_audio_operator_to_victim(self, operator_id: str, audio_bytes: bytes, manager):
        op_data = self.operators.get(operator_id)
        if not op_data or not op_data['current_call']: return
        
        call_id = op_data['current_call']
        if manager:
            await manager.send_audio_to_victim(call_id, audio_bytes)

    # --- QUEUE LOGIC ---
    async def _process_queue_loop(self):
        while self.is_running:
            await self._process_queue_once()
            await asyncio.sleep(2)

    async def _process_queue_once(self):
        if not self.call_queue: return
        self._sort_queue()
        
        for call_id in list(self.call_queue):
            call = self.active_calls.get(call_id)
            if not call: 
                self.call_queue.remove(call_id)
                continue

            op_id = await self._find_available_operator(call)
            if op_id:
                await self._assign_call(call.id, op_id)
                self.call_queue.remove(call_id)
            else:
                break
        await self._broadcast_update()

    async def _find_available_operator(self, call: Call) -> Optional[str]:
        for op_id, data in self.operators.items():
            if data['model'].status == OperatorStatus.AVAILABLE:
                return op_id
        return None

    async def _assign_call(self, call_id: str, operator_id: str):
        op_data = self.operators.get(operator_id)
        call = self.active_calls.get(call_id)
        if not op_data or not call: return

        call.assigned_to = operator_id
        call.status = CallStatus.IN_PROGRESS
        
        op_data['current_call'] = call_id
        op_data['model'].status = OperatorStatus.BUSY

        # --- SAFETY CHECK: Same fix for assignment message ---
        phone = "Unknown"
        try:
            if isinstance(call.caller, dict):
                phone = call.caller.get("phone_number", "Unknown")
            else:
                phone = call.caller.phone_number
        except: pass
        # -----------------------------------------------------

        msg = {
            "type": "new_assignment",
            "caller_id": phone,
            "location": call.location.address if call.location else "Unknown",
            "severity": f"{call.severity_level.value} ({call.severity_score})",
            "summary": call.summary
        }
        await op_data['ws'].send_json(msg)
        print(f"🔗 Assigned {call_id} -> {operator_id}")
        await self._broadcast_update()

    def _sort_queue(self):
        self.call_queue.sort(
            key=lambda cid: self.active_calls[cid].severity_score if cid in self.active_calls else 0, 
            reverse=True
        )

    # --- ACTIONS ---
    async def force_assign_operator(self, call_id: str, operator_id: str):
        op_data = self.operators.get(operator_id)
        if not op_data: return False

        current_call_id = op_data['current_call']
        if current_call_id:
            old_call = self.active_calls.get(current_call_id)
            if old_call:
                old_call.assigned_to = "AI_AGENT"
                self.call_queue.insert(0, current_call_id)
        
        if call_id in self.call_queue:
            self.call_queue.remove(call_id)
            
        await self._assign_call(call_id, operator_id)
        return True

    async def complete_call(self, operator_id: str):
        op_data = self.operators.get(operator_id)
        if not op_data or not op_data['current_call']: return

        call_id = op_data['current_call']
        call = self.active_calls.get(call_id)
        
        if call:
            call.status = CallStatus.COMPLETED
            call.completed_at = datetime.now()

        op_data['current_call'] = None
        op_data['model'].status = OperatorStatus.AVAILABLE
        
        await op_data['ws'].send_json({"type": "call_ended"})
        await self._process_queue_once()
        await self._broadcast_update()