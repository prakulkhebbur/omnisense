# src/services/pattern_detector.py
from typing import List, Dict, Tuple
from collections import defaultdict
from src.models.call import Call
from src.models.enums import EmergencyType
import re

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

        # Known location keywords to look for (extendable)
        known_places = ["newtown", "park street", "sector 5", "downtown", "main street", "central"]

        for call in active_calls:
            # collect candidate text sources
            candidates = []
            try:
                if call.location and getattr(call.location, 'address', None):
                    candidates.append(call.location.address)
            except: pass

            try:
                if getattr(call, 'extracted_info', None) and getattr(call.extracted_info, 'location', None):
                    loc = call.extracted_info.location
                    if getattr(loc, 'address', None):
                        candidates.append(loc.address)
            except: pass

            try:
                if getattr(call, 'summary', None):
                    candidates.append(call.summary)
            except: pass

            try:
                for t in getattr(call, 'transcript', []) or []:
                    if getattr(t, 'text', None):
                        candidates.append(t.text)
            except: pass

            text_blob = " ".join([c for c in candidates if c])
            if not text_blob:
                continue

            text_lower = text_blob.lower()

            # find a place token from known list or any 'sector \d+' pattern
            place_token = None
            for p in known_places:
                if p in text_lower:
                    place_token = p.title()
                    break

            if not place_token:
                m = re.search(r"sector\s*\d+", text_lower)
                if m:
                    place_token = m.group(0).title()

            # emergency type preference: use extracted_info if present, else call.emergency_type
            etype = None
            try:
                if getattr(call, 'extracted_info', None) and getattr(call.extracted_info, 'emergency_type', None):
                    etype = call.extracted_info.emergency_type
            except: pass
            if not etype:
                etype = getattr(call, 'emergency_type', None)

            key = (etype, place_token if place_token else "Unknown")
            clusters[key].append(call.id)

        # Analyze clusters
        # produce alerts for clusters reaching threshold and warnings for near-threshold
        for (etype, loc_name), call_ids in clusters.items():
            count = len(call_ids)
            et_text = (etype.value if etype and hasattr(etype, 'value') else str(etype))
            if count >= self.threshold:
                alert_msg = f"🚨 MASS EVENT DETECTED: {count} calls reporting {et_text} in {loc_name}"
                alerts.append(alert_msg)
            elif count >= max(2, int(self.threshold/2)):
                warn_msg = f"⚠️ Potential cluster: {count} calls mentioning {et_text} near {loc_name}"
                alerts.append(warn_msg)

        # Debug: print clusters and alerts (helpful during local testing)
        try:
            if alerts:
                print(f"[PatternDetector] clusters: { {k: len(v) for k, v in clusters.items()} }")
                print(f"[PatternDetector] alerts: {alerts}")
            else:
                print("[PatternDetector] No strong patterns detected.")
        except:
            pass
                
        return alerts