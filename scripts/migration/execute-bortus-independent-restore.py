"""Run the approved separate-volume BORTUS recovery check using existing credentials."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).parent
ANCHOR=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery')
RUNTIME=Path('/home/brajam/.local/share/branconet-migration')
IMAGE='docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
# Reviewed descendant changes only Ingenium replicaCount 1 to 0; BORTUS guards remain pinned below.
COMMIT='44420b74ff814af7b15eb6442d5464a15b53c823'
RUN='da37c4f713e8'
JOURNAL=ANCHOR/'recovery/bortus-checkpoints'/RUN/'journal.json'
JOURNAL_SHA='19736598e98c98f481d2f974a23e98af366b92b5354954cfae50aa034276ba88'
GUARDS=ANCHOR/('guard-probes-'+RUN+'-publication-settle')/'record.json'
PROOF=ANCHOR/'qualified-node-imports.json'

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/filename)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def need(value):
    if not value:raise RuntimeError('restore_current_qualification_failed')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore',action='store_true')
    parser.add_argument('--diagnose-health',action='store_true')
    parser.add_argument('--after-longhorn-profile',action='store_true')
    parser.add_argument('--after-tool-path',action='store_true')
    args=parser.parse_args()
    restore=load('current_independent_restore','bortus-independent-restore.py')
    guard=load('current_restore_guard','bortus-admission-operator.py')
    options=restore.reader.credentials.OperatorMTLSOptions(str(RUNTIME/'admin.conf'))
    guard_options=load('current_restore_guard_credentials','bortus-operator-mtls.py').OperatorMTLSOptions(str(RUNTIME/'admin.conf'))
    guard_api=guard.API(guard_options)
    schema=load('release_current_schema_producer','schema-current-writer-v1/current-schema-producer.py')
    schema_api=schema.VerifiedAPI(options)
    schema_inputs=RUNTIME/'schema-current-writer-66f5c84fa205'
    runtime_verifier=load('release_current_runtime_verifier','verify-bortus-current-node-image.py')
    deadline=time.monotonic()+295
    proof_raw=PROOF.read_bytes();proof=json.loads(proof_raw)
    admission_raw=GUARDS.read_bytes();admission=json.loads(admission_raw)
    reconciled=json.loads(GUARDS.with_name('completion-reconciliation.json').read_bytes())
    need(reconciled['state']=='completed' and reconciled['owned_fixtures_absent'] is True and reconciled['actual_guard_probe_evidence_validated'] is True
         and reconciled['original_record_sha256']==hashlib.sha256(admission_raw).hexdigest() and len(admission['outcomes'])==42)
    qualification_sha=hashlib.sha256(proof_raw).hexdigest()
    admission_sha=hashlib.sha256(admission_raw).hexdigest()
    publication=admission['binding']['publication']
    def get(kind,name=None,namespace=None):
        command=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf'),'--request-timeout=15s','get',kind]
        if name:command.append(name)
        if namespace:command.extend(['-n',namespace])
        command.extend(['-o','json'])
        result=subprocess.run(command,capture_output=True,timeout=min(20,deadline-time.monotonic()))
        need(result.returncode==0 and len(result.stdout)<=8*1024**2)
        return json.loads(result.stdout)
    def qualification(image,target,until):
        need(time.monotonic()<until and image==IMAGE and target=='bortus-restore-'+RUN
             and PROOF.read_bytes()==proof_raw and GUARDS.read_bytes()==admission_raw)
        schema_before=schema.collect(ANCHOR,schema_inputs/'schema-reader.cjs',schema_inputs/'migration-manifest.json',until,time.monotonic_ns(),schema_api.get)
        current_runtime=runtime_verifier.verify(until)
        need(proof['image']==image and len(proof['nodes'])==3)
        nodes=get('nodes')['items'];byname={n['metadata']['name']:n for n in nodes}
        names=sorted(n['node'] for n in proof['nodes']);need(names==['node01','node02','node03'])
        for name in names:
            node=byname[name]
            need(not node['metadata'].get('deletionTimestamp') and
                 any(c['type']=='Ready' and c['status']=='True' for c in node['status']['conditions']) and
                 not any(c['type']=='DiskPressure' and c['status']=='True' for c in node['status']['conditions']) and
                 any(image in entry['names'] for entry in node['status']['images']))
        engine=get('settings.longhorn.io','default-engine-image','longhorn-system')
        need(engine['value']==restore.health.ENGINE_PROFILES['1.13.0'])
        for pin in publication['guard_pins']:
            obj=guard_api.guard(pin['kind'],pin['name'],deadline=until)
            need(obj['metadata']['uid']==pin['uid'] and
                 hashlib.sha256(guard.validator.canonical_spec(pin['kind'],obj['spec'])).hexdigest()==pin['spec_sha256'])
        for kind,name in [('gitrepository','branconet-charts'),('kustomization','migration-releases')]:
            obj=get(kind,name,'flux-system')
            revision=obj['status']['artifact']['revision'] if kind=='gitrepository' else obj['status']['lastAppliedRevision']
            need(revision=='validated@sha1:'+COMMIT)
        schema_after=schema.collect(ANCHOR,schema_inputs/'schema-reader.cjs',schema_inputs/'migration-manifest.json',until,time.monotonic_ns(),schema_api.get)
        need(schema_before['sha256']!=schema_after['sha256'] and schema_before['receipt']['writer']==schema_after['receipt']['writer'])
        observation={'current_validation':True,'current_chart_revision':COMMIT,'actual_schema_before':schema_before,'actual_schema_after':schema_after,'actual_runtime_observation':current_runtime,'qualification_sha256':qualification_sha,'admission_sha256':admission_sha,'production_changed':False}
        fd=os.open(ANCHOR/('qualification-observation-'+uuid.uuid4().hex[:12]+'.json'),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(observation,stream);stream.flush();os.fsync(stream.fileno())
        return {'holder_image':image,'source_commit':proof['source_commit'],'config_image_id':proof['config_digest'],
                'node_names':names,'protected_claim_names':['bortus-data',target],
                'qualification_receipt_sha256':qualification_sha,'admission_receipt_sha256':admission_sha,'current_validation':True}
    qualification(IMAGE,'bortus-restore-'+RUN,deadline)
    if args.diagnose_health:
        api=restore.reader.metadata.MetadataAPI(options)
        run=ANCHOR/('independent-restore-'+RUN)
        created=json.loads((run/'journal.json').read_bytes())['operations']
        original=json.loads(JOURNAL.read_bytes())['baseline']['identities']
        target='bortus-restore-'+RUN
        claim=api.get('claim',target,deadline=deadline)
        pv=api.get('pv',claim['spec']['volumeName'],deadline=deadline)
        volume=api.get('volume',pv['spec']['csi']['volumeHandle'],deadline=deadline)
        backup=api.get('backup','backup-'+RUN,deadline=deadline)
        node=api.get('node','node02',deadline=deadline)
        select=lambda obj:{k:obj.get(k) for k in ('name','uid','namespace')}
        expected={'original_claim':select(original['claim']),'original_pv':select(original['pv']),
          'original_volume':select(original['longhorn_volume']),'claim':select(created['claim_create']['identity']),
          'pv':select(pv['metadata']),'volume':select(volume['metadata']),'backup':select(backup['metadata']),
          'holder':select(created['holder_create']['identity']),'holder_image':IMAGE,'original_node':'node01',
          'node':select(node['metadata']),'longhorn_version':restore.health.CURRENT_LONGHORN_VERSION,'backup_url':backup['status']['url']}
        objects={'claim':claim,'pv':pv,'volume':volume,'backup':backup,'node':node}
        for key,resource in [('pvs','pv'),('pods','pod'),('engines','engine'),('replicas','replica')]:
            objects[key]=api.list(resource,deadline=deadline)
        try:
            result=restore.health.evaluate(expected,objects)
            print(json.dumps({'restored_consumer_health':True,'replicas':len(result.replicas)}))
        except Exception as error:
            frames=[];tb=error.__traceback__
            while tb:frames.append(Path(tb.tb_frame.f_code.co_filename).name+':'+str(tb.tb_lineno));tb=tb.tb_next
            print(json.dumps({'restored_consumer_health':False,'code':getattr(error,'code',None),'locations':frames}))
        return
    if not args.restore:

        print(json.dumps({'current_restore_qualification_passed':True,'nodes':3,'actual_guard_cases':42,'mutations':0}));return
    journal=json.loads(JOURNAL.read_bytes())
    folder=ANCHOR/('independent-restore-'+RUN)
    if args.after_tool_path:
        folder=folder.with_name(folder.name+'-lh113')
    if args.after_longhorn_profile or args.after_tool_path:
        retired=json.loads((folder/'version-rehearsal-retirement.json').read_bytes())
        need(retired['state']=='completed' and len(retired['removed'])==5 and retired['original_resources_changed'] is False)
        folder=folder.with_name(folder.name+('-h-tool' if args.after_tool_path else '-lh113'))
    result=restore.restore(folder,JOURNAL,JOURNAL_SHA,
        Path(journal['sqlite_archive']['artifact']),IMAGE,'node02',str(RUNTIME/'admin.conf'),options,qualification,
        age=RUNTIME/'bin/age',recipient_file=Path('/home/brajam/.ssh/id_ed25519.pub'),
        identity_file=Path('/home/brajam/.ssh/id_ed25519'),deadline=deadline)
    print(json.dumps({'independent_restore':result._asdict(),'production_application_changed':False}))

if __name__=='__main__':
    try:main()
    except Exception as error:
        frames=[];tb=error.__traceback__
        while tb:frames.append(Path(tb.tb_frame.f_code.co_filename).name+':'+str(tb.tb_lineno));tb=tb.tb_next
        print(json.dumps({'restore_failed':type(error).__name__,'code':getattr(error,'code',None),'locations':frames}),file=sys.stderr)
        raise SystemExit(1)

