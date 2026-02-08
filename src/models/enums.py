from enum import Enum

class CallStatus(str, Enum):
    INCOMING = "incoming"
    AI_HANDLING = "ai_handling"
    OPERATOR_HANDLING = "operator_handling"
    QUEUED = "queued"
    COMPLETED = "completed"
    DROPPED = "dropped"

class EmergencyType(str, Enum):
    CARDIAC_ARREST = "cardiac_arrest"
    STROKE = "stroke"
    SEVERE_TRAUMA = "severe_trauma"
    FIRE = "fire"
    MEDICAL_EMERGENCY = "medical_emergency"
    ACCIDENT = "accident"
    MINOR_INJURY = "minor_injury"
    NON_EMERGENCY = "non_emergency"
    UNKNOWN = "unknown"

class SeverityLevel(str, Enum):
    CRITICAL = "critical"  # Red
    HIGH = "high"         # Orange
    MEDIUM = "medium"     # Yellow
    LOW = "low"          # Green