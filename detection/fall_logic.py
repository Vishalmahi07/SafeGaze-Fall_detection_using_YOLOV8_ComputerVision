"""
Improved Fall Detection Logic — v2
===================================
Key improvements over v1:
1. Confidence-gated keypoints — ignores keypoints with conf < 0.3
2. Multi-signal fusion — combines 3 independent signals:
   a) Torso angle from vertical (corrected formula)
   b) Vertical bounding-box aspect ratio (tall vs. wide)
   c) Hip-to-shoulder vertical drop (using y-coords in image space)
3. Smoothing buffer — votes over last N frames to kill jitter
4. Proper status reset — returns NORMAL faster after recovery
5. Falls in any direction (sideways, forward, backward) are detected
"""
import math
import time
import numpy as np
from collections import deque
from config import FALL_ANGLE_THRESHOLD, FALL_TIME_THRESHOLD, COOLDOWN_PERIOD

# ─── YOLOv8-Pose Keypoint Index Map ──────────────────────────────────────────
KP_NOSE          = 0
KP_LEFT_EYE      = 1
KP_RIGHT_EYE     = 2
KP_LEFT_EAR      = 3
KP_RIGHT_EAR     = 4
KP_LEFT_SHOULDER = 5
KP_RIGHT_SHOULDER= 6
KP_LEFT_ELBOW    = 7
KP_RIGHT_ELBOW   = 8
KP_LEFT_WRIST    = 9
KP_RIGHT_WRIST   = 10
KP_LEFT_HIP      = 11
KP_RIGHT_HIP     = 12
KP_LEFT_KNEE     = 13
KP_RIGHT_KNEE    = 14
KP_LEFT_ANKLE    = 15
KP_RIGHT_ANKLE   = 16

# ─── Tuning constants ─────────────────────────────────────────────────────────
KP_CONF_THRESHOLD  = 0.25   # Minimum keypoint confidence to trust
HISTORY_FRAMES     = 6      # Frames to vote over (reduces jitter)
FALL_VOTE_RATIO    = 0.60   # Fraction of history frames that must agree "FALL"
RECOVERY_RATIO     = 0.35   # Fraction must agree "FALL" to stay in FALL state

# Signal weights for fusion (must sum to 1.0)
W_ANGLE   = 0.45   # Torso angle signal
W_ASPECT  = 0.30   # Bounding-box aspect ratio signal
W_DROP    = 0.25   # Hip-shoulder vertical drop signal


def _get_kp(keypoints, idx, conf_thresh=KP_CONF_THRESHOLD):
    """
    Returns (x, y) of keypoint at idx if confidence >= thresh, else None.
    keypoints shape: (17, 3) — [x, y, conf]
    """
    if idx >= len(keypoints):
        return None
    kp = keypoints[idx]
    # Handle both (x, y) and (x, y, conf) shapes
    if len(kp) >= 3 and kp[2] < conf_thresh:
        return None
    x, y = float(kp[0]), float(kp[1])
    # Reject if both x and y are effectively zero (not detected)
    if x < 1.0 and y < 1.0:
        return None
    return (x, y)


def _midpoint(p1, p2):
    if p1 is None or p2 is None:
        return None
    return ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)


def _distance(p1, p2):
    if p1 is None or p2 is None:
        return None
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


# ─── Signal A: Torso angle from vertical ─────────────────────────────────────
def _compute_torso_angle(keypoints):
    """
    Returns angle of the shoulder-hip line from VERTICAL (degrees).
    Standing upright → ~0°
    Lying flat → ~90°
    Threshold typically 45–55°
    
    Image coords: y increases downward.
    Standing: shoulder above hip → hip.y > shoulder.y
    """
    ls = _get_kp(keypoints, KP_LEFT_SHOULDER)
    rs = _get_kp(keypoints, KP_RIGHT_SHOULDER)
    lh = _get_kp(keypoints, KP_LEFT_HIP)
    rh = _get_kp(keypoints, KP_RIGHT_HIP)

    mid_shoulder = _midpoint(ls, rs)
    mid_hip      = _midpoint(lh, rh)

    # Fall back to single-side if one side not detected
    if mid_shoulder is None:
        mid_shoulder = ls or rs
    if mid_hip is None:
        mid_hip = lh or rh

    if mid_shoulder is None or mid_hip is None:
        return None

    dx = mid_hip[0] - mid_shoulder[0]
    dy = mid_hip[1] - mid_shoulder[1]          # positive = hip below shoulder (standing)

    # Angle from vertical: atan2(|dx|, |dy|)
    # Standing: dy large, dx small → angle near 0°
    # Lying: dy small, dx large  → angle near 90°
    angle = math.degrees(math.atan2(abs(dx), abs(dy)))
    return angle   # 0 = upright, 90 = horizontal


