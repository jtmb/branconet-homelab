"""Public disposable age/raw-byte orchestration. All API/SSH/etcd calls mocked."""
import base64,copy,hashlib,importlib.util,json,os,pathlib,shlex,shutil,subprocess,sys,tempfile,time,unittest
from unittest import mock
HERE=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('etcd_checkpoint',HERE.parent/'backup-etcd.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Client:
    def __init__(self,test):
        self.t=test;self.deadline=test.deadline;self.children=m.q.Children(self.deadline);self.jobs=[];self.calls=[];self.objects={};self.restoring=False;self.mode='normal';self.nas_mode=0o600;self.nas_cifs=False;self.nas_bad_field=None
    def spawn(self,args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,pass_fds=()):
        self.calls.append(('spawn',list(args)))
        if self.mode=='tamper-cipher'and '-d'in args and (self.t.parent/('etcd-'+self.t.run_id)/'snapshot.age').exists():
            p=self.t.parent/('etcd-'+self.t.run_id)/'snapshot.age'
            with p.open('r+b')as f:f.seek(-1,2);b=f.read(1);f.seek(-1,2);f.write(bytes([b[0]^1]));f.flush();os.fsync(f.fileno())
            self.mode='normal'
        if args[0]==str(m.SSH_BINARY):
            tokens=shlex.split(args[-1]);self.t.assertEqual(['python3','-c'],tokens[:2]);expected,binding=m.nas_writer();self.t.assertEqual(expected,tokens[2]);disk=json.loads((self.t.parent/('etcd-'+self.t.run_id)/'record.json').read_text());self.t.assertEqual('pending',disk['operations']['nas']['state']);self.t.assertEqual(binding,disk['operations']['nas']['details']['writer_binding'])
            code=tokens[2].replace(repr(m.q.NAS_ROOT),repr(str(self.t.nas)))
            if self.nas_cifs:code=code.replace('try:\n mount_before=mount_identity()',"def mount_identity():return ('/mnt/container-backups',('PUBLIC PIN',),('cifs','PUBLIC SOURCE','rw'))\ntry:\n mount_before=mount_identity()")
            if self.nas_mode!=0o600:
                needle=" digest=hashlib.sha256();left=info['bytes']";self.t.assertEqual(1,code.count(needle));code=code.replace(needle,' os.fchmod(target,'+str(self.nas_mode)+')\n'+needle)
            if self.nas_bad_field:
                key,value=self.nas_bad_field;needle=" print(json.dumps({'bytes':info['bytes']";self.t.assertEqual(1,code.count(needle));code=code.replace(needle," result="+repr({'bytes':None,'sha256':None,'fsynced':True,'same_inode_readback':True,'cipher_mode':self.nas_mode,'cifs_mount':self.nas_cifs})+";result.update(bytes=info['bytes'],sha256=digest.hexdigest());result["+repr(key)+"]="+repr(value)+";print(json.dumps(result));raise SystemExit(0)\n"+needle)
            args=[sys.executable,'-B','-c',code]
        p=subprocess.Popen(args,stdin=stdin,stdout=stdout,stderr=subprocess.DEVNULL,start_new_session=True,pass_fds=pass_fds)
        self.jobs.append({'pid':p.pid,'start_ticks':pathlib.Path('/proc/'+str(p.pid)+'/stat').read_text().split()[21],'process':p});return p
    def remote_start(self,r):
        self.calls.append(('remote-start',copy.deepcopy(r)))
        if r['mode']=='read':
            code='import sys,base64;sys.stdin.buffer.read();sys.stdout.buffer.write(base64.b64decode('+repr(base64.b64encode(self.t.raw).decode())+'))'
        elif r['mode']=='receive':
            self.t.assertEqual(len(self.t.raw),r['bytes'])
            code="import sys,json,hashlib,pathlib;line=sys.stdin.buffer.readline(1025);header=json.loads(line);data=sys.stdin.buffer.read();assert set(header)=={'abi','mode','run_id','bytes','sha256'} and header['abi']==1 and header['mode']=='receive' and header['bytes']==len(data) and header['sha256']==hashlib.sha256(data).hexdigest();p=pathlib.Path("+repr(str(self.t.proof))+ ");p.write_bytes(data);p.chmod(0o600);i=p.stat();print(json.dumps({'inode':[i.st_dev,i.st_ino,i.st_size,i.st_mtime_ns,i.st_ctime_ns],'bytes':len(data),'digest':hashlib.sha256(data).hexdigest()}))"
        else:raise AssertionError('Unexpected source')
        return self.spawn([sys.executable,'-B','-c',code])
    def remote(self,r):
        self.calls.append(('remote',copy.deepcopy(r)))
        if r['mode']=='keys':
            result=copy.deepcopy(self.t.document['files'])
            if self.mode=='keys-drift':result['/etc/kubernetes/longhorn-crypto-key']=base64.b64encode(b'DRIFT').decode()
            return result
        if r['mode']=='directory':return {'created':True}
        if r['mode']=='metadata':return {'inode':[1,2,len(self.t.raw),3,4],'bytes':len(self.t.raw),'digest':m.sha(self.t.raw)}
        if r['mode']in('proof','unlink'):
            i=self.t.proof.stat();out={'inode':[i.st_dev,i.st_ino,i.st_size,i.st_mtime_ns,i.st_ctime_ns],'bytes':i.st_size,'digest':m.sha(self.t.proof.read_bytes())};self.t.assertEqual(out['inode'],r['inode'])
            if r['mode']=='unlink':self.t.proof.unlink()
            return out
        raise AssertionError('Unexpected remote operation')
    def api(self,args,body=None,maximum=None):
        self.calls.append(('api',list(args),copy.deepcopy(body)))
        if args[:3]==['get','pod','etcd-masternode']:
            uid='original-etcd'if self.mode!='source-drift'else'foreign-etcd'
            return {'metadata':{'name':'etcd-masternode','namespace':'kube-system','uid':uid,'resourceVersion':'a'},'spec':{'nodeName':'masternode','containers':[{'name':'etcd','image':self.t.source['image']}]},'status':{'containerStatuses':[{'name':'etcd','ready':True,'imageID':self.t.source['image_id']}]}}
        if args[:3]==['get','secret','longhorn-crypto']:
            return {'metadata':{'name':'longhorn-crypto','namespace':'longhorn-system','uid':'original-key','resourceVersion':'b'},'data':{'CRYPTO_KEY_VALUE':self.t.document['files']['/etc/kubernetes/longhorn-crypto-key']}}
        if args[0]=='create':
            kind='pod'if body['kind']=='Pod'else'networkpolicy';obj=copy.deepcopy(body);obj['metadata'].update(uid=kind+'-owned',resourceVersion='created');self.objects[kind]=obj
            if kind=='pod'and self.mode=='api-defaults':
                obj['spec']['tolerations']=[{'key':'node.kubernetes.io/not-ready','operator':'Exists','effect':'NoExecute','tolerationSeconds':300},{'key':'node.kubernetes.io/unreachable','operator':'Exists','effect':'NoExecute','tolerationSeconds':300}]
                obj['spec']['containers'][0].update(terminationMessagePath='/dev/termination-log',terminationMessagePolicy='File')
            if kind=='pod'and self.mode=='lost-create':raise m.Refused('child')
            return copy.deepcopy(obj)
        if args[:2]==['delete','--raw']:
            kind='pod'if '/pods/'in args[2]else'networkpolicy';obj=self.objects[kind];self.t.assertEqual(body['preconditions'],{k:obj['metadata'][k]for k in('uid','resourceVersion')})
            disk=json.loads((self.t.parent/('etcd-'+self.t.run_id)/'record.json').read_text());self.t.assertEqual('pending',disk['operations'][kind+'-delete']['state'])
            if self.mode=='lost-delete'and kind=='pod':raise m.Refused('child')
            self.objects.pop(kind);return {'kind':'Status','status':'Success'}
        if args[:2]==['get','--raw']:
            self.t.assertIn(args[2],('/api/v1/namespaces/migration-system/pods','/apis/networking.k8s.io/v1/namespaces/migration-system/networkpolicies'));kind='pod'if args[2].endswith('/pods')else'networkpolicy';args=['get',kind,'-n',m.NS]
        if args[0]=='get':
            kind=args[1]
            if len(args)>2 and args[2]!='-n':
                obj=copy.deepcopy(self.objects.get(kind))
                if obj and kind=='pod':obj['status']={'containerStatuses':[{'name':'etcd','ready':True,'state':{'running':{}},'imageID':self.t.source['restore_image']}]}
                return obj
            meta={'resourceVersion':'opaque-a','continue':'','remainingItemCount':0}
            if self.mode=='incomplete-list':meta['continue']='next'
            return {'apiVersion':'v1'if kind=='pod'else'networking.k8s.io/v1','kind':'PodList'if kind=='pod'else'NetworkPolicyList','metadata':meta,'items':list(copy.deepcopy(self.objects).values())if kind in self.objects else[]}
        raise AssertionError('Unexpected API operation')
    def kube(self,args,body=b'',maximum=65536,stream=False):
        self.calls.append(('kube',list(args)))
        if stream:return self.spawn([sys.executable,'-B','-c','import time;time.sleep(30)'],stdout=subprocess.DEVNULL)
        if args[0]=='wait':return b''
        if 'snapshot'in args and 'status'in args:return json.dumps(self.t.status).encode()
        if 'snapshot'in args and 'restore'in args:self.t.assertNotIn('--skip-hash-check',args);self.t.assertEqual(self.t.raw,self.t.proof.read_bytes());self.restoring=True;return b''
        if '/registry/secrets/'in args:
            if not self.restoring:self.t.assertIn('--rev=7',args)
            obj=copy.deepcopy(self.t.registry)
            if self.restoring and self.mode=='extra-record':obj['kvs'].append({'key':base64.b64encode(b'/registry/secrets/extra/name').decode(),'value':base64.b64encode(b'EXTRA').decode()});obj['count']=3
            return json.dumps(obj).encode()
        return b''
    def close(self):
        for job in self.jobs:
            if 'process'not in job:continue
            p=job['process'];self.children(p)
            for f in(p.stdin,p.stdout,p.stderr):
                if f and not f.closed:f.close()
            job.update(actual_exit_code=p.poll(),reaped=p.poll()is not None);job.pop('process')


class Tests(unittest.TestCase):
    def setUp(self):
        base=HERE/'public-etcd-fixtures';base.mkdir(mode=0o700,exist_ok=True);self.root=pathlib.Path(tempfile.mkdtemp(dir=base));self.root.chmod(0o700)
        self.runtime=self.root/'runtime';(self.runtime/'bin').mkdir(parents=True);age=pathlib.Path.home()/'.local/share/branconet-migration/bin/age';shutil.copyfile(age,self.runtime/'bin/age');(self.runtime/'bin/age').chmod(0o700)
        self.private=self.root/'keys';self.private.mkdir(mode=0o700);self.identity=self.private/'id';subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.identity)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5);self.recipient=pathlib.Path(str(self.identity)+'.pub');self.recipient.chmod(0o600)
        self.parent=self.root/'runs';self.parent.mkdir(mode=0o755);self.nas=self.root/'nas';self.nas.mkdir(mode=0o700);self.proof=self.root/'public-proof.snapshot';self.run_id='123456789abc';self.deadline=time.monotonic()+15
        self.raw=(b'PUBLIC RAW ETCD FIXTURE\0'*256)[:4096].ljust(4096,b'\0')+b'X'*32
        self.status={'hash':123,'revision':7,'totalKey':2,'totalSize':4096,'version':'3.7.0'}
        self.source={'uid':'original-etcd','image':'registry.k8s.io/etcd:3.7.0-0','image_id':'source-observed-identity','restore_image':'registry.k8s.io/etcd@sha256:'+'1'*64}
        files={p:base64.b64encode(b'PUBLIC PKI FIXTURE').decode()for p in m.REQUIRED};files['/etc/kubernetes/longhorn-crypto-key']=base64.b64encode(b'PUBLIC LUKS FIXTURE').decode();files['/etc/kubernetes/encryption-config.json']=base64.b64encode(json.dumps({'kind':'EncryptionConfiguration','resources':[{'resources':['secrets'],'providers':[{'aescbc':{'keys':[{'name':'public-key','secret':base64.b64encode(b'X'*32).decode()}]}}]}]}).encode()).decode();self.document={'files':files}
        bundle=self.private/'config.age';recipient=self.recipient.read_text().strip();subprocess.run([str(self.runtime/'bin/age'),'-r',recipient,'-o',str(bundle)],input=json.dumps(self.document).encode(),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5);bundle.chmod(0o600);self.bundle={'path':str(bundle),'sha256':m.sha(bundle.read_bytes())}
        self.registry={'header':{'revision':'7'},'count':'2','kvs':[{'key':base64.b64encode(k).decode(),'value':base64.b64encode(b'k8s:enc:aescbc:v1:public-key:PUBLIC CIPHERTEXT').decode()}for k in(b'/registry/secrets/longhorn-system/longhorn-crypto',b'/registry/secrets/bortus/bortus-runtime')]}
        self.patch=mock.patch.object(m,'RUNTIME',self.runtime);self.patch.start();self.addCleanup(self.patch.stop);self.client=Client(self);self.addCleanup(self.client.close)
    def execute(self):return m.checkpoint(deadline=self.deadline,expected_source=self.source,config_bundle=self.bundle,recipient=self.recipient,identity_file=self.identity,tools={},password_provider=lambda:'PUBLIC PRIVATE STDIN FIXTURE',parent=self.parent,run_id=self.run_id,client=self.client)
    def test_complete_actual_age_raw_bytes_revision_equality_and_owned_cleanup(self):
        r=self.execute();self.assertEqual('completed',r['phase']);self.assertFalse(r['actual_production_checkpoint_accepted']);self.assertEqual({},self.client.objects);self.assertFalse(self.proof.exists());self.assertTrue(all(j['reaped']for j in r['owned_children']));self.assertTrue(all(v['state']=='confirmed'for v in r['operations'].values()));self.assertNotIn('digest',json.dumps(r));self.assertTrue((self.nas/('etcd-'+self.run_id+'.age')).exists())
        previous=(self.parent/('etcd-'+self.run_id)/'record.json').read_bytes();calls=len(self.client.calls)
        with self.assertRaises(m.Refused):self.execute()
        self.assertEqual(previous,(self.parent/('etcd-'+self.run_id)/'record.json').read_bytes());self.assertEqual(calls,len(self.client.calls))
    def test_api_defaulted_create_fresh_get_and_once_only_cleanup(self):
        self.client.mode='api-defaults';r=self.execute()
        self.assertEqual('completed',r['phase']);self.assertEqual({},self.client.objects)
        self.assertTrue(r['operations']['pod-delete']['result']['absence_confirmed'])
        self.assertEqual(2,sum(c[0]=='api'and c[1][0]=='delete'for c in self.client.calls))
    def test_expected_defaults_cannot_hide_changed_or_unknown_fields(self):
        _,pod=m.proposals(self.run_id,self.source['restore_image']);expected=copy.deepcopy(pod);expected['metadata'].update(uid='owned',resourceVersion='created')
        expected['spec']['tolerations']=[{'key':'node.kubernetes.io/not-ready','operator':'Exists','effect':'NoExecute','tolerationSeconds':300},{'key':'node.kubernetes.io/unreachable','operator':'Exists','effect':'NoExecute','tolerationSeconds':300}]
        expected['spec']['containers'][0].update(terminationMessagePath='/dev/termination-log',terminationMessagePolicy='File')
        self.assertEqual('owned',m.resource_matches(expected,copy.deepcopy(expected))['uid'])
        variants=[]
        for key,value in [('terminationMessagePath','/foreign'),('terminationMessagePolicy','FallbackToLogsOnError'),('unknownDefault',True)]:
            bad=copy.deepcopy(expected);bad['spec']['containers'][0][key]=value;variants.append(bad)
        bad=copy.deepcopy(expected);bad['spec']['tolerations'][0]['tolerationSeconds']=301;variants.append(bad)
        bad=copy.deepcopy(expected);bad['spec']['tolerations'].append({'key':'foreign','operator':'Exists'});variants.append(bad)
        for bad in variants:
            with self.assertRaises(m.Refused):m.resource_matches(expected,bad)
            with self.assertRaises(m.Refused):m.resource_matches(pod,bad)
    def test_extra_restored_record_is_refusal_not_subset_success(self):
        self.client.mode='extra-record'
        with self.assertRaises(m.Refused):self.execute()
        self.assertEqual({},self.client.objects)
    def test_missing_or_changed_current_key_bundle_prevents_snapshot(self):
        self.client.mode='keys-drift'
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(any(c[0]=='kube'for c in self.client.calls))
    def test_source_uid_replacement_prevents_any_privileged_dispatch(self):
        self.client.mode='source-drift'
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(any(c[0]=='remote'for c in self.client.calls))
    def test_lost_pod_create_retains_policy_and_unknown_intent_without_adoption(self):
        self.client.mode='lost-create'
        with self.assertRaises(m.Refused):self.execute()
        self.assertEqual({'pod','networkpolicy'},set(self.client.objects));r=json.loads((self.parent/('etcd-'+self.run_id)/'record.json').read_text());self.assertEqual('uncertain',r['operations']['pod-create']['state']);self.assertNotIn('networkpolicy-delete',r['operations']);self.assertTrue(self.proof.exists())
    def test_lost_pod_delete_is_once_only_and_retains_policy(self):
        self.client.mode='lost-delete'
        with self.assertRaises(m.Refused):self.execute()
        self.assertEqual(1,sum(c[0]=='api'and c[1][0]=='delete'for c in self.client.calls));self.assertIn('networkpolicy',self.client.objects)
    def test_nas_collision_never_overwrites(self):
        p=self.nas/('etcd-'+self.run_id+'.age');p.write_bytes(b'PUBLIC ORIGINAL');p.chmod(0o600)
        with self.assertRaises(m.Refused):self.execute()
        self.assertEqual(b'PUBLIC ORIGINAL',p.read_bytes());self.assertFalse(self.client.objects)
    def test_expired_shared_lease_no_dispatch_or_directory(self):
        self.deadline=time.monotonic()-1
        with self.assertRaises(m.Refused):self.execute()
        self.assertEqual([],self.client.calls);self.assertEqual([],list(self.parent.iterdir()))
    def test_snapshot_checksum_trailer_relation_and_bool_size_refused(self):
        pin={'inode':[1,2,len(self.raw),3,4],'bytes':len(self.raw),'digest':'a'*64};self.assertEqual(7,m.snapshot_status(self.status,pin))
        for change in({'bytes':4096},{'inode':[1,2,4096,3,4]},{'bytes':True}):
            with self.assertRaises(m.Refused):m.snapshot_status(self.status,dict(pin,**change))
    def test_duplicate_more_wrong_count_revision_and_invalid_registry_refuse(self):
        for change in({'count':True},{'more':True},{'count':'1'},{'header':{'revision':'6'}},{'kvs':self.registry['kvs']*2,'count':'4'}):
            with self.assertRaises(m.Refused):m.registry(dict(self.registry,**change),7)
    def test_required_original_keys_missing_refuses(self):
        doc=copy.deepcopy(self.document);doc['files'].pop('/etc/kubernetes/pki/ca.key')
        with self.assertRaises(m.Refused):m.keys(doc)
    def test_isolation_spec_hostnetwork_imageid_or_conflicting_state_refused(self):
        policy,pod=m.proposals(self.run_id,self.source['restore_image']);obj=copy.deepcopy(pod);obj['metadata'].update(uid='x',resourceVersion='y');obj['status']={'containerStatuses':[{'name':'etcd','ready':True,'state':{'running':{}},'imageID':self.source['restore_image']}]};m.resource_matches(pod,obj,True)
        for mode in('host','image','state'):
            bad=copy.deepcopy(obj)
            if mode=='host':bad['spec']['hostNetwork']=True
            elif mode=='image':bad['status']['containerStatuses'][0]['imageID']='sha256:config'
            else:bad['status']['containerStatuses'][0]['state']['waiting']={}
            with self.assertRaises(m.Refused):m.resource_matches(pod,bad,True)
    def test_canonical_deny_policy_matches_actual_omitted_empty_rule_serialization(self):
        policy,_=m.proposals(self.run_id,self.source['restore_image']);obj=copy.deepcopy(policy);obj['metadata'].update(uid='owned-policy',resourceVersion='opaque-rv')
        self.assertEqual({'podSelector','policyTypes'},set(policy['spec']));self.assertEqual(['Ingress','Egress'],policy['spec']['policyTypes']);self.assertEqual('owned-policy',m.resource_matches(policy,obj)['uid'])
        for change in({'ingress':[{}]},{'egress':[{}]},{'ingress':None},{'egress':[]},{'podSelector':{}},{'policyTypes':['Ingress']}):
            bad=copy.deepcopy(obj);bad['spec'].update(change)
            with self.assertRaises(m.Refused):m.resource_matches(policy,bad)
    def test_canonical_policy_does_not_relax_persistent_uid_rv_or_owned_name(self):
        policy,_=m.proposals(self.run_id,self.source['restore_image']);obj=copy.deepcopy(policy);obj['metadata'].update(uid='owned-policy',resourceVersion='opaque-rv')
        for change in({'uid':None},{'uid':True},{'resourceVersion':None},{'resourceVersion':''},{'name':'foreign-policy'},{'namespace':'foreign'}):
            bad=copy.deepcopy(obj);bad['metadata'].update(change)
            with self.assertRaises(m.Refused):m.resource_matches(policy,bad)
    def test_fresh_policy_uid_replacement_refuses_cleanup_without_adoption(self):
        original=self.client.api
        def api(args,body=None,maximum=None):
            result=original(args,body,maximum)
            if args[:2]==['get','networkpolicy']and len(args)>2 and args[2]!='-n'and result:result['metadata']['uid']='foreign-policy'
            return result
        self.client.api=api
        with self.assertRaises(m.Refused):self.execute()
        self.assertIn('networkpolicy',self.client.objects);self.assertFalse(any(c[0]=='api'and c[1][0]=='delete'and '/networkpolicies/'in c[1][2]for c in self.client.calls))
    def test_absence_uses_exact_typed_native_endpoints_without_cli_reinterpretation(self):
        for kind,path,api,collection in [('pod','/api/v1/namespaces/migration-system/pods','v1','PodList'),('networkpolicy','/apis/networking.k8s.io/v1/namespaces/migration-system/networkpolicies','networking.k8s.io/v1','NetworkPolicyList')]:
            calls=[]
            class Inventory:
                def api(self,args):
                    calls.append(args)
                    if args[:2]==['get','--raw']:return {'apiVersion':api,'kind':collection,'metadata':{'resourceVersion':'opaque-rv','continue':'','remainingItemCount':0},'items':[]}
                    return None
            m.absent(Inventory(),kind,'owned-name','owned-uid');self.assertEqual(['get','--raw',path],calls[-1]);self.assertEqual(2,len(calls))
    def test_typed_absence_refuses_generic_partial_overbound_foreign_and_duplicate_items(self):
        good={'apiVersion':'v1','kind':'PodList','metadata':{'resourceVersion':'opaque-rv','continue':'','remainingItemCount':0},'items':[]}
        item={'metadata':{'name':'another','namespace':m.NS,'uid':'another-uid','resourceVersion':'opaque-item'}}
        bads=[dict(good,kind='List'),dict(good,apiVersion='foreign'),dict(good,items={}),dict(good,items=[item]*10001)]
        for change in({'resourceVersion':''},{'resourceVersion':True},{'continue':'next'},{'remainingItemCount':1},{'remainingItemCount':True}):bads.append(dict(good,metadata=dict(good['metadata'],**change)))
        for change in({'uid':'owned-uid'},{'name':'owned-name'},{'namespace':'foreign'},{'uid':None}):
            value=copy.deepcopy(item);value['metadata'].update(change);bads.append(dict(good,items=[value]))
        bads.append(dict(good,items=[item,item]))
        for obj in bads:
            class Inventory:
                def api(self,args):return obj if args[:2]==['get','--raw']else None
            with self.assertRaises(m.Refused):m.absent(Inventory(),'pod','owned-name','owned-uid')
    def test_absence_unknown_kind_refuses_before_any_dispatch(self):
        class Inventory:
            def api(self,args):raise AssertionError('No dispatch for unknown kind')
        with self.assertRaises(m.Refused):m.absent(Inventory(),'secret','owned-name','owned-uid')
    def test_cipher_forced0755_on_exact_cifs_retains_six_fields_and_writer_binding(self):
        self.client.nas_mode=0o755;self.client.nas_cifs=True;result=self.execute();nas=result['operations']['nas'];self.assertEqual(0o755,nas['result']['cipher_mode']);self.assertIs(True,nas['result']['cifs_mount']);self.assertEqual({'bytes','sha256','fsynced','same_inode_readback','cipher_mode','cifs_mount'},set(nas['result']));self.assertEqual(m.nas_writer()[1],nas['details']['writer_binding']);self.assertEqual(0o600,(self.parent/('etcd-'+self.run_id)/'snapshot.age').stat().st_mode&0o777)
    def test_cipher0755_on_non_cifs_refuses_after_retaining_exclusive_output(self):
        self.client.nas_mode=0o755
        with self.assertRaises(m.Refused):self.execute()
        self.assertTrue((self.nas/('etcd-'+self.run_id+'.age')).exists());self.assertFalse(self.client.objects)
    def test_cipher_worldwrite_on_cifs_refuses_before_restore(self):
        self.client.nas_mode=0o777;self.client.nas_cifs=True
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(self.client.objects)
    def test_cipher_reply_boolean_mode_refuses_not_truthy_acceptance(self):
        self.client.nas_bad_field=('cipher_mode',True)
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(self.client.objects)
    def test_cipher_reply_boolean_count_refuses_not_numeric_acceptance(self):
        self.client.nas_bad_field=('bytes',True)
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(self.client.objects)
    def test_cipher_reply_fake_cifs_flag_or_extra_field_refuses(self):
        self.client.nas_bad_field=('cifs_mount',1)
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(self.client.objects)
    def test_cipher_reply_extra_field_refuses(self):
        self.client.nas_bad_field=('extra','PUBLIC METADATA')
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(self.client.objects)
    def test_pending_directory_flush_failure_no_mutation(self):
        original=m.Ledger.save
        def fail(ledger):
            if 'snapshot'in ledger.r['operations']:raise OSError('PUBLIC FSYNC FAULT')
            return original(ledger)
        with mock.patch.object(m.Ledger,'save',fail):
            with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(any(c[0]=='remote'and c[1]['mode']=='directory'for c in self.client.calls))
    def test_actual_cipher_authentication_tamper_refuses_before_nas_or_restore(self):
        self.client.mode='tamper-cipher'
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(any(c[0]=='spawn'and c[1][0]==str(m.SSH_BINARY)for c in self.client.calls));self.assertEqual({},self.client.objects)
        r=json.loads((self.parent/('etcd-'+self.run_id)/'record.json').read_text());self.assertEqual('uncertain',r['operations']['archive']['state'])
    def test_actual_directory_fsync_fault_cannot_authorize_source_callback(self):
        original=m.Ledger.save;fsync=os.fsync
        def save(ledger):
            def fault(fd):
                if fd==ledger.fd and 'snapshot'in ledger.r['operations']:raise OSError('PUBLIC DIRECTORY FSYNC FAULT')
                return fsync(fd)
            with mock.patch.object(m.os,'fsync',fault):return original(ledger)
        with mock.patch.object(m.Ledger,'save',save):
            with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(any(c[0]=='remote'and c[1]['mode']=='directory'for c in self.client.calls))
    def test_public_early_refusal_traceback_has_no_input_or_provider_reference(self):
        marker='PUBLIC_PRIVATE_REFERENCE'
        try:m.checkpoint(deadline=time.monotonic()-1,expected_source={'private':marker},config_bundle={'private':marker},recipient=marker,identity_file=marker,tools={},password_provider=lambda:marker,parent=marker,run_id=marker)
        except m.Refused as e:
            self.assertIsNone(e.__context__);tb=e.__traceback__
            while tb:
                if pathlib.Path(tb.tb_frame.f_code.co_filename)==pathlib.Path(m.__file__):
                    self.assertNotIn(marker,repr(tb.tb_frame.f_locals));self.assertIsNone(tb.tb_frame.f_locals['password_provider'])
                tb=tb.tb_next
        else:self.fail('Expected refusal')
    def test_actual_child_deadline_closes_owned_python_no_private_output(self):
        p=self.client.spawn([sys.executable,'-B','-c','import time;time.sleep(30)'])
        with self.assertRaises(m.Refused):m.collect(p,time.monotonic()+.1,m.q.Children(time.monotonic()+.1),body=b'PUBLIC PRIVATE BODY')
        self.assertIsNotNone(p.poll());self.assertTrue(p.stdin.closed);self.assertTrue(p.stdout.closed)
    def test_collect_completed_stream_with_already_closed_stdin(self):
        p=self.client.spawn([sys.executable,'-B','-c','import sys;sys.stdin.buffer.read();print("PUBLIC METADATA")']);p.stdin.close()
        self.assertEqual(b'PUBLIC METADATA\n',m.collect(p,self.deadline,self.client.children));self.assertIsNotNone(p.poll());self.assertTrue(p.stdout.closed)
    def test_private_stdin_not_remote_source_argv_and_forced_password_consumption(self):
        t=object.__new__(m.Transport);t.deadline=self.deadline;t.password_provider=lambda:'PUBLIC_SUDO_SENTINEL';t.children=self.client.children;t.jobs=[];captured=[];t.check=lambda:None
        def spawn(args,**kwargs):captured.append(args);return self.client.spawn([sys.executable,'-B','-c','import sys;sys.stdin.buffer.read()'])
        t.spawn=spawn;p=t.remote_start({'mode':'keys','run_id':self.run_id,'paths':[]});m.collect(p,self.deadline,self.client.children)
        argv=shlex.split(captured[0][-1]);self.assertEqual(['python3','-c',m.PRIVILEGED_WRAPPER],argv[:3]);self.assertEqual(m.REMOTE,argv[-1]);self.assertNotIn('PUBLIC_SUDO_SENTINEL',str(captured));self.assertNotIn('PUBLIC_SUDO_SENTINEL',m.REMOTE)


if __name__=='__main__':unittest.main()
