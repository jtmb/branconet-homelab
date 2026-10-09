#!/usr/bin/env python3
"""Bounded, independent cold copies using the reviewed per-application gates."""
import concurrent.futures
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHARTS = [
    'media-stack/jackett', 'media-stack/bazarr', 'media-stack/tautulli',
    'media-stack/radarr', 'media-stack/sonarr', 'media-stack/ytdl',
    'apps/xteve', 'media-stack/plex', 'media-stack/unpackerr',
    'apps/pihole', 'apps/minecraft-exporter',
]

def copy(chart):
    name = chart.rsplit('/', 1)[-1]
    evidence = ROOT / 'evidence' / ('copy-' + name + '.json')
    if evidence.exists():
        accepted = json.loads(evidence.read_text())
        if not all(c['manifest_equal'] for c in accepted['copies']):
            return {'chart': chart, 'accepted': False, 'reason': 'Existing copy requires review'}
        return {'chart': chart, 'accepted': True, 'existing': True}
    result = subprocess.run([sys.executable, str(ROOT/'scripts/migration/copy-application-data.py'), '--chart', chart], capture_output=True, text=True)
    # Tool errors have no source env/secret values; never emit raw application logs.
    report = {'chart': chart, 'accepted': result.returncode == 0, 'exit': result.returncode}
    if result.returncode:
        report['diagnostic'] = result.stderr[-2500:]
    print(json.dumps(report), flush=True)
    return report

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(copy, CHARTS))
    (ROOT/'evidence/application-copy-wave.json').write_text(json.dumps(results, indent=2)+'\n')
    raise SystemExit(0 if all(r['accepted'] for r in results) else 1)