# ─── Signal B: Bounding-box aspect ratio ─────────────────────────────────────
def _compute_aspect_ratio(keypoints):
    """
    Computes height/width ratio of the bounding box of visible keypoints.
    Standing → tall box → ratio >> 1
    Fallen   → wide box → ratio << 1
    Returns height/width or None if not enough points.
    """
    xs, ys = [], []
    for i in range(17):
        kp = _get_kp(keypoints, i, conf_thresh=0.15)
        if kp:
            xs.append(kp[0])
            ys.append(kp[1])

    if len(xs) < 4:
        return None

    width  = max(xs) - min(xs)
    height = max(ys) - min(ys)

    if width < 5:   # degenerate
        return None

    return height / (width + 1e-6)   # >1 = tall, <1 = wide


# ─── Signal C: Vertical position drop ────────────────────────────────────────
def _compute_vertical_drop_score(keypoints):
    """
    Checks whether the hip centre is unusually LOW in the frame
    relative to shoulder-to-ankle span.
    In image coords, y increases downward.
    
    When standing: hip y is roughly in the middle.
    When fallen:   hip y is close to where ankles used to be.
    
    Score: 0.0 (upright) → 1.0 (fully fallen)
    """
    ls = _get_kp(keypoints, KP_LEFT_SHOULDER)
    rs = _get_kp(keypoints, KP_RIGHT_SHOULDER)
    lh = _get_kp(keypoints, KP_LEFT_HIP)
    rh = _get_kp(keypoints, KP_RIGHT_HIP)
    la = _get_kp(keypoints, KP_LEFT_ANKLE)
    ra = _get_kp(keypoints, KP_RIGHT_ANKLE)

    mid_shoulder = _midpoint(ls, rs) or ls or rs
    mid_hip      = _midpoint(lh, rh) or lh or rh
    mid_ankle    = _midpoint(la, ra) or la or ra

    if not (mid_shoulder and mid_hip):
        return None

    # If ankles not visible, skip this signal
    if mid_ankle is None:
        return None

    shoulder_y = mid_shoulder[1]
    hip_y      = mid_hip[1]
    ankle_y    = mid_ankle[1]

    body_height = abs(ankle_y - shoulder_y)
    if body_height < 10:
        return None

    # Normalised hip position: 0 = hip at shoulder level, 1 = hip at ankle level
    hip_position = (hip_y - shoulder_y) / body_height
    # When standing, hip is ~0.5 (midway). When lying flat, it drops to ~0.8-1.0
    # Map: 0.5 → 0.0 (normal), 1.0 → 1.0 (fallen)
    score = max(0.0, (hip_position - 0.5) / 0.5)
    return min(1.0, score)


