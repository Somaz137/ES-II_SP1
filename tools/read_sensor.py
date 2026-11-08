#!/usr/bin/env python3
"""Print parsed JSON readings streamed by firmware/room_environment_safety_control_bme680.ino."""
import argparse
import json
import time
import serial
from serial.tools import list_ports

p = argparse.ArgumentParser()
p.add_argument('--port', default=None, help='ESP32 port, e.g. /dev/ttyUSB0')
p.add_argument('--baud', type=int, default=115200)
a = p.parse_args()
if a.port is None:
    ports = list(list_ports.comports())
    if not ports:
        p.error('No serial ports found. Plug in the ESP32 and check permissions.')
    print('Available serial ports:')
    for port in ports:
        print(f'  {port.device}: {port.description}')
    p.error('Specify --port /dev/ttyUSB0 (or the actual device above)')

with serial.Serial(a.port, a.baud, timeout=2) as esp:
    time.sleep(2)  # ESP32 may reset when serial opens; lecture Module 3.3
    while True:
        line = esp.readline().decode('utf-8', errors='replace').strip()
        if not line:
            print('No data received (timeout)')
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            print('Skipped non-JSON line:', line)
            continue
        print(obj)
