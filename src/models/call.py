from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid

from .enums import CallStatus, EmergencyType, SeverityLevel

class Location(BaseModel):
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    landmark: Optional[str] = None

class CallerInfo(BaseModel):
    name: Optional[str] = None
    phone_number: str
    is_victim: bool = True
    relationship: Optional[str] = None

class VictimInfo(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    conscious: Optional[bool] = None
    breathing: Optional[bool] = None
    # --- FIX 1: Use default_factory for lists ---
    medical_conditions: List[str] = Field(default_factory=list)

class TranscriptMessage(BaseModel):
    timestamp: datetime
    role: str  # "caller", "ai", "operator"
    text: str

class ExtractedInfo(BaseModel):
    emergency_type: Optional[EmergencyType] = None
    location: Optional[Location] = None
    victim_info: Optional[VictimInfo] = None
    # --- FIX 2: Use default_factory for lists ---
    severity_indicators: List[str] = Field(default_factory=list)
    additional_details: Dict[str, Any] = Field(default_factory=dict)

class Call(BaseModel):
    # Core
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    call_number: Optional[int] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    answered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Caller info
    caller: CallerInfo
    
    # Emergency details
    emergency_type: EmergencyType = EmergencyType.UNKNOWN
    location: Optional[Location] = None
    victim_info: Optional[VictimInfo] = None
    
    # Summary Field
    summary: str = "Processing..."

    # Status
    status: CallStatus = CallStatus.INCOMING
    assigned_to: Optional[str] = None
    
    # Priority
    severity_score: int = 0
    severity_level: SeverityLevel = SeverityLevel.MEDIUM
    priority_rank: int = 999
    
    # --- FIX 3: CRITICAL - Use default_factory for the transcript ---
    # This ensures every call gets its own unique list!
    transcript: List[TranscriptMessage] = Field(default_factory=list)
    extracted_info: Optional[ExtractedInfo] = None
    
    # Resources
    nearest_hospital: Optional[str] = None
    nearest_hospital_distance_km: Optional[float] = None
    # Whether the call has been archived/closed from the dashboard
    archived: bool = False
    
    # Pattern detection
    related_calls: List[str] = Field(default_factory=list)
    pattern_flags: List[str] = Field(default_factory=list)
    
    # Operator notes
    operator_notes: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_transcript_message(self, role: str, text: str):
        """Add message to transcript"""
        self.transcript.append(
            TranscriptMessage(
                timestamp=datetime.now(),
                role=role,
                text=text
            )
        )
        self.updated_at = datetime.now()
    
    def get_severity_color(self) -> str:
        """Get color for dashboard"""
        colors = {
            SeverityLevel.CRITICAL: "#FF0000",
            SeverityLevel.HIGH: "#FF6600",
            SeverityLevel.MEDIUM: "#FFCC00",
            SeverityLevel.LOW: "#00CC00"
        }
        return colors.get(self.severity_level, "#CCCCCC")