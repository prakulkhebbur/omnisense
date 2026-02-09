# src/services/pattern_detector.py
from typing import List, Dict, Tuple
from collections import defaultdict
from src.models.call import Call
from src.models.enums import EmergencyType

class PatternDetector:
    """
    Analyzes active and queued calls to detect widespread emergencies
    (e.g., Gas Leaks, Mass Fires, Riots)
    """
    
    def __init__(self, time_window_seconds=300, threshold=3):
        self.time_window = time_window_seconds
        self.threshold = threshold  # Min calls to trigger an alert

    def detect_patterns(self, active_calls: List[Call]) -> List[str]:
        """
        Scans calls for location + emergency type clusters.
        Returns a list of alert strings.
        """
        # Group patterns: (EmergencyType, Location_Keyword)
        clusters = defaultdict(list)
        alerts = []

        for call in active_calls:
            if not call.location or not call.location.address:
                continue
                
            # Simple keyword extraction for location grouping
            # In production, use geospatial clustering (Lat/Lon)
            loc_lower = call.location.address.lower()
            
            # Group by emergency type and roughly by location phrase
            key = None
            if "newtown" in loc_lower: key = (call.emergency_type, "Newtown")
            elif "park street" in loc_lower: key = (call.emergency_type, "Park Street")
            elif "sector 5" in loc_lower: key = (call.emergency_type, "Sector 5")
            
            if key:
                clusters[key].append(call.id)

        # Analyze clusters
        for (etype, loc_name), call_ids in clusters.items():
            if len(call_ids) >= self.threshold:
                alert_msg = f"🚨 MASS EVENT DETECTED: {len(call_ids)} calls reporting {etype.value} in {loc_name}"
                alerts.append(alert_msg)
                
        return alerts