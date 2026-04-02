"""
Smart Parking System — Python + OpenCV (WiFi version)
------------------------------------------------------
Requirements:
    pip install opencv-python numpy requests

Mobile camera setup:
    Install "IP Webcam" app on Android.
    Start server → note the IP (e.g. 192.168.1.5:8080).
    Set CAMERA_URL below.

Arduino setup:
    Upload the WiFi sketch (smart_parking_arduino_wifi.ino).
    Note the IP address printed on the LCD / Serial Monitor.
    Set ARDUINO_IP below.

Usage:
    1. Update CAMERA_URL and ARDUINO_IP.
    2. Run once with CALIBRATE_MODE = True to find ROI coordinates.
    3. Fill in PARKING_SLOTS with your measured coordinates.
    4. Set CALIBRATE_MODE = False for normal operation.
    5. Press 'q' to quit.
"""

import cv2
import numpy as np
import requests
import time
import sys
import threading

# ─── Configuration ────────────────────────────────────────────────────────────

CAMERA_URL     = "http://192.168.1.5:8080/video"   # IP Webcam stream URL
ARDUINO_IP     = "http://192.168.1.42"              # Arduino's IP (from LCD / Serial Monitor)
CALIBRATE_MODE = False

# ─── Parking Slot Definitions ─────────────────────────────────────────────────
# ROI format: (x1, y1, x2, y2)  — top-left corner to bottom-right corner
# Run with CALIBRATE_MODE = True to find these values visually.

PARKING_SLOTS = {
    1: {"floor": 1, "block": 1, "slot": 1, "roi": (30,  40,  180, 150)},
    2: {"floor": 1, "block": 1, "slot": 2, "roi": (200, 40,  350, 150)},
    3: {"floor": 1, "block": 1, "slot": 3, "roi": (370, 40,  520, 150)},
    4: {"floor": 1, "block": 2, "slot": 4, "roi": (30,  170, 180, 280)},
    5: {"floor": 1, "block": 2, "slot": 5, "roi": (200, 170, 350, 280)},
    6: {"floor": 1, "block": 2, "slot": 6, "roi": (370, 170, 520, 280)},
}

# ─── Detection Parameters ─────────────────────────────────────────────────────
PIXEL_THRESHOLD  = 60    # Grayscale value — above this = foreground pixel
OCCUPIED_RATIO   = 0.25  # Fraction of bright pixels that means "car present"
SEND_INTERVAL_S  = 5.0   # Re-send even if message hasn't changed (keep-alive)

# ─── WiFi Send (non-blocking, runs in background thread) ──────────────────────

_last_message  = ""
_last_sent_at  = 0.0
_send_lock     = threading.Lock()

def send_to_arduino(message: str):
    """Send slot info to Arduino over WiFi via HTTP GET. Non-blocking."""
    def _send():
        try:
            url = f"{ARDUINO_IP}/?msg={message}"
            response = requests.get(url, timeout=2)
            print(f"[WiFi] Sent: {message}  →  status {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"[WiFi] ERROR: Cannot reach Arduino at {ARDUINO_IP}. Check IP and WiFi.")
        except requests.exceptions.Timeout:
            print(f"[WiFi] WARN: Arduino did not respond in time — skipping frame.")
        except Exception as e:
            print(f"[WiFi] WARN: {e}")

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


def maybe_send(message: str):
    """Send only when the message changes or after SEND_INTERVAL_S seconds."""
    global _last_message, _last_sent_at
    with _send_lock:
        now = time.time()
        if message != _last_message or (now - _last_sent_at) >= SEND_INTERVAL_S:
            send_to_arduino(message)
            _last_message = message
            _last_sent_at = now

# ─── Core Detection Logic ──────────────────────────────────────────────────────

def is_occupied(frame: np.ndarray, roi: tuple) -> bool:
    """Return True if a car is detected in the ROI region."""
    x1, y1, x2, y2 = roi
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return False

    crop  = frame[y1:y2, x1:x2]
    gray  = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur  = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, PIXEL_THRESHOLD, 255, cv2.THRESH_BINARY)

    ratio = np.count_nonzero(thresh) / thresh.size
    return ratio > OCCUPIED_RATIO


