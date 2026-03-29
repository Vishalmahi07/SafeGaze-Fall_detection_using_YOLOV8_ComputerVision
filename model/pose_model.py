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
        """Runs inference on a single frame."""
        # conf=0.5 can be tweaked, using low-medium confidence to ensure detection
        results = self.model(frame, conf=0.5, verbose=False)
        return results
