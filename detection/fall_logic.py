import math
import numpy as np
import time
from config import FALL_ANGLE_THRESHOLD, FALL_TIME_THRESHOLD, COOLDOWN_PERIOD

class FallDetector:
    def __init__(self):
        self.fall_start_time = None
        self.last_alert_time = 0
        self.current_status = "NORMAL"

    def process_keypoints(self, keypoints):
        """
        Analyzes YOLO pose keypoints for a single person.
        Args:
            keypoints: The keypoints tensor from yolov8 results.
        Returns:
            str: "NORMAL" or "FALL DETECTED"
        """
        
        # YOLOv8 keypoint indices:
        # 5: left_shoulder, 6: right_shoulder
        # 11: left_hip, 12: right_hip
        
        # We need at least 13 keypoints to check against index 11 and 12
        if len(keypoints) < 13:
            return self.current_status

        try:
            # Extract coordinates for shoulders and hips
            left_shoulder = keypoints[5][:2]
            right_shoulder = keypoints[6][:2]
            left_hip = keypoints[11][:2]
            right_hip = keypoints[12][:2]

            # Calculate midpoints
            mid_shoulder = ((left_shoulder[0] + right_shoulder[0]) / 2, 
                            (left_shoulder[1] + right_shoulder[1]) / 2)
            mid_hip = ((left_hip[0] + right_hip[0]) / 2, 
                       (left_hip[1] + right_hip[1]) / 2)

            # Check if any part is 0 (meaning keypoint wasn't detected properly)
            # A very simplistic check, robust logic would look at confidence scores.
            if mid_shoulder == (0, 0) or mid_hip == (0, 0):
                return self.current_status

            # Calculate angle of the torso line relative to the vertical axis (y-axis)
            # Use arctan2. dx = x2 - x1, dy = y2 - y1
            dx = mid_hip[0] - mid_shoulder[0]
            dy = mid_hip[1] - mid_shoulder[1]
            
            # The angle compared to horizontal
            angle_rad = math.atan2(dy, dx)
            angle_deg = abs(math.degrees(angle_rad))

            # The angle from the vertical. 
            # If body is perfectly vertical, dy is large, dx is 0, angle_deg = 90.
            # Torso angle from vertical = |90 - angle_deg|
            # Note: Depending on image coordinate system (y goes down), 
            # standing straight: mid_shoulder is above mid_hip.
            # dy > 0, angle is around 90.
            torso_angle_vertical = abs(90 - angle_deg)
            
            # If torso angle > FALL_ANGLE_THRESHOLD, person is leaning heavily or falling
            if torso_angle_vertical > FALL_ANGLE_THRESHOLD:
                if self.fall_start_time is None:
                    # Start the fall timer
                    self.fall_start_time = time.time()
                else:
                    elapsed_time = time.time() - self.fall_start_time
                    if elapsed_time > FALL_TIME_THRESHOLD:
                        # Fall duration exceeded threshold -> DETECTED
                        self._trigger_fall_detected()
            else:
                # Person returned upright
                self.fall_start_time = None
                self.current_status = "NORMAL"
                
        except Exception as e:
            # Silently pass errors associated with tensor indexing on missing keypoints
            pass

        return self.current_status

    def _trigger_fall_detected(self):
        """Helper to handle state change and cooldown."""
        current_time = time.time()
        
        # Check cooldown to prevent alert spam
        if current_time - self.last_alert_time > COOLDOWN_PERIOD:
            self.current_status = "FALL DETECTED"
            self.last_alert_time = current_time
        else:
            # We are in cooldown, status remains FALL DETECTED or becomes one quietly
            self.current_status = "FALL DETECTED"
