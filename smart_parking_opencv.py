"""
Smart Parking System — Auto ROI Detection (WiFi version)
---------------------------------------------------------
Requirements:
    pip install opencv-python numpy requests

How it works:
    FIRST RUN  → Set SETUP_MODE = True
                 Click the 4 corners of your parking area in order:
                   top-left → top-right → bottom-right → bottom-left
                 Enter number of rows and columns when prompted.
                 ROIs are saved to parking_config.json automatically.

    AFTER THAT → Set SETUP_MODE = False
                 Script loads saved ROIs and runs detection normally.

    RE-SETUP   → Delete parking_config.json (or set SETUP_MODE = True again).
"""

import cv2
import numpy as np
import requests
import time
import sys
import threading
import json
import os

# ─── Configuration ────────────────────────────────────────────────────────────

CAMERA_URL   = "http://10.38.229.114:8080/video"
ARDUINO_IP   = "http://10.38.229.172"
SETUP_MODE   = True          # True = run corner-picker setup; False = use saved config
CONFIG_FILE  = "parking_config.json"

# ─── Detection Parameters ─────────────────────────────────────────────────────
PIXEL_THRESHOLD = 60
OCCUPIED_RATIO  = 0.25
SEND_INTERVAL_S = 5.0

# ─── ROI Config Save / Load ───────────────────────────────────────────────────

def save_config(slots: dict):
    data = {
        str(k): {
            "floor": v["floor"],
            "block": v["block"],
            "slot":  v["slot"],
            "roi":   list(v["roi"])
        }
        for k, v in slots.items()
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[INFO] Saved {len(slots)} slots to {CONFIG_FILE}")


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    slots = {
        int(k): {
            "floor": v["floor"],
            "block": v["block"],
            "slot":  v["slot"],
            "roi":   tuple(v["roi"])
        }
        for k, v in data.items()
    }
    print(f"[INFO] Loaded {len(slots)} slots from {CONFIG_FILE}")
    return slots

# ─── Auto ROI Generator ───────────────────────────────────────────────────────

def generate_rois(corners: list, rows: int, cols: int,
                  floor: int = 1) -> dict:
    """
    Given 4 corners (TL, TR, BR, BL) of the parking area,
    divide into a rows×cols grid and return a PARKING_SLOTS dict.

    Each slot is assigned:
        floor  = floor (same for all in this camera view)
        block  = row number  (1-indexed)
        slot   = column number (1-indexed)
    """
    tl, tr, br, bl = [np.float32(c) for c in corners]
    slots = {}
    slot_id = 1

    for r in range(rows):
        r0 = r / rows
        r1 = (r + 1) / rows

        # Interpolate left and right edges along the quad
        left_top    = tl + r0 * (bl - tl)
        left_bot    = tl + r1 * (bl - tl)
        right_top   = tr + r0 * (br - tr)
        right_bot   = tr + r1 * (br - tr)

        for c in range(cols):
            c0 = c / cols
            c1 = (c + 1) / cols

            # Bilinear interpolation for each corner of the cell
            p_tl = left_top  + c0 * (right_top  - left_top)
            p_tr = left_top  + c1 * (right_top  - left_top)
            p_bl = left_bot  + c0 * (right_bot  - left_bot)
            p_br = left_bot  + c1 * (right_bot  - left_bot)

            # Bounding box of the (possibly skewed) cell
            xs = [p_tl[0], p_tr[0], p_bl[0], p_br[0]]
            ys = [p_tl[1], p_tr[1], p_bl[1], p_br[1]]

            # Shrink by 8px per side to avoid lane markings
            pad = 8
            x1 = int(min(xs)) + pad
            y1 = int(min(ys)) + pad
            x2 = int(max(xs)) - pad
            y2 = int(max(ys)) - pad

            slots[slot_id] = {
                "floor": floor,
                "block": r + 1,     # row = block
                "slot":  c + 1,     # col = slot
                "roi":   (x1, y1, x2, y2)
            }
            slot_id += 1

    return slots

# ─── Interactive Setup Mode ───────────────────────────────────────────────────

setup_corners  = []
setup_done     = False
hover_pt       = (0, 0)
CORNER_LABELS  = ["Top-left", "Top-right", "Bottom-right", "Bottom-left"]


def on_setup_mouse(event, x, y, flags, param):
    global hover_pt, setup_done
    hover_pt = (x, y)
    if event == cv2.EVENT_LBUTTONDOWN and not setup_done:
        if len(setup_corners) < 4:
            setup_corners.append((x, y))
            print(f"  Corner {len(setup_corners)}/4 set: {CORNER_LABELS[len(setup_corners)-1]} → ({x}, {y})")
        if len(setup_corners) == 4:
            setup_done = True


def draw_setup_overlay(frame: np.ndarray) -> np.ndarray:
    vis = frame.copy()
    h, w = vis.shape[:2]

    # Instructions bar at the top
    cv2.rectangle(vis, (0, 0), (w, 36), (0, 0, 0), -1)
    n = len(setup_corners)
    if n < 4:
        msg = f"Click {CORNER_LABELS[n]}  ({n}/4 corners set)  |  Right-click to undo"
    else:
        msg = "All 4 corners set — press ENTER to confirm, R to redo"
    cv2.putText(vis, msg, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 220), 1)

    # Draw placed corners and connecting lines
    for i, pt in enumerate(setup_corners):
        cv2.circle(vis, pt, 7, (0, 255, 100), -1)
        cv2.circle(vis, pt, 7, (255, 255, 255), 1)
        cv2.putText(vis, CORNER_LABELS[i], (pt[0] + 10, pt[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 100), 1)

    if len(setup_corners) >= 2:
        for i in range(len(setup_corners) - 1):
            cv2.line(vis, setup_corners[i], setup_corners[i+1], (0, 200, 80), 1)

    if len(setup_corners) == 4:
        cv2.line(vis, setup_corners[3], setup_corners[0], (0, 200, 80), 1)
        # Fill quad with light overlay
        pts = np.array(setup_corners, dtype=np.int32)
        overlay = vis.copy()
        cv2.fillPoly(overlay, [pts], (0, 200, 80))
        cv2.addWeighted(overlay, 0.12, vis, 0.88, 0, vis)
        cv2.polylines(vis, [pts], True, (0, 255, 100), 2)

    # Crosshair at hover
    if not setup_done:
        cv2.drawMarker(vis, hover_pt, (200, 200, 200), cv2.MARKER_CROSS, 16, 1)
        cv2.putText(vis, f"({hover_pt[0]},{hover_pt[1]})",
                    (hover_pt[0] + 8, hover_pt[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)

    return vis


def draw_grid_preview(frame: np.ndarray, slots: dict) -> np.ndarray:
    vis = frame.copy()
    h, w = vis.shape[:2]
    cv2.rectangle(vis, (0, 0), (w, 36), (0, 0, 0), -1)
    cv2.putText(vis, "Grid preview — press ENTER to save, R to redo",
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 220), 1)
    for sid, info in slots.items():
        x1, y1, x2, y2 = info["roi"]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 200, 80), 1)
        label = f"F{info['floor']} B{info['block']} S{info['slot']}"
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.putText(vis, label, (x1 + 4, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 230, 100), 1)
    return vis


