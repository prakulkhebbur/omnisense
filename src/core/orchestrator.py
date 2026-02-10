import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from src.models.call import Call, CallStatus, EmergencyType, SeverityLevel
from src.models.operator import Operator, OperatorStatus
from src.agents.call_agent import AICallAgent
from src.ranking.priority_ranker import PriorityRanker
from src.services.pattern_detector import PatternDetector

class CallOrchestrator:
    def __init__(self):
        # 1. Initialize State correctly
        self.active_calls: Dict[str, Call] = {}
        self.call_queue: List[str] = []
        self.operators: Dict[str, dict] = {} 
        # Keep a short history of completed/archived calls for analysis
        self.call_history: List[Call] = []
        
        self.ai_agent = AICallAgent()
        self.ranker = PriorityRanker()
        self.pattern_detector = PatternDetector()
        
        self.is_running = False
        self._queue_task = None
        self.broadcast_func = None
        self.manager = None  # ConnectionManager for audio/victim events

    def set_broadcast_function(self, broadcast_func):
        self.broadcast_func = broadcast_func

    def set_manager(self, manager):
        """Store ConnectionManager to send events to victims."""
        self.manager = manager

    async def _broadcast_update(self):
        try:
            # Active calls: those currently IN_PROGRESS
            # Also include calls that are COMPLETED but not yet archived (awaiting user End Case)
            active_calls = [c.model_dump(mode='json') for c in self.active_calls.values()
                            if c.status == CallStatus.IN_PROGRESS or (c.status == CallStatus.COMPLETED and not getattr(c, 'archived', False))]

            # Completed (archived) calls: shown greyed out
            completed_calls = [c.model_dump(mode='json') for c in self.active_calls.values()
                               if c.status == CallStatus.COMPLETED and getattr(c, 'archived', False)]

            # Pending (queued) calls: reflect queue order
            pending_calls = []
            for cid in self.call_queue:
                call = self.active_calls.get(cid)
                if call:
                    pending_calls.append(call.model_dump(mode='json'))

            operators_state = {}
            for op_id, op in self.operators.items():
                model = op.get('model')
                operators_state[op_id] = {
                    'status': model.status.value if model else 'UNKNOWN',
                    'current_call': op.get('current_call')
                }

            state = {
                "active_calls": active_calls,
                "completed_calls": completed_calls,
                "pending_calls": pending_calls,
                "operators": operators_state,
                "stats": {
                    "total_active": len(active_calls),
                    "completed": len(completed_calls),
                    "queued": len(pending_calls)
                }
            }
            # Run cross-call pattern detection and attach alerts
            try:
                # Merge active calls and recent history (dedupe by id)
                combined = {c.id: c for c in list(self.active_calls.values())}
                for c in getattr(self, 'call_history', []) or []:
                    if c.id not in combined:
                        combined[c.id] = c

                patterns = self.pattern_detector.detect_patterns(list(combined.values()))
                state["patterns"] = patterns
            except Exception as e:
                print(f"Pattern detection failed: {e}")
            
            if self.broadcast_func:
                await self.broadcast_func(state)
        except Exception as e:
            print(f"❌ Broadcast Failed: {e}")

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
        if not self.call_queue:
            await self._broadcast_update()
            return
        self._sort_queue()

        filtered_queue = []
        for call_id in self.call_queue:
            call = self.active_calls.get(call_id)
            if not call:
                continue
            if call.assigned_to != "AI_AGENT":
                continue
            filtered_queue.append(call_id)

        self.call_queue = filtered_queue
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

        # Remove from queue immediately so dashboard/operator lists update
        if call_id in self.call_queue:
            try:
                self.call_queue.remove(call_id)
            except ValueError:
                pass

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
        # Announce transfer to the victim: operator has taken over, AI remains as background layer
        if self.manager:
            try:
                await self.manager.send_event_to_victim(call.id, {
                    "type": "transferred_to_operator",
                    "operator_id": operator_id,
                    "message": "This call has been transferred to a human operator. AI will remain in the background layer."
                })
            except: pass
        print(f"🔗 Assigned {call_id} -> {operator_id}")
        await self._broadcast_update()

    def _sort_queue(self):
        self.call_queue = [cid for cid in self.call_queue if cid in self.active_calls]
        self.call_queue.sort(
            key=lambda cid: self.active_calls[cid].severity_score,
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

    async def complete_call(self, operator_id: str, manager=None):
        op_data = self.operators.get(operator_id)
        if not op_data or not op_data['current_call']: return

        call_id = op_data['current_call']
        call = self.active_calls.get(call_id)
        
        if call:
            call.status = CallStatus.COMPLETED
            call.completed_at = datetime.now()
            # Add to history for cross-call pattern detection and analysis
            try:
                if not any(c.id == call.id for c in self.call_history):
                    self.call_history.append(call)
                    # keep history reasonably bounded
                    if len(self.call_history) > 500:
                        self.call_history.pop(0)
            except Exception:
                pass
            # Ensure completed calls are not left in the queue
            if call_id in self.call_queue:
                try:
                    self.call_queue.remove(call_id)
                except ValueError:
                    pass

        op_data['current_call'] = None
        op_data['model'].status = OperatorStatus.AVAILABLE
        
        await op_data['ws'].send_json({"type": "call_ended"})
        if manager:
            await manager.send_event_to_victim(call_id, {"type": "call_ended"})
            await manager.close_victim(call_id)
        # Process queue and broadcast so dashboards and operators see updated lists
        await self._process_queue_once()
        await self._broadcast_update()

    async def operator_completes_call(self, operator_id: str, manager=None) -> Optional[str]:
        """Compatibility wrapper used by external routes/APIs.
        Completes the operator's current call, then attempts to assign
        the next queued AI-handled call to the now-available operator.
        Returns the newly assigned call id or None.
        """
        # Finish the current call first
        await self.complete_call(operator_id, manager=manager)

        # If operator no longer exists or is not available, return
        op_data = self.operators.get(operator_id)
        if not op_data or op_data['model'].status != OperatorStatus.AVAILABLE:
            await self._broadcast_update()
            return None

        # Find the highest priority call in the queue still assigned to AI_AGENT
        next_call_id = None
        for cid in list(self.call_queue):
            call = self.active_calls.get(cid)
            if not call:
                continue
            if call.assigned_to == "AI_AGENT":
                next_call_id = cid
                break

        if next_call_id:
            # remove from queue and assign to this operator
            try:
                self.call_queue.remove(next_call_id)
            except ValueError:
                pass
            await self._assign_call(next_call_id, operator_id)
            return next_call_id

        await self._broadcast_update()
        return None

    async def handle_caller_disconnect(self, call_id: str):
        call = self.active_calls.get(call_id)
        if call:
            call.status = CallStatus.COMPLETED
            call.completed_at = datetime.now()
            # Remove from queue if present
            if call_id in self.call_queue:
                try:
                    self.call_queue.remove(call_id)
                except ValueError:
                    pass
            # Preserve in history
            try:
                if not any(c.id == call.id for c in self.call_history):
                    self.call_history.append(call)
                    if len(self.call_history) > 500:
                        self.call_history.pop(0)
            except Exception:
                pass

        assigned_op_id = call.assigned_to if call else None
        if assigned_op_id and assigned_op_id != "AI_AGENT":
            op_data = self.operators.get(assigned_op_id)
            if op_data and op_data.get('current_call') == call_id:
                op_data['current_call'] = None
                op_data['model'].status = OperatorStatus.AVAILABLE
                if op_data.get('ws'):
                    try:
                        await op_data['ws'].send_json({"type": "call_ended"})
                    except:
                        pass

        await self._process_queue_once()
        await self._broadcast_update()
