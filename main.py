import cv2
import threading
import uvicorn
import time
import os
from datetime import datetime

from config import MODEL_PATH
from database.db import init_db, log_alert, SNAPSHOTS_DIR
from model.pose_model import PoseModel
from detection.fall_logic import FallDetector
from alerts.sms_alert import send_sms_alert
from alerts.email_alert import send_email_alert

# Import the FastAPI app instance to share state
from backend.server import app

def run_fastapi_server():
    """Runs the FastAPI server in a separate thread."""
    print("[INFO] Starting FastAPI server on http://localhost:8000...")
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    # Disable signal handler installation to prevent ValueError in thread
    # because signals can only be listened to from the main Python thread.
    server.install_signal_handlers = lambda: None
    
    server.run()

def trigger_alert_sequence(frame, source="System"):
    """Handles the full sequence of logging and sending alerts."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = os.path.join(SNAPSHOTS_DIR, f"fall_alert_{timestamp}.jpg")
    
    # Save the frame to disk
    cv2.imwrite(snapshot_path, frame)
    
    # 1. Log to SQLite Database
    log_alert("FALL DETECTED", snapshot_path)
    print(f"[ALERT] Logged Fall Event at {timestamp}")
    
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sms_text = f"ALERT ({source}): Fall detected at {time_str}. Please check immediately."
    email_subject = f"Critical Alert: Fall Detected - Immediate Attention Required"
    email_body = f"A fall was detected by the {source} System at {time_str}.\n\nPlease review the attached snapshot.\n"
    
    # 2. Trigger SMS
    send_sms_alert(sms_text)
    
    # 3. Trigger Email
    send_email_alert(email_subject, email_body, snapshot_path)

def main():
    # 1. Initialize SQLite Database
    init_db()

    # 2. Start FastAPI server thread
    server_thread = threading.Thread(target=run_fastapi_server, daemon=True)
    server_thread.start()

    # Wait a second for server to initialize
    time.sleep(1)

    # 3. Initialize Models and Components
    pose_model = PoseModel(model_path=MODEL_PATH)
    fall_detector = FallDetector()

    # 4. Start OpenCV Webcam Capture
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        return

    print("[INFO] Starting Fall Detection Loop. Press 'q' to quit.")

    # State tracking to ensure we only trigger the alert sequence once per fall event
    fall_already_handled = False
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Failed to grab frame. Exiting loop.")
            break

        # Check for mock test alert from the frontend
        if getattr(app.state, 'trigger_test_alert', False):
            print("[INFO] Manually triggering test alert sequence...")
            trigger_alert_sequence(frame, "Manual Test")
            app.state.trigger_test_alert = False

        # Run pose inference
        results = pose_model.predict(frame)
        annotated_frame = frame.copy()
        current_status = "NORMAL"
        
        # We process the first detected person (if any)
        if len(results) > 0 and len(results[0].keypoints.data) > 0:
            keypoints = results[0].keypoints.data[0].cpu().numpy()
            
            # Send keypoints to logic
            current_status = fall_detector.process_keypoints(keypoints)
            
            # Annotate frame
            annotated_frame = results[0].plot()

        app.state.current_status = current_status

        if current_status == "FALL DETECTED":
            # Ensure we only send an alert once per fall occurrence
            if not fall_already_handled:
                trigger_alert_sequence(frame, "AI Vision")
                fall_already_handled = True
            
            # Draw red border or text on frame to indicate alert
            cv2.putText(annotated_frame, "FALL DETECTED!", (50, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
        else:
            # Person recovered / cooldown expired / normal
            fall_already_handled = False

        # Convert frame to bytes and update shared state for the video_feed MJPEG stream
        ret_encoding, buffer = cv2.imencode('.jpg', annotated_frame)
        if ret_encoding:
            app.state.latest_frame_bytes = buffer.tobytes()

        # Local display window (optional, can be commented out in production)
        cv2.imshow("Fall Detection Live Feed", annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
