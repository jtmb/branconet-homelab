"""Reconcile the original cache ledger against the final read-only projection.

No cluster writes, cache removal or refused-target retries. Original failed
journals remain authoritative; observed absence is not a remove acknowledgement.
"""
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'platform-upstream-review-20261027/longhorn-application-batch-20261028/native-cache-qualification'


def main():
    names = ['qualify-79a2a109481a4c47adb9fc99b57ac4af.json',
             'qualify-ddad8659bcfd4d98b6ed7a4ebb88ae12.json',
             'physical-85906da803ac465c8f20b0e306c71968.json',
             'retire-output-4a0cc2198ea44ff7a0c5034a2efb2ccf.jsonl',
             'retire-b7645c8b01344006ad9ccf0c2824faa4.json']
    raw = {n: (OUT / n).read_bytes() for n in names}
    first, second, final = [json.loads(raw[n]) for n in names[:3]]
    journal = [json.loads(line) for line in raw[names[3]].splitlines()]
    completed = json.loads(raw[names[4]])
    original = first['profile']
    candidates = original['mappedCandidates']
    target_ids = {x['id'] for x in candidates}
    assert len(candidates) == len(target_ids) == 71
    assert not final['orphanDirectories'] and not final['mappedCandidates']
    assert set(final['allBackendIDs']) == set(original['allBackendIDs']) - target_ids
    assert original['nativeInventory']['imageRecordsSHA256'] == final['nativeInventory']['imageRecordsSHA256']
    assert original['nativeInventory']['containers'] == final['nativeInventory']['containers']
    assert original['nativeInventory']['leases'] == final['nativeInventory']['leases']
    assert first['verifiedOriginalBlobs'] == second['verifiedOriginalBlobs']
    assert len(first['verifiedOriginalBlobs']) == 95
    assert completed['status'] == 'qualified_cache_paths_absent_images_and_original_payloads_preserved'
    # The initial incomplete journal ends at NotFound; never reinterpret it as
    # an entirely successful operation or resubmit that key.
    events = {}
    for row in journal:
        event = row.get('status', 'remove_acknowledged' if row.get('nativeRemoveCompleted') else 'remove_intent')
        events[event] = events.get(event, 0) + 1
    assert events['remove_acknowledged'] == 32 and events['native_remove_failed_no_retry'] == 1
    assert {row['intent'] for row in journal if 'intent' in row}.isdisjoint(
        {row['key'] for row in completed['directNativeRemoveAcknowledgements']})
    value = {'status': 'original_71_cache_paths_absent_all_other_backend_ids_preserved',
        'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'inputs': {n: hashlib.sha256(v).hexdigest() for n, v in raw.items()},
        'originalAllocatedLinuxBytes': sum(x['allocatedBytes'] for x in candidates),
        'originalPathLedger': [{k: x[k] for k in ('key', 'path', 'allocatedBytes')} for x in candidates],
        'originalBackendCount': original['backendSnapshotCount'], 'finalBackendCount': final['backendSnapshotCount'],
        'otherBackendIDsPreserved': True, 'orphanDirectories': [],
        'initialJournalEventCounts': events, 'initialOperationCompleted': False,
        'secondOperationDirectAcknowledgements': len(completed['directNativeRemoveAcknowledgements']),
        'totalDirectAcknowledgements': 39, 'otherQualifiedPathsObservedAbsent': 32,
        'original95BlobsVerifiedBeforeAndAfter': True, 'imageRecordsContainersLeasesUnchanged': True,
        'failedKeyNotRetried': 'sha256:c7b875d3de914680ec64ba55be5865955ec595e7370812894ee68a502e2e8391',
        'windowsRecoveryClaimed': False, 'dataVolumesChanged': False, 'fullGoalComplete': False}
    assert value['originalAllocatedLinuxBytes'] == 3004600320
    with (OUT / 'reconciliation.json').open('x') as stream:
        json.dump(value, stream, indent=2)
    print(json.dumps({k: v for k, v in value.items() if k not in ('originalPathLedger', 'inputs')}))


if __name__ == '__main__':
    main()
