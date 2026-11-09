"""Download the original public task file at the audited revision; verify its hash."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'vendor/PROVENANCE.json').read_text())
    expected = manifest['files']['tasks_original.json']
    output = ROOT / 'vendor/tasks_original.json'
    if output.exists():
        if hashlib.sha256(output.read_bytes()).hexdigest() != expected:
            raise ValueError('Existing task file differs from the audited version; left unchanged')
        print('Existing task file verified.')
        return
    revision = manifest['benchmark_commit']
    url = f'https://raw.githubusercontent.com/stanfordmlgroup/MedAgentBench/{revision}/data/medagentbench/test_data_v2.json'
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Downloaded task file does not match the audited SHA-256')
    json.loads(data)
    output.write_bytes(data)
    print('Downloaded and verified vendor/tasks_original.json (excluded from Git).')


if __name__ == '__main__':
    main()
