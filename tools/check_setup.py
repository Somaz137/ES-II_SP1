#!/usr/bin/env python3
"""Read-only SAFE-ROOM runtime/package/port diagnostics."""
import glob
import os
import platform
import sqlite3
import sys
from importlib import metadata

PINS = {
    'numpy': '1.26.4',
    'opencv-python': '4.11.0.86',
    'pyserial': '3.5',
    'Flask': '3.0.3',
    'PyYAML': '6.0.1',
    'pytest': '8.2.0',
}
print('Platform:', platform.platform())
print('Architecture:', platform.machine())
print('Python:', sys.version.split()[0])
print('Python executable:', sys.executable)
print('Virtual environment:', sys.prefix != sys.base_prefix)
for pkg, target in PINS.items():
    try:
        found = metadata.version(pkg)
    except metadata.PackageNotFoundError:
        found = 'NOT INSTALLED'
    print(f'{pkg:16} expected={target:12} installed={found:16} ' + ('OK' if found == target else 'CHECK'))
print('SQLite:', sqlite3.sqlite_version, '(Python stdlib)')
ports = sorted(glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))
print('Serial ports:', ports or 'none currently visible')
print('Video devices:', sorted(glob.glob('/dev/video*')) or 'none currently visible')
print('dialout group (active session):', 'dialout' in [__import__('grp').getgrgid(g).gr_name for g in os.getgroups()])
