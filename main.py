import os
import sys
import torch

def check_system_health():
    print("=" * 60)
    print("   IBVAP — INTELLIGENT BORDER VIDEO ANALYTICS PLATFORM   ")
    print("=" * 60)
    
    # 1. GPU Check
    cuda_available = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_available else "CPU (Fallback)"
    print(f"[SYSTEM CHECK] Hardware Acceleration: [{device_name}]")
    
    # 2. Directory Checks
    os.makedirs("security_logs", exist_ok=True)
    os.makedirs("telegram_alerts", exist_ok=True)
    print(f"[SYSTEM CHECK] Output directories verified.")
    print("-" * 60)

def display_menu():
    print("\nSelect a Security Module to Execute:\n")
    print("  [1] Module 1: Virtual Safe Zone & Polygon Intrusion Engine")
    print("  [2] Module 4: Low-Bandwidth Event Logger & CSV Snapshot Engine")
    print("  [3] Module 5: Continuous Audio Alarm Engine")
    print("  [4] Module 6: 3-Second Loitering Auto-Capture Engine")
    print("  [5] Module 7: Full Telegram Security Dispatcher (ALARM + LIVE PHOTO)")
    print("  [6] Launch Flask Web Command & Control Dashboard")
    print("  [0] Exit Platform\n")

def run_module(script_name):
    if os.path.exists(script_name):
        print(f"\n[LAUNCHING]: Running {script_name}...\n")
        os.system(f"{sys.executable} {script_name}")
    else:
        print(f"\n[ERROR]: Could not find '{script_name}' in the current directory!")

def main():
    check_system_health()
    
    while True:
        display_menu()
        choice = input("Enter choice [0-6]: ").strip()
        
        if choice == '1':
            run_module("module1_virtual_fence.py")
        elif choice == '2':
            run_module("module4_event_logger.py")
        elif choice == '3':
            run_module("module5_alarm_fence.py")
        elif choice == '4':
            run_module("module6_loitering_capture.py")
        elif choice == '5':
            run_module("module7_telegram_alerts.py")
        elif choice == '6':
            run_module("app.py")
        elif choice == '0':
            print("\nShutting down IBVAP Platform. Security session terminated.\n")
            break
        else:
            print("\n[INVALID INPUT]: Please enter a number between 0 and 6.")

if __name__ == "__main__":
    main()