"""Append only the missing Minecraft website CNAME through Pi-hole's own CLI."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/longhorn-static-runtime-20261028'
ALIAS = 'mc.branconet.lan,branconet.lan'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def save(name, value):
    with (H / name).open('x') as out:
        json.dump(value, out, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['apply', 'verify'])
    a = parser.parse_args()
    need(os.geteuid() == 1000 and F.is_mount() and H.resolve() == H, 'original_controller_and_owned_output_root')
    need(json.loads((H / 'acceptance.json').read_text())['status'] == 'four_original_sites_on_new_runtime_with_identical_file_hashes',
        'static_runtime_cycle_accepted_before_independent_DNS_fix')
    repo = Path(__file__).resolve().parents[5]
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'))
    dep = lib['get']('deployments', 'pihole', 'pihole')
    selector = dep['spec']['selector']['matchLabels']
    pods = [p for p in lib['get']('pods', namespace='pihole')
        if all(p['metadata'].get('labels', {}).get(k) == v for k, v in selector.items()) and not p['metadata'].get('deletionTimestamp')]
    need(len(pods) == 1 and dep['status'].get('availableReplicas') == 1, 'one_healthy_original_DNS_pod')
    pod = pods[0]
    container = next(c for c in pod['spec']['containers'] if c['name'] == 'pihole')
    need(not any(e['name'] == 'FTLCONF_dns_cnameRecords' for e in container.get('env', [])), 'native_field_not_overridden_by_environment')
    status = next(c for c in pod['status']['containerStatuses'] if c['name'] == 'pihole')
    need(status['ready'], 'original_DNS_container_ready')

    def execute(args):
        p = lib['call'](['-n', 'pihole', 'exec', pod['metadata']['name'], '-c', 'pihole', '--', *args], timeout=30)
        need(p.returncode == 0 and len(p.stdout) <= 65536, 'bounded_native_DNS_command_failed_preserve_intent')
        return p.stdout.decode().strip()

    def aliases():
        text = execute(['pihole-FTL', '--config', 'dns.cnameRecords'])
        need(text.startswith('[ ') and text.endswith(' ]'), 'known_native_CNAME_array_format')
        values = text[2:-2].split(', ') if text[2:-2] else []
        need(len(values) <= 1000 and len(set(values)) == len(values)
            and all(re.fullmatch(r'[a-zA-Z0-9_.-]+,[a-zA-Z0-9_.-]+(?:,[0-9]+)?', v) for v in values),
            'preserve_every_existing_CNAME_without_control_characters')
        return values

    current = aliases()
    identity = {'deploymentUID': dep['metadata']['uid'], 'podUID': pod['metadata']['uid'],
        'containerID': status['containerID'], 'imageID': status['imageID'], 'restartCount': status['restartCount']}
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    intent_path = H / 'website-dns-intent.json'
    if a.mode == 'apply' and not intent_path.exists():
        need(not any(v.split(',')[0] == 'mc.branconet.lan' for v in current), 'missing_alias_only_no_existing_DNS_record_replacement')
        need(execute(['id', '-u']) == '0', 'native_CLI_authorized_container_user')
        save('website-dns-intent.json', {'sourceSHA256': source, 'identity': identity, 'before': current, 'after': current + [ALIAS],
            'generatedProductionState': '/etc/pihole/pihole.toml:dns.cnameRecords (one appended alias)',
            'regeneration': 'Native pihole-FTL --config dns.cnameRecords with preserved prior array plus the single fixed alias',
            'protected': 'All previous DNS records, native Secrets, Pi-hole data, images, Pod and PVC identities',
            'officialConfigurationReference': 'https://docs.pi-hole.net/ftldns/configfile/#cnamerecords'})
        need(aliases() == current, 'fresh_unchanged_native_alias_field_before_write')
        execute(['pihole-FTL', '--config', 'dns.cnameRecords', json.dumps(current + [ALIAS])])
        current = aliases()
    else:
        need(a.mode == 'verify', 'existing_intent_requires_observation_never_automatic_reapply')
    intent = json.loads(intent_path.read_text())
    need(source == intent['sourceSHA256'] and identity == intent['identity']
        and current == intent['after'], 'same_original_DNS_container_and_every_prior_alias_preserved')
    save('website-dns-' + a.mode + '.json', {'status': 'single_website_alias_present_all_original_records_preserved',
        'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'sourceSHA256': source,
        'identity': identity, 'previousAliasesPreserved': len(intent['before']), 'alias': ALIAS,
        'clusterResourceMutations': False, 'nativeSecretChanges': False})
    print(json.dumps({'status': 'single_website_alias_present_all_original_records_preserved', 'alias': ALIAS}))


if __name__ == '__main__':
    main()
