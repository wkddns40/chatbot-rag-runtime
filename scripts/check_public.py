"""Publication guard for staged/tracked files; values are never printed."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
patterns = [
    rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
    rb'gh[pousr]_[A-Za-z0-9]{20,}', rb'github_pat_[A-Za-z0-9_]{20,}',
    rb'\b192\.168\.\d+\.\d+\b', rb'\b10\.\d+\.\d+\.\d+\b',
    rb'\b172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+\b',
]
failures = []
for name in filter(None,paths):
    path = root/name
    if name=='.env' or name.endswith(('.pem','.key','.pfx','.docx','.sqlite','.dump')):
        failures.append(name)
    if path.suffix in {'.png','.webp'}:
        continue
    data = path.read_bytes()
    if any(re.search(pattern,data) for pattern in patterns):
        failures.append(name)
    if (root/'.env').exists():
        for line in (root/'.env').read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key,value=line.split('=',1)
                if ('TOKEN' in key or 'PASSWORD' in key or 'KEY' in key) and len(value)>12 and value.encode() in data:
                    failures.append(name)
assert not failures, 'Publication guard failed in: '+', '.join(sorted(set(failures)))
print(f'PASS: {len(list(filter(None,paths)))} publication files; no local credentials or private IP literals detected.')