# ─── Fusion ───────────────────────────────────────────────────────────
def _compute_fall_score(keypoints, angle_threshold=None):
    """
    Fuses 3 signals into one [0, 1] fall probability score.
    Decision rule:
      1. Weighted average score >= 0.42  → FALL
      2. OR: majority of binary votes say FALL (>= 2 out of 3)  → FALL
      3. OR: aspect ratio is extreme (< 0.45) alone  → FALL (person clearly horizontal)
    Returns (score, debug_dict).
    """
    if angle_threshold is None:
        angle_threshold = FALL_ANGLE_THRESHOLD

    # Signal A: torso angle
    angle = _compute_torso_angle(keypoints)
    if angle is not None:
        a_score  = min(1.0, angle / 90.0)
        a_binary = 1.0 if angle >= angle_threshold else 0.0
    else:
        a_score, a_binary = None, None

    # Signal B: bounding-box aspect ratio
    aspect = _compute_aspect_ratio(keypoints)
    if aspect is not None:
        # aspect < 0.40 → very horizontal (score=1.0), >1.5 → very tall (score=0.0)
        b_score  = max(0.0, 1.0 - min(1.5, aspect) / 1.5)
        b_binary = 1.0 if aspect < 0.70 else 0.0
    else:
        b_score, b_binary = None, None

    # Signal C: vertical drop
    c_score  = _compute_vertical_drop_score(keypoints)
    c_binary = None
    if c_score is not None:
        c_binary = 1.0 if c_score > 0.50 else 0.0

    # — Weighted average (skip unavailable signals) —
    signals  = [(a_score, W_ANGLE), (b_score, W_ASPECT), (c_score, W_DROP)]
    binaries = [b for b in [a_binary, b_binary, c_binary] if b is not None]

    valid_signals = [(s, w) for s, w in signals if s is not None]
    if not valid_signals:
        return 0.0, {}

    total_w = sum(w for _, w in valid_signals)
    fused   = sum(s * w for s, w in valid_signals) / total_w

    # — Override rules —
    # Rule 1: majority binary vote (>= 2 of 3 available signals say FALL)
    if len(binaries) >= 2 and sum(binaries) >= 2:
        fused = max(fused, 0.55)   # force above threshold

    # Rule 2: extreme aspect ratio alone (<<0.45 = clearly lying flat)
    if aspect is not None and aspect < 0.45:
        fused = max(fused, 0.60)

    # Rule 3: extreme torso angle alone
    if angle is not None and angle >= 70:
        fused = max(fused, 0.55)

    debug = {
        "torso_angle_deg": round(angle, 1) if angle is not None else None,
        "aspect_ratio":    round(aspect, 2) if aspect is not None else None,
        "drop_score":      round(c_score, 2) if c_score is not None else None,
        "fused_score":     round(fused, 3),
        "binary_votes":    [b for b in binaries if b is not None],
    }
    return fused, debug


# ─── FallDetector class ───────────────────────────────────────────────────────
class FallDetector:
    def __init__(self):
        self.fall_start_time  = None
        self.last_alert_time  = 0
        self.current_status   = "NORMAL"
        # Smoothing: ring buffer of per-frame binary fall signals (0 or 1)
        self._history         = deque(maxlen=HISTORY_FRAMES)
        self._last_debug      = {}

    # ── Public ────────────────────────────────────────────────────────────────
    def process_keypoints(self, keypoints):
        """
        Main entry point. Analyzes keypoints and returns "NORMAL" | "FALL DETECTED".
        """
        try:
            score, debug = _compute_fall_score(keypoints)
            self._last_debug = debug

            # Binary fall signal for this frame
            frame_fall = 1 if score >= 0.48 else 0
            self._history.append(frame_fall)

            # Vote: what fraction of history frames say FALL?
            if len(self._history) == 0:
                return self.current_status

            fall_votes = sum(self._history)
            vote_ratio = fall_votes / len(self._history)

            if self.current_status == "NORMAL":
                # Transition to FALL: need FALL_VOTE_RATIO agreement + sustained time
                if vote_ratio >= FALL_VOTE_RATIO:
                    if self.fall_start_time is None:
                        self.fall_start_time = time.time()
                    elif (time.time() - self.fall_start_time) >= FALL_TIME_THRESHOLD:
                        self._trigger_fall_detected()
                else:
                    self.fall_start_time = None

            else:  # currently FALL DETECTED
                # Recover to NORMAL: votes drop below RECOVERY_RATIO
                if vote_ratio < RECOVERY_RATIO:
                    self.fall_start_time = None
                    self.current_status  = "NORMAL"
                    print("[FallDetector] ✅ Person recovered — status reset to NORMAL")
                # If cooldown expired AND still in FALL state → keep as FALL
                # (the alert was already sent; next alert will fire after cooldown)

        except Exception as e:
            print(f"[FallDetector] Warning: {e}")

        return self.current_status

    # ── Private ───────────────────────────────────────────────────────────────
    def _trigger_fall_detected(self):
        current_time = time.time()
        self.current_status = "FALL DETECTED"
        if current_time - self.last_alert_time > COOLDOWN_PERIOD:
            self.last_alert_time = current_time
            # Printed for debugging; the actual alert is handled by main.py
            print(f"[FallDetector] 🚨 FALL DETECTED — "
                  f"angle={self._last_debug.get('torso_angle_deg')}°  "
                  f"aspect={self._last_debug.get('aspect_ratio')}  "
                  f"drop={self._last_debug.get('drop_score')}  "
                  f"fused={self._last_debug.get('fused_score')}")

    @property
    def debug_info(self):
        """Returns last frame's debug metrics for overlay display."""
        return self._last_debug