def find_best_slot(statuses: dict):
    """Return the first free slot's info dict, or None if all are occupied."""
    for slot_id, occupied in statuses.items():
        if not occupied:
            return PARKING_SLOTS[slot_id]
    return None


def build_message(slot_info) -> str:
    if slot_info is None:
        return "NONE"
    return f"F{slot_info['floor']}B{slot_info['block']}S{slot_info['slot']}"

# ─── Visualisation ─────────────────────────────────────────────────────────────

def annotate_frame(frame: np.ndarray, statuses: dict, best_slot) -> np.ndarray:
    vis = frame.copy()

    for slot_id, occupied in statuses.items():
        info = PARKING_SLOTS[slot_id]
        x1, y1, x2, y2 = info["roi"]
        is_best = (best_slot is not None and best_slot == info)

        color     = (0, 0, 220) if occupied else (0, 200, 0)
        thickness = 3 if is_best else 2
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, thickness)

        label  = f"F{info['floor']} B{info['block']} S{info['slot']}"
        status = "OCC" if occupied else "FREE"
        cv2.putText(vis, label,  (x1+4, y1+18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        cv2.putText(vis, status, (x1+4, y1+34), cv2.FONT_HERSHEY_SIMPLEX, 0.40, color, 1)
        if is_best:
            cv2.putText(vis, "BEST", (x1+4, y1+50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 2)

    msg = build_message(best_slot)
    cv2.putText(vis, f"Sending to Arduino: {msg}",
                (10, vis.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
    cv2.putText(vis, f"Arduino @ {ARDUINO_IP}",
                (10, vis.shape[0] - 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
    return vis

# ─── Calibration Mode ──────────────────────────────────────────────────────────

mouse_pos = (0, 0)

def on_mouse(event, x, y, flags, param):
    global mouse_pos
    mouse_pos = (x, y)


def run_calibration(cap):
    print("\n[CALIBRATE] Hover mouse over parking space corners.")
    print("            Note (x1,y1) top-left and (x2,y2) bottom-right for each slot.")
    print("            Press 'q' to quit calibration.\n")
    cv2.namedWindow("Calibrate")
    cv2.setMouseCallback("Calibrate", on_mouse)

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        vis = frame.copy()
        x, y = mouse_pos
        cv2.drawMarker(vis, (x, y), (0, 255, 255), cv2.MARKER_CROSS, 20, 1)
        cv2.putText(vis, f"({x}, {y})", (x + 8, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        for sid, info in PARKING_SLOTS.items():
            x1, y1, x2, y2 = info["roi"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (100, 200, 100), 1)
            cv2.putText(vis, f"S{sid}", (x1 + 4, y1 + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 200, 100), 1)
        cv2.imshow("Calibrate", vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cv2.destroyAllWindows()

# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[INFO] Connecting to camera: {CAMERA_URL}")
    cap = cv2.VideoCapture(CAMERA_URL)
    if not cap.isOpened():
        print("[ERROR] Cannot open camera. Check that IP Webcam is running and CAMERA_URL is correct.")
        sys.exit(1)
    print("[INFO] Camera connected.")

    if CALIBRATE_MODE:
        run_calibration(cap)
        cap.release()
        return

    # Quick connectivity check to Arduino
    print(f"[INFO] Checking Arduino at {ARDUINO_IP} ...")
    try:
        requests.get(f"{ARDUINO_IP}/?msg=TEST", timeout=3)
        print("[INFO] Arduino reachable.")
    except Exception:
        print(f"[WARN] Arduino not responding at {ARDUINO_IP}.")
        print("       Continuing anyway — will retry each send.")

    cv2.namedWindow("Smart Parking Monitor")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Frame read failed, retrying...")
            time.sleep(0.5)
            continue

        statuses  = {sid: is_occupied(frame, info["roi"])
                     for sid, info in PARKING_SLOTS.items()}
        best_slot = find_best_slot(statuses)
        message   = build_message(best_slot)

        maybe_send(message)

        vis = annotate_frame(frame, statuses, best_slot)
        cv2.imshow("Smart Parking Monitor", vis)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Shut down.")


if __name__ == "__main__":
    main()