def run_setup(cap) -> dict:
    global setup_corners, setup_done

    cv2.namedWindow("Parking Setup")
    cv2.setMouseCallback("Parking Setup", on_setup_mouse)

    print("\n[SETUP] Click the 4 corners of the parking area in this order:")
    for lbl in CORNER_LABELS:
        print(f"         {lbl}")
    print()

    # ── Phase 1: Pick 4 corners ──────────────────────────────────────────────
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        vis = draw_setup_overlay(frame)
        cv2.imshow("Parking Setup", vis)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('r') or key == ord('R'):
            setup_corners.clear()
            setup_done = False
            print("[SETUP] Corners reset.")

        if key == 13 and setup_done:   # ENTER
            break

    # ── Phase 2: Ask for rows and cols ───────────────────────────────────────
    print()
    while True:
        try:
            rows = int(input("[SETUP] How many ROWS of parking slots? "))
            cols = int(input("[SETUP] How many COLUMNS (slots per row)? "))
            floor= int(input("[SETUP] Floor number for this camera? [1] ") or "1")
            if rows > 0 and cols > 0:
                break
            print("        Must be positive integers.")
        except ValueError:
            print("        Please enter a number.")

    slots = generate_rois(setup_corners, rows, cols, floor)
    print(f"\n[SETUP] Generated {len(slots)} ROIs ({rows} rows × {cols} cols).")

    # ── Phase 3: Preview the grid ────────────────────────────────────────────
    print("[SETUP] Review the grid preview. Press ENTER to save, R to redo.")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        vis = draw_grid_preview(frame, slots)
        cv2.imshow("Parking Setup", vis)
        key = cv2.waitKey(1) & 0xFF

        if key == 13:     # ENTER — happy with it
            save_config(slots)
            break
        if key == ord('r') or key == ord('R'):
            setup_corners.clear()
            setup_done = False
            print("[SETUP] Restarting corner selection...")
            cv2.destroyWindow("Parking Setup")
            return run_setup(cap)   # recursive redo

    cv2.destroyWindow("Parking Setup")
    return slots

# ─── WiFi Send ────────────────────────────────────────────────────────────────

