from ultralytics import YOLO

class PoseModel:
    def __init__(self, model_path="yolov8n-pose.pt"):
        """Initializes the YOLOv8 Pose model."""
        try:
            print(f"> Loading YOLOv8 pose model from: {model_path}")
            self.model = YOLO(model_path)
            print("> Model loaded successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to load pose model: {e}")
            raise e

    def predict(self, frame):
        """
        Runs inference on a single frame.
        
        conf=0.35 — Lowered from 0.5 so the model still detects people who are
        partially out-of-frame, lying down, or at unusual angles.
        iou=0.45  — Slightly relaxed NMS so overlapping detections are not pruned.
        """
        results = self.model(
            frame,
            conf=0.35,      # was 0.5 — more sensitive person detection
            iou=0.45,       # NMS IoU threshold
            verbose=False,
        )
        return results
