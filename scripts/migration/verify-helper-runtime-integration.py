"""Check restored Unpackerr Arr integration and Homepage's normal HTTPS route."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import ssl
import urllib.request

BASE = '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true')
    a = parser.parse_args()
    root = Path(BASE) if a.native else Path(r'\\?\UNC\wsl.localhost\Ubuntu' + BASE.replace('/', '\\'))
    h = root / 'platform-upstream-review-20261027/longhorn-helper-runtime-20261028'
    acceptance = json.loads((h / 'acceptance.json').read_text())
    assert acceptance['status'] == 'same_Homepage_and_Unpackerr_data_on_new_runtime'
    record = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'runtimeAcceptanceSHA256': hashlib.sha256((h / 'acceptance.json').read_bytes()).hexdigest(),
        'clusterMutationPerformed': False, 'browserAcceptance': False}
    if a.native:
        assert os.name == 'posix' and root.is_mount() and os.geteuid() == 1000
        repo = Path(__file__).resolve().parents[2]
        lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'))
        app = next(x for x in acceptance['applications'] if x['identity']['name'] == 'unpackerr')
        pods = lib['get']('pods', namespace='plex')
        pod = next(p for p in pods if p['metadata']['uid'] == app['podUID'])
        status = next(c for c in pod['status']['containerStatuses'] if c['name'] == 'unpackerr')
        assert status['ready'] and status['restartCount'] == 0 and status['imageID'] == app['imageID']
        p = lib['call'](['-n', 'plex', 'exec', pod['metadata']['name'], '-c', 'unpackerr', '--', '/unpackerr', '--version'])
        assert p.returncode == 0
        version = p.stdout.decode()
        assert re.search(r'unpackerr, version 1\.0\.0\s', version)
        p = lib['call'](['-n', 'plex', 'logs', pod['metadata']['name'], '-c', 'unpackerr', '--since=5m', '--tail=1000'])
        assert p.returncode == 0 and len(p.stdout) <= 2 * 1024**2
        logs = p.stdout.decode()
        checks = {'radarrMention': bool(re.search('radarr', logs, re.I)),
            'sonarrMention': bool(re.search('sonarr', logs, re.I)), 'queueRetrievalLines': len(re.findall('Retrieved', logs)),
            'authenticationFailure': bool(re.search(r'unauthorized|invalid api key|HTTP[/ ]\S* 401|status(?: code)?:? 401', logs, re.I)),
            'errorFatalLines': sum(bool(re.search(r'\[(?:ERROR|FATAL)\]', line)) for line in logs.splitlines())}
        logs = version = None
        assert checks['radarrMention'] and checks['sonarrMention'] and checks['queueRetrievalLines'] >= 2
        assert not checks['authenticationFailure'] and checks['errorFatalLines'] == 0
        record.update(status='restored_Unpackerr_Arr_queue_integration_passed', podUID=app['podUID'],
            imageID=app['imageID'], version='1.0.0', integrationChecks=checks,
            limitation='Startup queue retrieval does not prove a new real Arr import or extraction')
        path = h / 'unpackerr-integration.json'
    else:
        assert os.name == 'nt'
        url = 'https://homepage.branconet.lan/'
        with urllib.request.urlopen(url, context=ssl.create_default_context(), timeout=30) as response:
            body = response.read(8 * 1024**2 + 1)
            assert response.status == 200 and response.url == url and 0 < len(body) <= 8 * 1024**2
            record.update(status='restored_Homepage_default_trust_HTTPS_passed', URL=url, HTTPStatus=response.status,
                defaultWindowsCertificateTrust=True, bodyBytes=len(body), bodySHA256=hashlib.sha256(body).hexdigest())
        path = h / 'homepage-https.json'
    with path.open('x') as out:
        json.dump(record, out, indent=2)
    print(json.dumps({'status': record['status'], 'browserAcceptance': False}))


if __name__ == '__main__':
    main()
