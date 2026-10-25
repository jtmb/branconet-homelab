"""Authenticate one original cold network-table projection; never change app data."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import re


def archived_network(state, cold):
    """Only authenticated pages, sparse tmpfs; no whole DB copy or parser replacement."""
    state.need(cold['archive_sha256'] == 'ee490a2b19a2a8a302d72f82cde05fd7c3fad288159168c54a36ba49c48e1289', 'exact_network_projection_archive')
    state.need(any(x.split()[1:3] == ['/dev/shm', 'tmpfs'] for x in Path('/proc/mounts').read_text().splitlines()), 'native_tmpfs_projection')
    archive = Path(cold['archive_path'])
    state.need(state.sha(archive) == cold['archive_sha256'], 'original_ciphertext_identity')
    child = subprocess.Popen([str(state.shared.AGE), '-d', '-i', str(state.shared.IDENTITY), str(archive)],
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        with tempfile.TemporaryDirectory(prefix='pihole-network-pages-', dir='/dev/shm') as folder:
            target = Path(folder) / 'projection.db'
            manifest = None
            seen = set()
            total = 0
            with tarfile.open(fileobj=child.stdout, mode='r|') as bundle:
                for member in bundle:
                    state.need(member.name not in seen and len(seen) <= 4096, 'unique_bounded_archive_members')
                    seen.add(member.name)
                    if member.name == 'manifest.json':
                        state.need(len(seen) == 1 and member.isfile() and member.size <= 8 * 1024 ** 2, 'first_archive_manifest')
                        manifest = json.load(bundle.extractfile(member))
                        state.need(hashlib.sha256(state.shared.canonical(manifest)).hexdigest() == cold['manifest_sha256'], 'original_complete_manifest')
                        continue
                    state.need(manifest is not None and member.name in manifest['entries'], 'original_archive_member')
                    row = manifest['entries'][member.name]
                    state.need(member.mode == row['mode'] and member.uid == row['uid'] and member.gid == row['gid'], 'original_archive_metadata')
                    if row['kind'] == 'file':
                        state.need(member.isfile() and member.size == row['bytes'], 'original_file_size')
                        digest = hashlib.sha256()
                        count = 0
                        stream = bundle.extractfile(member)
                        output = target.open('xb') if member.name == 'data-1/pihole-FTL.db' else None
                        try:
                            for block in iter(lambda: stream.read(1024 ** 2), b''):
                                if output:
                                    # Exact authenticated DB: its schema root is page1,
                                    # sole schema child8130; both network roots8/12 are
                                    # in the first MiB. All other pages stay sparse holes.
                                    if count < 1024 ** 2:
                                        output.seek(count)
                                        output.write(block[:1024 ** 2 - count])
                                    lo, hi = max(count, 8129 * 4096), min(count + len(block), 8130 * 4096)
                                    if lo < hi:
                                        output.seek(lo)
                                        output.write(block[lo - count:hi - count])
                                digest.update(block)
                                count += len(block)
                            state.need(count == member.size and digest.hexdigest() == row['sha256'], 'complete_original_file_hash')
                            total += count
                            state.need(total <= 4 * 1024 ** 3, 'original_archive_data_bound')
                            if output:
                                output.truncate(member.size)
                        finally:
                            if output:
                                output.close()
                    elif row['kind'] == 'directory':
                        state.need(member.isdir(), 'original_directory')
                    else:
                        state.need(row['kind'] == 'symlink' and member.issym() and member.linkname == row['link'], 'original_symlink')
            state.need(seen == {'manifest.json'} | set(manifest['entries']) and total == manifest['total_file_bytes'], 'complete_archive_members')
            tail = child.stdout.read(1024 ** 2 + 1)
            state.need(len(tail) <= 1024 ** 2 and not any(tail) and child.wait(timeout=30) == 0, 'authenticated_archive_eof')
            state.need(target.stat().st_blocks * 512 <= 16 * 1024 ** 2, 'sparse_projection_allocation')
            with target.open('rb') as stream:
                header = stream.read(4096)
            state.need(header[:16] == b'SQLite format 3\0' and int.from_bytes(header[16:18], 'big') == 4096
                       and header[100] == 5 and int.from_bytes(header[103:105], 'big') == 0
                       and int.from_bytes(header[108:112], 'big') == 8130, 'exact_schema_page_layout')
            connection = sqlite3.connect('file:' + str(target) + '?mode=ro', uri=True)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute('PRAGMA query_only=ON')
                connection.execute('PRAGMA cache_size=-1024')
                roots = dict(connection.execute("SELECT name,rootpage FROM sqlite_master WHERE name IN ('network','network_addresses')"))
                state.need(roots == {'network': 8, 'network_addresses': 12}, 'original_network_page_roots')
                # HEX retains even existing invalid UTF-8 vendor bytes, without
                # silently normalizing historical fields or exposing values.
                network = [dict(r) for r in connection.execute('SELECT id,hex(hwaddr) hwaddr,hex(interface) interface,firstSeen,lastQuery,numQueries,hex(macVendor) macVendor,aliasclient_id FROM network')]
                addresses = [dict(r) for r in connection.execute('SELECT network_id,hex(ip) ip,lastSeen,CASE WHEN name IS NULL THEN NULL ELSE hex(name) END name,nameUpdated FROM network_addresses')]
                state.need(len(network) == 10 and len(addresses) == 12, 'exact_original_small_network_tables')
                state.need(state.sha(archive) == cold['archive_sha256'], 'ciphertext_retained_after_projection')
                return network, addresses, {'materializedBytes': target.stat().st_blocks * 512, 'wholeDatabaseCopyClaimed': False,
                                            'fullArchiveAuthenticated': True, 'unrequestedPagesAreSparseHoles': True}
            finally:
                connection.close()
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)


def prove_replacement(state, cold, baseline, previous, snapshots, execute, key):
    state.need(baseline['snapshots']['pihole-FTL.db']['tables']['session']['count'] == 0, 'authenticated_original_baseline_had_no_sessions')
    old, old_addresses, projection = archived_network(state, cold)
    literal, digest = state.sql.lit, state.sql.digest_query
    native_key = digest(literal('SELECT network_id,ip FROM network_addresses WHERE ip=') + '||quote(ip)')
    native_ip = digest(literal('SELECT ip FROM network_addresses WHERE ip=') + '||quote(ip)')
    native_name = digest(literal('SELECT name FROM network_addresses WHERE ip=') + '||quote(ip)')
    native_stable = digest(literal('SELECT id,hwaddr,interface,firstSeen,macVendor,aliasclient_id FROM network WHERE id=') + '||CAST(id AS TEXT)')
    query = "SELECT json_object('network',json((SELECT json_group_array(json_object('id',id,'hwaddr',hex(hwaddr),'interface',hex(interface),'firstSeen',firstSeen,'lastQuery',lastQuery,'numQueries',numQueries,'aliasclient_id',aliasclient_id,'stable_digest'," + native_stable + ")) FROM network)), 'addresses',json((SELECT json_group_array(json_object('network_id',network_id,'ip',hex(ip),'lastSeen',lastSeen,'name',CASE WHEN name IS NULL THEN NULL ELSE hex(name) END,'nameUpdated',nameUpdated,'key_digest'," + native_key + ",'ip_digest'," + native_ip + ",'name_digest'," + native_name + ")) FROM network_addresses))) AS network_observation;"
    raw = execute(['timeout', '-s', 'KILL', '30', '/sql/pihole-sql', 'sqlite3', '-readonly', '-bail', '-batch', '-json', '-init', '/dev/null', '/sql/pihole-FTL.db'], query.encode(), timeout=45)
    current = json.loads(json.loads(raw)[0]['network_observation'])
    state.need(len(current['network']) <= 1000 and len(current['addresses']) <= 2000, 'bounded_network_bookkeeping')
    now = {r['id']: r for r in current['network']}
    addresses = {r['ip']: r for r in current['addresses']}
    missing = [r for r in old if r['id'] not in now]
    state.need([r['id'] for r in missing] == [2], 'one_specific_original_mock_replacement')
    original = missing[0]
    old_ip = [r for r in old_addresses if r['network_id'] == 2]
    state.need(len(old_ip) == 1 and original['aliasclient_id'] is None, 'unconfigured_single_address_mock')
    old_ip = old_ip[0]
    state.need(bytes.fromhex(original['hwaddr']) == b'ip-' + bytes.fromhex(old_ip['ip']), 'original_mock_matches_exact_address')
    state.need(all(r['ip'] in addresses for r in old_addresses), 'all_original_network_addresses_still_present')
    current_ip = addresses[old_ip['ip']]
    replacement = now[current_ip['network_id']]
    state.need(replacement['id'] == 11 and re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', bytes.fromhex(replacement['hwaddr']).decode('ascii'))
               and replacement['aliasclient_id'] is None and replacement['interface'] == original['interface'], 'exact_real_hardware_replacement')
    state.need(replacement['firstSeen'] <= original['firstSeen'] and replacement['lastQuery'] >= original['lastQuery']
               and replacement['numQueries'] >= original['numQueries'], 'replacement_preserves_earliest_seen_and_counters')
    state.need(current_ip['name'] == old_ip['name'] and current_ip['lastSeen'] >= old_ip['lastSeen']
               and (old_ip['nameUpdated'] is None or current_ip['nameUpdated'] >= old_ip['nameUpdated']), 'same_address_name_and_monotonic_clocks')
    def wrapped(value):
        return state.mac(key, ['sqlite-native-digest', 'pihole-FTL.db'], value)
    snap = snapshots['pihole-FTL.db']
    native_rows = {r['id']: r for r in snap['network_rows']}
    address_rows = {r['key_digest']: r for r in snap['address_rows']}
    state.need(native_rows[11]['stable_digest'] == wrapped(replacement['stable_digest']), 'same_measured_replacement_hardware')
    new_address_key = wrapped(current_ip['key_digest'])
    measured = address_rows[new_address_key]
    state.need(measured['network_id'] == 11 and measured['ip_digest'] == wrapped(current_ip['ip_digest'])
               and measured['name_digest'] == wrapped(current_ip['name_digest']), 'same_measured_address_mapping_and_name')
    all_ips = [wrapped(addresses[r['ip']]['ip_digest']) for r in old_addresses]
    state.need(set(all_ips) <= {r['ip_digest'] for r in snap['address_rows']}, 'all_original_ips_in_same_sql_capture')
    mappings = {}
    for label, prior in [('baseline', baseline), ('previous', previous)]:
        if prior is None:
            continue
        data = prior['snapshots']['pihole-FTL.db']
        state.need({r['id'] for r in data['network_rows']} - set(native_rows) == {2}, 'only_measured_mock_id_removed')
        absent = {r['key_digest'] for r in data['address_rows']} - set(address_rows)
        state.need(len(absent) == 1, 'only_single_address_network_id_changed')
        mappings[label] = {next(iter(absent)): new_address_key}
    return {'networkReplacements': {'2': 11}, 'addressReplacements': mappings,
            'originalMockMetadataHMAC': state.mac(key, 'archived-network-mock', original),
            'all12OriginalIPsVerified': True, 'originalConfiguredAliasWasAbsent': True,
            'sameAddressNameVerified': True, 'projection': projection,
            'sourceCommit': '29c8b13f4bba0c4f4f47598e45a65cbf1cedac88',
            'networkSourceSHA256': 'b4a313cfe9af454eb8a71c7233953f9a6a57731f27c72672d3a8791430dac275',
            'sourceBehavior': 'ARP discovery replaces an unconfigured ip-address mock with real hardware; unassigned mock is deleted',
            'removedMockStillArchived': True, 'wholeNetworkRowEquivalenceClaimed': False}
