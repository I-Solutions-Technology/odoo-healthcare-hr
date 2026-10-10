#!/usr/bin/env python3
"""PyCharm helper: run scripts/test.sh and print a result summary.

Usage (PyCharm asks for the arguments): <modules comma separated> [test database]
"""
import os
import re
import subprocess
import sys

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:] or [input('Modules to test (comma separated): ').strip()]
modules = args[0]
db = args[1] if len(args) > 1 else 'healthcare_hr_test'
print(f'Testing {modules} on a fresh database "{db}" ...', flush=True)
subprocess.run(['bash', os.path.join(base, 'scripts', 'test.sh'), modules, db], cwd=base)
log = os.path.join(base, 'logs', f'test_{db}.log')
if not os.path.exists(log):
    log = os.path.join(base, 'logs', 'test.log')
if os.path.exists(log):
    lines = open(log, encoding='utf-8', errors='replace').read().splitlines()
    shown = [l for l in lines if re.search(r'(ERROR|CRITICAL|FAIL:| failed, | tests? )', l)]
    print('\n'.join(shown[-40:]) or 'No result line found, see ' + log)
    failed = any(re.search(r' [1-9]\d* failed| [1-9]\d* error', l) for l in shown)
    sys.exit(1 if failed else 0)
