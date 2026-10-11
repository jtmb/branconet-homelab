import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location('qualified_schema_producer', HERE / 'current-schema-producer.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
GOOD = {'abi':1,'node_version':'v22.23.3','read_only_requested':True,
        'schema_migration_count':7,'expected_legacy_migrations':True,
        'migration_checksums_match':True,'migrations_complete':True,
        'tables_and_columns_match':True,'original_table_count':13,
        'credential_or_application_rows_read':False}


def objects():
    container = {'name':'bortus','image':m.IMAGE,
                 'volumeMounts':[{'name':'data','mountPath':'/data'}]}
    podspec = {'nodeName':'workernode2','containers':[container],
               'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':'bortus-data'}}]}
    pod = {'metadata':{'name':'bortus-public-fixture','namespace':'bortus','uid':'fixture-writer',
                      'resourceVersion':'opaque:a','ownerReferences':[{'kind':'ReplicaSet','controller':True,
                      'name':'bortus-public','uid':'fixture-rs'}]},'spec':podspec,
           'status':{'phase':'Running','conditions':[{'type':'Ready','status':'True'}],
                     'containerStatuses':[{'name':'bortus','imageID':m.IMAGE,'ready':True,
                                           'restartCount':0,'state':{'running':{}}}]}}
    dep = {'metadata':{'uid':m.DEPLOYMENT_UID,'generation':1},
           'spec':{'replicas':1,'strategy':{'type':'Recreate'},'template':{'spec':podspec}},
           'status':{'readyReplicas':1,'availableReplicas':1,'observedGeneration':1}}
    claim = {'metadata':{'uid':m.CLAIM_UID},'status':{'phase':'Bound'},
             'spec':{'volumeName':m.VOLUME}}
    pv = {'metadata':{'uid':m.PV_UID},'spec':{'claimRef':{'uid':m.CLAIM_UID},
          'persistentVolumeReclaimPolicy':'Retain','csi':{'driver':'driver.longhorn.io','volumeHandle':m.VOLUME}}}
    rs = {'metadata':{'uid':'fixture-rs','ownerReferences':[{'controller':True,'kind':'Deployment',
                     'name':'bortus','uid':m.DEPLOYMENT_UID}]}}
    return {'dep':dep,'claim':claim,'pv':pv,'pod':pod,'rs':rs}


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.root.chmod(0o700)
        self.reader = self.root / 'reader.cjs'
        self.manifest = self.root / 'manifest.json'
        for dst, src in ((self.reader,HERE/'schema-reader.cjs'),(self.manifest,HERE/'migration-manifest.json')):
            dst.write_bytes(src.read_bytes()); dst.chmod(0o600)
        self.data = objects()
        self.execs = 0
        self.gets = 0

    def tearDown(self):
        self.temp.cleanup()

    def get(self, path, deadline):
        m.left(deadline); self.gets += 1
        if '/deployments/' in path:key='dep'
        elif '/persistentvolumeclaims/' in path:key='claim'
        elif '/persistentvolumes/' in path:key='pv'
        elif '/replicasets/' in path:key='rs'
        else:
            self.assertTrue(path.endswith('/pods'))
            return {'apiVersion':'v1','kind':'PodList','metadata':{'resourceVersion':'collection:opaque'},
                    'items':[copy.deepcopy(self.data['pod'])]}
        return copy.deepcopy(self.data[key])

    def execute(self, writer, container, raw, deadline):
        self.execs += 1
        self.assertEqual(hashlib.sha256(raw).hexdigest(),m.READER_SHA)
        self.assertEqual(container,'bortus')
        self.assertEqual(writer['image'],m.IMAGE)
        m.left(deadline)
        return json.dumps(GOOD).encode()

    def collect(self, execute=None, deadline=None):
        return m.collect(self.root,self.reader,self.manifest,
                         deadline or time.monotonic()+5,time.monotonic_ns(),self.get,
                         execute or self.execute)

    def test_fresh_unique_fsynced_receipts(self):
        first=self.collect(); second=self.collect()
        self.assertNotEqual(first['path'],second['path'])
        self.assertEqual(self.execs,2);self.assertEqual(self.gets,20)
        self.assertEqual(hashlib.sha256(pathlib.Path(first['path']).read_bytes()).hexdigest(),first['sha256'])
        self.assertEqual(pathlib.Path(first['path']).stat().st_mode & 0o777,0o600)
        self.assertTrue(first['receipt']['metadata_only'])

    def test_refuses_same_name_new_uid(self):
        def changed(*args):
            out=self.execute(*args);self.data['pod']['metadata']['uid']='replacement';return out
        with self.assertRaises(m.Refused):self.collect(changed)
        self.assertFalse(list(self.root.glob('schema-*.json')))

    def test_refuses_opaque_rv_drift(self):
        def changed(*args):
            out=self.execute(*args);self.data['pod']['metadata']['resourceVersion']='opaque:b';return out
        with self.assertRaises(m.Refused):self.collect(changed)

    def test_refuses_template_drift(self):
        def changed(*args):
            out=self.execute(*args);self.data['dep']['spec']['template']['metadata']={'labels':{'changed':'yes'}};return out
        with self.assertRaises(m.Refused):self.collect(changed)

    def test_refuses_storage_replacement(self):
        self.data['claim']['metadata']['uid']='replacement'
        with self.assertRaises(m.Refused):self.collect()
        self.assertEqual(self.execs,0)

    def test_refuses_actual_image_mismatch(self):
        self.data['pod']['status']['containerStatuses'][0]['imageID']='sha256:wrong'
        with self.assertRaises(m.Refused):self.collect()
        self.assertEqual(self.execs,0)

    def test_refuses_not_ready(self):
        self.data['pod']['status']['conditions'][0]['status']='False'
        with self.assertRaises(m.Refused):self.collect()

    def test_refuses_conflicting_container_states(self):
        self.data['pod']['status']['containerStatuses'][0]['state']['terminated']={}
        with self.assertRaises(m.Refused):self.collect()
        self.assertEqual(self.execs,0)

    def test_refuses_missing_collection_resource_version(self):
        get=self.get
        def absent(path,deadline):
            value=get(path,deadline)
            if path.endswith('/pods'):value['metadata']={}
            return value
        with patch.object(self,'get',absent):
            with self.assertRaises(m.Refused):self.collect()
        self.assertEqual(self.execs,0)

    def test_refuses_fifo_before_read(self):
        self.reader.unlink();os.mkfifo(self.reader,0o600)
        started=time.monotonic()
        with self.assertRaises(m.Refused):self.collect()
        self.assertLess(time.monotonic()-started,.2)

    def test_selector_constructor_failure_reaps_child(self):
        runtime=self.root/'runtime';(runtime/'bin').mkdir(parents=True)
        kubectl=runtime/'bin/kubectl'
        kubectl.write_text('#!/usr/bin/python3\nimport time;time.sleep(5)\n');kubectl.chmod(0o700)
        original=m.subprocess.Popen;children=[]
        def tracked(*a,**kw):
            process=original(*a,**kw);children.append(process);return process
        with patch.object(m,'RUNTIME',runtime),patch.object(m.subprocess,'Popen',tracked),\
             patch.object(m.selectors,'DefaultSelector',side_effect=OSError('public fixture')):
            with self.assertRaises(OSError):
                m.node_exec({'name':'bortus-public-fixture'},'bortus',b'public-input',time.monotonic()+2)
        self.assertEqual(len(children),1)
        self.assertIsNotNone(children[0].returncode)
        self.assertFalse(pathlib.Path('/proc/'+str(children[0].pid)).exists())
        self.assertTrue(all(s.closed for s in (children[0].stdin,children[0].stdout,children[0].stderr)))

    def test_refuses_forward_schema_and_type_shortcut(self):
        for change in ({'schema_migration_count':11},{'metadata_only':True},{'abi':True}):
            value=GOOD|change
            with self.assertRaises(m.Refused):self.collect(lambda *a:json.dumps(value).encode())

    def test_refuses_expired_deadline(self):
        with self.assertRaises(m.Refused):self.collect(deadline=time.monotonic()-1)
        self.assertEqual(self.gets,0)

    def test_refuses_unpinned_or_linked_reader(self):
        self.reader.write_bytes(b'changed')
        with self.assertRaises(m.Refused):self.collect()
        self.assertEqual(self.gets,0)
        self.reader.unlink();self.reader.symlink_to(HERE/'schema-reader.cjs')
        with self.assertRaises(OSError):self.collect()

    def test_refuses_transport_error_without_receipt(self):
        def failed(*args):raise m.Refused()
        with self.assertRaises(m.Refused):self.collect(failed)
        self.assertFalse(list(self.root.glob('schema-*.json')))

    def test_real_owned_child_bounded_pipe_cleanup(self):
        runtime=self.root/'runtime';(runtime/'bin').mkdir(parents=True)
        kubectl=runtime/'bin/kubectl'
        executable='#!/usr/bin/python3\nimport sys,json\nx=sys.stdin.buffer.read()\nassert x==b"public-input"\nprint(json.dumps('+repr(GOOD)+'))\n'
        kubectl.write_text(executable);kubectl.chmod(0o700)
        with patch.object(m,'RUNTIME',runtime):
            raw=m.node_exec({'name':'bortus-public-fixture'},'bortus',b'public-input',time.monotonic()+5)
            self.assertEqual(json.loads(raw),GOOD)
            for body in ('import sys;sys.stdout.write("x"*5000)',
                         'import sys;sys.stderr.write("public-fixture-error");sys.exit(1)',
                         'import time;time.sleep(5)'):
                kubectl.write_text('#!/usr/bin/python3\n'+body+'\n')
                started=time.monotonic()
                with self.assertRaises((m.Refused,BrokenPipeError)):
                    m.node_exec({'name':'bortus-public-fixture'},'bortus',b'public-input',time.monotonic()+.3)
                self.assertLess(time.monotonic()-started,1)


if __name__=='__main__':unittest.main(verbosity=2)
