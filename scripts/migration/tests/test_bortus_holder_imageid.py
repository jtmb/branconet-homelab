"""Public metadata reproduces observed CRI display-name defaults; no runtime calls."""
import copy
import importlib.util
import pathlib
import sys
import unittest
import test_bortus_restored_consumer_fence as fixtures

spec=importlib.util.spec_from_file_location('holder_imageid_reader',pathlib.Path(__file__).parents[1]/'bortus-restore-reader.py')
reader=importlib.util.module_from_spec(spec);sys.modules[spec.name]=reader;spec.loader.exec_module(reader)
health=reader.data.health


class ImageIdentityTests(unittest.TestCase):
    def setUp(self):
        self.expected,self.objects=fixtures.fixture();self.pod=self.objects['pods']['items'][0]
        self.image=self.expected['holder_image'];self.state=self.pod['status']['containerStatuses'][0]
        self.state['imageID']=self.image
        self.proposal={'spec':copy.deepcopy(self.pod['spec'])}
    def accepts(self):
        reader.inert_holder(self.pod,self.proposal)
        self.assertEqual(self.pod['metadata']['uid'],health.holder_matches(self.pod,self.image,'claim','node').uid)
    def refuses(self):
        with self.assertRaises(reader.ReaderRefused):reader.inert_holder(self.pod,self.proposal)
        with self.assertRaises(health.Refused):health.holder_matches(self.pod,self.image,'claim','node')
    def test_actual_runtime_release_display_with_exact_spec_and_imageid(self):
        self.state['image']='docker.io/library/bortus:release-'+'b'*40
        self.accepts()
    def test_exact_digest_display_retains_success(self):self.accepts()
    def test_display_never_substitutes_missing_mismatched_or_config_imageid(self):
        for identity in (None,'sha256:'+'a'*64,'registry/bortus@sha256:'+'c'*64,
                         'alias.invalid/bortus@sha256:'+'a'*64,'docker-pullable://'+self.image,True):
            with self.subTest(identity=identity):
                self.state['imageID']=identity;self.refuses()
    def test_spec_image_must_remain_exact_even_with_approved_status_id(self):
        self.pod['spec']['containers'][0]['image']='registry/bortus:mutable';self.refuses()
    def test_state_must_be_only_running_and_display_bounded(self):
        self.state['state']['terminated']={};self.refuses()
        self.state['state']={'running':{}};self.state['image']='x'*4097;self.refuses()


if __name__=='__main__':unittest.main()
