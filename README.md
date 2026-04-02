# 🅿️ Smart IoT Parking Detection System

> A prototype IoT system that uses a mobile phone camera and OpenCV to detect empty parking slots in real time, and displays the best available slot on a 16×2 LCD via an Arduino Uno R4 WiFi — fully wireless, no USB cable needed during operation.

---

## 📸 System Overview

```
┌─────────────────┐        WiFi (HTTP)       ┌──────────────────────┐
│  Android Phone  │ ──────────────────────►  │  Arduino Uno R4 WiFi │
│  (IP Webcam app)│                          │  + 16×2 LCD (I2C)    │
└────────┬────────┘                          └──────────────────────┘
         │ WiFi video stream
         ▼
┌─────────────────────────────────────────────┐
│           PC / Laptop                       │
│  Python 3 + OpenCV                          │
│  • Reads camera feed                        │
│  • Analyses ROI regions per parking slot    │
│  • Detects car presence via thresholding    │
│  • Sends best free slot → Arduino over WiFi │
└─────────────────────────────────────────────┘
```

The Python script analyses each parking space as a **Region of Interest (ROI)** in the camera frame. An interactive setup wizard lets you click the 4 corners of your parking area and specify rows × columns — the ROIs are auto-generated and saved to `parking_config.json`.

---

## ✨ Features

- **Wireless end-to-end** — Arduino communicates over WiFi, no USB serial cable needed
- **Interactive ROI setup** — click corners on the live feed, enter rows × columns, done
- **Perspective-aware grid** — ROIs follow camera angle (bilinear interpolation across quad)
- **Auto-save config** — `parking_config.json` persists between runs; press `R` to redo setup
- **Smart throttling** — sends updates only when slot status changes + keep-alive every 5 s
- **Non-blocking WiFi sends** — each HTTP request runs in a background thread so the video loop never freezes
- **LCD displays best slot** — format: `F1 B2 S6` (Floor · Block · Slot)
- **Custom LCD characters** — check mark, cross mark, and car icon
- **Value-engineered BOM** — full cost analysis Excel workbook included (`docs/`)

---

## 🗂️ Repository Structure

```
smart-parking-iot/
├── arduino/
│   ├── smart_parking_wifi/
│   │   └── smart_parking_wifi.ino      # Arduino WiFi HTTP server + LCD driver
│   └── libraries.md                    # Required Arduino libraries
├── python/
│   ├── smart_parking_auto_roi.py       # Main script (auto ROI + WiFi send)
│   ├── smart_parking_wifi.py           # Manual ROI version (fixed slots dict)
│   └── requirements.txt               # Python dependencies
├── docs/
│   └── VE_Cost_Analysis_SmartParking.xlsx  # Value engineering & cost analysis
├── assets/
│   └── system_diagram.png             # Architecture diagram (add your own)
├── parking_config.json                # Auto-generated after first setup run
├── .gitignore
└── README.md
```

---

## 🛒 Hardware Requirements

| # | Component | Specification | Approx. Cost | Where to Buy |
|---|-----------|--------------|-------------|-------------|
| 1 | **Arduino Uno R4 WiFi** | R4 series, onboard ESP32-S3 WiFi | ~$25 | Arduino Store / Robu.in |
| 2 | **16×2 LCD Display** | HD44780 compatible | ~$2 | AliExpress / Robu.in |
| 3 | **I2C LCD Module** | PCF8574 backpack (0x27 or 0x3F) | ~$1.50 | AliExpress |
| 4 | **Android Smartphone** | Any Android with rear camera | User-owned | — |
| 5 | **USB Power Bank** | 5 V, min 1 A output, ≥ 2000 mAh | ~$8 | Any store |
| 6 | **USB-A to USB-C Cable** | 1 m, for Arduino power | ~$1.50 | Any store |
| 7 | **Jumper Wires** | Male-to-Female pack (×10 minimum) | ~$1.20 | AliExpress |
| 8 | **Breadboard** | Half-size (400 tie points) | ~$1.80 | AliExpress / Robu.in |
| 9 | **WiFi Router** | 2.4 GHz, any home/lab router | User-owned | — |

**Total estimated hardware cost: ~$16–20** (excluding phone and router)

### Wiring — LCD to Arduino Uno R4 WiFi

| LCD I2C Pin | Arduino Pin |
|-------------|-------------|
| VCC | 5V |
| GND | GND |
| SDA | A4 |
| SCL | A5 |

> **Note:** If the LCD does not light up after uploading, try changing the I2C address in the sketch from `0x27` to `0x3F`.

---

## 💻 Software Requirements

### Python (PC / Laptop)

- Python **3.8 or higher**
- Install all dependencies:

```bash
pip install -r python/requirements.txt
```

`requirements.txt` contents:

```
opencv-python>=4.8.0
numpy>=1.24.0
requests>=2.31.0
```

### Arduino IDE