_last_message = ""
_last_sent_at = 0.0
_send_lock    = threading.Lock()


def send_to_arduino(message: str):
    def _send():
        try:
            r = requests.get(f"{ARDUINO_IP}/?msg={message}", timeout=2)
            print(f"[WiFi] Sent: {message}  →  {r.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"[WiFi] ERROR: Cannot reach Arduino at {ARDUINO_IP}")
        except requests.exceptions.Timeout:
            print("[WiFi] WARN: Arduino timeout — skipping frame")
        except Exception as e:
            print(f"[WiFi] WARN: {e}")
    threading.Thread(target=_send, daemon=True).start()


def maybe_send(message: str):
    global _last_message, _last_sent_at
    with _send_lock:
        now = time.time()
        if message != _last_message or (now - _last_sent_at) >= SEND_INTERVAL_S:
            send_to_arduino(message)
            _last_message = message
            _last_sent_at = now

# ─── Detection ────────────────────────────────────────────────────────────────

def is_occupied(frame: np.ndarray, roi: tuple) -> bool:
    x1, y1, x2, y2 = roi
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return False
    crop  = frame[y1:y2, x1:x2]
    gray  = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur  = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(blur, PIXEL_THRESHOLD, 255, cv2.THRESH_BINARY)
    return (np.count_nonzero(th) / th.size) > OCCUPIED_RATIO


def find_best_slot(statuses: dict, slots: dict):
    for sid, occupied in statuses.items():
        if not occupied:
            return slots[sid]
    return None


def build_message(slot_info) -> str:
    if slot_info is None:
        return "NONE"
    return f"F{slot_info['floor']}B{slot_info['block']}S{slot_info['slot']}"

# ─── Annotated Frame ──────────────────────────────────────────────────────────

def annotate_frame(frame, statuses, best_slot, slots):
    vis = frame.copy()
    h, w = vis.shape[:2]
    for sid, occupied in statuses.items():
        info = slots[sid]
        x1, y1, x2, y2 = info["roi"]
        is_best = (best_slot is not None and best_slot == info)
        color = (0, 0, 220) if occupied else (0, 200, 0)
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 3 if is_best else 1)
        lbl = f"F{info['floor']} B{info['block']} S{info['slot']}"
        cv2.putText(vis, lbl,                        (x1+4, y1+16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)
        cv2.putText(vis, "OCC" if occupied else "FREE", (x1+4, y1+30), cv2.FONT_HERSHEY_SIMPLEX, 0.34, color, 1)
        if is_best:
            cv2.putText(vis, "BEST", (x1+4, y1+44), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)

    free  = sum(1 for v in statuses.values() if not v)
    total = len(statuses)
    msg   = build_message(best_slot)
    cv2.rectangle(vis, (0, h - 42), (w, h), (0, 0, 0), -1)
    cv2.putText(vis, f"Free: {free}/{total}  |  Sending: {msg}  |  Arduino: {ARDUINO_IP}",
                (10, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
    cv2.putText(vis, f"Slots: {total}  (auto-detected grid)",
                (10, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1)
    return vis

# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[INFO] Connecting to camera: {CAMERA_URL}")
    cap = cv2.VideoCapture(CAMERA_URL)
    if not cap.isOpened():
        print("[ERROR] Cannot open camera. Check IP Webcam is running and CAMERA_URL is correct.")
        sys.exit(1)
    print("[INFO] Camera connected.")

    # ── Load or run setup ────────────────────────────────────────────────────
    if SETUP_MODE:
        slots = run_setup(cap)
    else:
        slots = load_config()
        if not slots:
            print("[ERROR] No config found. Set SETUP_MODE = True to run setup first.")
            cap.release()
            sys.exit(1)

    print(f"[INFO] Running with {len(slots)} parking slots.")

    # ── Quick Arduino ping ───────────────────────────────────────────────────
    try:
        requests.get(f"{ARDUINO_IP}/?msg=TEST", timeout=3)
        print("[INFO] Arduino reachable.")
    except Exception:
        print(f"[WARN] Arduino not responding at {ARDUINO_IP} — will keep trying.")

    cv2.namedWindow("Smart Parking Monitor")

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.5)
            continue

        statuses  = {sid: is_occupied(frame, info["roi"]) for sid, info in slots.items()}
        best_slot = find_best_slot(statuses, slots)
        maybe_send(build_message(best_slot))

        vis = annotate_frame(frame, statuses, best_slot, slots)
        cv2.imshow("Smart Parking Monitor", vis)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord('r') or key == ord('R'):
            # Live redo setup without restarting the script
            print("[INFO] Entering re-setup mode...")
            slots = run_setup(cap)
            print(f"[INFO] Resumed with {len(slots)} slots.")

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Shut down.")


if __name__ == "__main__":
    main()