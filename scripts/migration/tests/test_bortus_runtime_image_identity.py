import copy,importlib.util,pathlib,unittest
s=importlib.util.spec_from_file_location('runtime_identity_test',pathlib.Path(__file__).parents[1]/'bortus-runtime-image-identity.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Identity(unittest.TestCase):
 def test_single_child_index_requires_qualified_archive_binding(self):
  image='docker.io/jtmb92/bortus@sha256:e7539b9e79aebe0024f0cfc70dc0a8f2fe89354ab7ffcf9df7a822ffcc343f77';manifest=image.split('@')[1];index='sha256:'+'6'*64;runtime='docker.io/jtmb92/bortus@'+index
  q={'source':m.SOURCE,'image':image,'manifest':manifest,'all_three_nodes_verified':True,'current_unfiltered_security_scan_passed':True,'archive_sha256':'a'*64};p={'manifest':manifest,'archive_sha256':'a'*64,'single_child_manifest_verified':True,'runtime_image_id':runtime,'index_digest':index}
  self.assertTrue(m.matches(runtime,image,p,q))
  for key,value in [('archive_sha256','b'*64),('manifest','sha256:'+'b'*64),('single_child_manifest_verified',False)]:
   wrong=copy.deepcopy(p);wrong[key]=value;self.assertFalse(m.matches(runtime,image,wrong,q))
  self.assertFalse(m.matches('docker.io/other/bortus@'+index,image,p,q));self.assertFalse(m.matches('sha256:'+'0'*64,image,p,q));self.assertFalse(m.matches(runtime,image,{},q))
  q['all_three_nodes_verified']=False;self.assertFalse(m.matches(runtime,image,p,q))
 def test_existing_exact_identity_and_foreign_image_rejections(self):
  image='registry.example/app@sha256:'+'a'*64
  self.assertTrue(m.matches(image,image));self.assertFalse(m.matches(None,image));self.assertFalse(m.matches('docker-pullable://'+image,image));self.assertFalse(m.matches(image[:-1]+'b',image))
if __name__=='__main__':unittest.main()