- Arduino IDE **2.x** (recommended) — [download here](https://www.arduino.cc/en/software)
- Board package: **Arduino UNO R4 Boards** (install via Boards Manager)
- Required libraries (install via Library Manager):

| Library | Author | Purpose |
|---------|--------|---------|
| `LiquidCrystal I2C` | Frank de Brabander | I2C LCD control |
| `WiFiS3` | Arduino | WiFi for Uno R4 (included with R4 board package) |

### Mobile App (Android)

- **IP Webcam** by Pavel Khlebovich — free on Google Play Store
- Start the server, note the IP address shown (e.g. `http://192.168.1.5:8080`)

> **iPhone users:** Use **iVCam** or **DroidCam** instead — set `CAMERA_URL` to their stream URL.

---

## 🚀 Setup & Usage

### Step 1 — Flash the Arduino

1. Open `arduino/smart_parking_wifi/smart_parking_wifi.ino` in Arduino IDE
2. Edit the credentials at the top:
   ```cpp
   const char* SSID     = "YOUR_WIFI_NAME";
   const char* PASSWORD = "YOUR_WIFI_PASSWORD";
   ```
3. Select **Tools → Board → Arduino UNO R4 WiFi**
4. Upload via USB
5. Open **Serial Monitor** at 9600 baud — the Arduino's IP address will print and appear on the LCD

### Step 2 — Start IP Webcam on your phone

1. Open the IP Webcam app
2. Scroll to the bottom and tap **Start server**
3. Note the URL shown (e.g. `http://192.168.1.5:8080`)
4. Confirm the feed in a browser on your PC

### Step 3 — Configure and run the Python script

1. Open `python/smart_parking_auto_roi.py`
2. Edit the two config lines:
   ```python
   CAMERA_URL = "http://192.168.1.5:8080/video"   # your phone's IP Webcam URL
   ARDUINO_IP = "http://192.168.1.42"              # Arduino's IP from LCD / Serial Monitor
   SETUP_MODE = True                               # True on first run
   ```
3. Run the script:
   ```bash
   cd python
   python smart_parking_auto_roi.py
   ```

### Step 4 — ROI Setup (first run only)

A live camera window opens. Follow the on-screen instructions:

1. **Click the 4 corners** of your parking area in order:
   `Top-left → Top-right → Bottom-right → Bottom-left`
2. Press **Enter** to confirm
3. In the terminal, enter the **number of rows** and **columns** of parking slots
4. Preview the auto-generated grid overlay — press **Enter** to save or **R** to redo
5. Config is saved to `parking_config.json`

### Step 5 — Normal operation

After setup, set `SETUP_MODE = False` in the script. From now on:
- Run `python smart_parking_auto_roi.py` — loads saved config instantly
- The OpenCV window shows coloured overlays: **green = free**, **red = occupied**, **cyan = best slot**
- The Arduino LCD shows the best available slot in format `F1 B2 S6`
- Press **R** at any time to re-run setup if the camera moves
- Press **Q** to quit

---

## 📡 Communication Protocol

### Python → Arduino (HTTP GET)

```
GET http://<arduino-ip>/?msg=F1B2S6
```

| Message | Meaning |
|---------|---------|
| `F1B2S6` | Floor 1, Block 2, Slot 6 is the best available |
| `NONE` | No free slots available |

### LCD Display Format

```
┌────────────────┐
│ ✓ Available    │   ← Row 1 (with custom check-mark character)
│ F1  B2  S6     │   ← Row 2: Floor · Block · Slot
└────────────────┘
```

---

## 🔧 Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| LCD shows nothing | Wrong I2C address | Change `0x27` → `0x3F` in sketch |
| Arduino not found on network | IP changed after reboot | Assign static IP in router DHCP settings |
| Camera feed won't open | Wrong URL or phone on mobile data | Ensure phone is on WiFi, check IP Webcam URL |
| False "occupied" on empty slots | Threshold too low | Increase `OCCUPIED_RATIO` (e.g. `0.25` → `0.40`) |
| Car not detected | Threshold too high | Decrease `PIXEL_THRESHOLD` (e.g. `60` → `40`) |
| WiFi send errors | Arduino and PC on different subnets | Ensure both devices are on the same router |
| ROIs shifted after run | Camera moved | Press `R` during runtime to redo setup |

---

## 🏗️ Value Engineering & Cost Analysis

A full cost analysis workbook is included at `docs/VE_Cost_Analysis_SmartParking.xlsx`.

| Scenario | Unit Cost | vs Baseline |
|----------|-----------|------------|
| Baseline (as-built prototype) | ~$97.50 | — |
| Value-Engineered (VE) | ~$58.20 | −40% |
| Aggressive (production batch) | ~$38.00 | −61% |

**Top cost-reduction opportunities:**

1. **Replace Arduino Uno R4 WiFi → ESP32-CAM** — saves $18.50/unit, eliminates phone dependency
2. **Automate software setup** — scripted installer reduces 6 hrs labour to 1.5 hrs
3. **Custom PCB** — eliminates breadboard and jumper wires, saves $4.80/unit at qty 5+
4. **Volume purchasing** — 22% further reduction at qty 100

---

## 🔮 Future Improvements

- [ ] Replace phone + PC with a single **ESP32-CAM** running lightweight detection
- [ ] Add **per-slot LED indicators** (green/red) using a 74HC595 shift register
- [ ] Push occupancy data to **ThingSpeak** or **Blynk** cloud dashboard
- [ ] Add a **buzzer** alert when a new slot becomes available
- [ ] Support **multiple camera angles** (one Python instance per floor)
- [ ] YOLO-based detection for improved accuracy under shadows and lighting changes

---

## 📄 License

This project is released under the **MIT License** — see [`LICENSE`](LICENSE) for details.

---

## 🙏 Acknowledgements

- [IP Webcam app](https://play.google.com/store/apps/details?id=com.pas.webcam) by Pavel Khlebovich
- [LiquidCrystal I2C library](https://github.com/johnrickman/LiquidCrystal_I2C) by Frank de Brabander
- [OpenCV](https://opencv.org/) — Open Source Computer Vision Library
- Arduino community for the WiFiS3 library
