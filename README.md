# IBVAP: Integrated Border & Perimeter Video Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![NVIDIA CUDA](https://img.shields.io/badge/CUDA-Accelerated-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://developer.nvidia.com/cuda-toolkit)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00FFFF?style=for-the-badge)](https://docs.ultralytics.com/)
[![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)

> **IBVAP** is an edge-native video analytics prototype engineered for real-time perimeter monitoring, user-defined safe-zone tracking, dynamic contextual threat scoring, license plate region processing (ANPR), and asynchronous emergency alerts.

---

## 📌 About the Project

### System Overview
**IBVAP (Integrated Border & Perimeter Video Analytics Platform)** is an edge-native surveillance and perimeter monitoring prototype engineered to automate intrusion detection and threat assessment in real time. Traditional surveillance setups rely heavily on continuous manual monitoring by operators, leading to screen fatigue and delayed response times during breach events. IBVAP addresses this operational bottleneck by combining local computer vision inference with an automated contextual risk-scoring matrix that evaluates and prioritizes suspicious events before alerting personnel.

By executing primary AI detection locally on edge GPU hardware, the platform minimizes external cloud processing requirements and ensures low-latency target tracking. When a critical zone breach occurs, IBVAP triggers asynchronous remote notifications via Telegram, ensuring security teams receive real-time breach telemetry and high-resolution event snapshots even when away from control room monitors.

---

### Key Capabilities & System Focus

* **Local Edge Analytics:** Performs primary object detection (detecting targets like persons and vehicles) locally on edge hardware using YOLOv8 with CUDA acceleration support.
* **Dynamic Operator-Defined Safe Zones:** Enables operators to draw and adjust interactive multi-point polygon boundaries directly over live RTSP or camera video feeds through a web UI.
* **Contextual Threat Matrix:** Evaluates intrusion events using a 0–100 heuristic risk scale based on target class, dwell time, movement parameters, and zone severity to filter out routine non-threat events.
* **Automated ANPR Integration:** Processes vehicle region-of-interest (ROI) crops using OpenCV and EasyOCR to extract and log license plate numbers during perimeter events.
* **Asynchronous Multi-Channel Alerts:** Utilizes a non-blocking background worker thread to dispatch immediate breach notifications and image snapshots via Telegram without interrupting the main video stream capture loop.
* **Unified Command Dashboard:** Provides a centralized, Flask-based browser interface displaying active camera feeds, status indicators, live analytics, and breach snapshot history.

---

## 📸 System Overview

![IBVAP Live Dashboard](docs/assets/dashboard_overview.png)
*Figure 1: IBVAP Monitoring Command Dashboard displaying live camera stream, zone boundary overlays, and real-time threat telemetry.*

---

## 🏗 Platform Architecture

```mermaid
graph TD
    A[Camera Feed / DirectShow / RTSP] --> B[Frame Ingestion & Preprocessing]
    B --> C[PyTorch / CUDA YOLOv8 Inference Engine]
    C --> D{Zone Collision Manager}
    C --> E[ANPR / EasyOCR Subsystem]
    
    D -->|Inside Restricted Zone| F[Contextual Threat Matrix Engine]
    D -->|Outside Restricted Zone| G[Live UI Overlay Render]
    
    F --> H[Flask Control Dashboard]
    F -->|Threat Threshold Exceeded| I[Asynchronous Alert Thread]

    
    E --> H
    I --> J[Telegram Bot API Alert Dispatch]
```
## 🖼 Real-World Hardware & Field Testing

| Local Edge Hardware Testbed | Real-Time Safe-Zone Tracking |
| :---: | :---: |
| ![Hardware Setup](docs/assets/hardware_setup.jpg) | ![YOLO Tracking](docs/assets/yolo_tracking.png) |
| *Figure 2: Edge hardware configuration running local analytics with a USB camera source.* | *Figure 3: Active target detection with bounding box classification and custom polygon zone overlays.* |

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
* **Python 3.10+** installed on the host system.
* **NVIDIA Drivers & CUDA Toolkit** (Required for GPU inference; defaults to CPU execution if CUDA is unavailable).

  # Clone repository
git clone [https://github.com/your-username/IBVAP.git](https://github.com/your-username/IBVAP.git)
cd IBVAP

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

## 🚀 Running the Application

Start the IBVAP platform execution loop:

```bash
python app.py

```
## 📁 Repository Structure

```text
IBVAP/
├── IBVAP images/                 # Documentation screenshots and UI assets
├── __pycache__/                  # Python compiled bytecode cache
├── security_logs/                # Generated system event logs
├── static/
│   └── breaches/                 # Captured breach snapshot images
├── telegram_alerts/              # Dispatched alert records
├── templates/                    # Web UI HTML templates
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git tracking exclusion configuration
├── README.md                     # Primary repository documentation
├── anpr_engine.py                # License plate processing submodule
├── app.py                        # Main Flask server & application entry point
├── frs_anpr_module.py            # Facial recognition & ANPR integration module
├── haarcascade_frontalface_default.xml # Haar Cascade face detection classifier
├── main.py                       # Standalone engine execution script
├── mudule1_virtual_fence.py      # Core virtual fence & zone management logic
├── module4_event_logger.py       # Event logging utility module
├── module5_alarm_fence.py        # Alarm trigger and breach handler
├── module6_loitering_capture.py  # Dwell time and loitering analysis module
├── module7_telegram_alerts.py    # Asynchronous Telegram alert integration
├── test_alert.ipy                # Alert system Jupyter testing notebook
├── test_telegram.py              # Telegram API verification script
├── virtual_fence.py              # Polygon spatial math utilities
└── yolov8n.pt                    # Pre-trained YOLOv8 nano weights model
```
## 📜 Compliance & Guidelines Alignment

* **MHA PIDS Guidelines:** Aligned with Ministry of Home Affairs Qualitative Requirements for Perimeter Intrusion Detection Systems.
* **ONVIF Framework:** Aligned with industry standards for IP security camera streaming protocols (RTSP/RTP) and camera interoperability.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).



