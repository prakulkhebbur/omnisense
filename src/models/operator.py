from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class OperatorStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"
    ON_BREAK = "ON_BREAK"

class Operator(BaseModel):
    id: str
    name: str
    status: OperatorStatus = OperatorStatus.OFFLINE
    current_call_id: Optional[str] = None
    shift_start: datetime = Field(default_factory=datetime.now)
    total_calls_taken: int = 0