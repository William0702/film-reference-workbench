"""Offline repair tests; do not claim these are fresh-machine network tests."""
import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bootstrap as b

class RepairTests(unittest.TestCase):
    def test_network_retry_then_verified_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'file'
            with patch.object(b.urllib.request,'urlopen',side_effect=[OSError('TLS EOF'),OSError('TLS EOF'),io.BytesIO(b'correct')]) as fetch, patch.object(b.time,'sleep'):
                b.download('https://fixture/primary',target,hashlib.sha256(b'correct').hexdigest(),['https://fixture/mirror'])
                self.assertEqual(fetch.call_count,3)
            self.assertEqual(target.read_bytes(),b'correct')

    def test_hash_mismatch_preserves_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'file';target.write_bytes(b'old')
            with patch.object(b.urllib.request,'urlopen',return_value=io.BytesIO(b'wrong')):
                with self.assertRaisesRegex(RuntimeError,'SHA256 mismatch'):
                    b.download('https://fixture/file',target,hashlib.sha256(b'correct').hexdigest())
            self.assertEqual(target.read_bytes(),b'old')

    def test_repair_skips_good_model_file_and_replaces_corrupt_one(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b,'RUNTIME',Path(tmp)):
            model=Path(tmp)/'model-small';model.mkdir()
            (model/'good').write_bytes(b'good');(model/'bad').write_bytes(b'bad')
            spec={'model':{'repository':'fixture/model','revision':'fixed','files':{
                'good':hashlib.sha256(b'good').hexdigest(),'bad':hashlib.sha256(b'repaired').hexdigest()}}}
            report={'supported':True,'tools':{x:{'ok':True} for x in ['node','ffmpeg','ffprobe']},'packages':{'ok':True}}
            with patch.object(b.urllib.request,'urlopen',return_value=io.BytesIO(b'repaired')) as fetch:
                b.repair(report,spec)
                self.assertEqual(fetch.call_count,1)
            self.assertEqual((model/'bad').read_bytes(),b'repaired')
            with patch.object(b.urllib.request,'urlopen',side_effect=AssertionError('No repeat downloads')):
                b.repair(report,spec)

    def test_unsafe_archive_does_not_escape_runtime(self):
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w') as z:z.writestr('../../escaped.txt','bad')
        with tempfile.TemporaryDirectory() as tmp, patch.object(b,'RUNTIME',Path(tmp)):
            report={'supported':True,'tools':{'node':{'ok':True},'ffmpeg':{'ok':False},'ffprobe':{'ok':False}},'packages':{'ok':True}}
            spec={'ffmpeg':{'filename':'bad.zip','version':'fixture','url':'https://fixture/archive','sha256':hashlib.sha256(payload.getvalue()).hexdigest()}}
            with patch.object(b.urllib.request,'urlopen',return_value=io.BytesIO(payload.getvalue())):
                with self.assertRaisesRegex(RuntimeError,'Unsafe archive path'):b.repair(report,spec)
            self.assertFalse((Path(tmp)/'escaped.txt').exists())

    def test_local_node_zip_install(self):
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w') as z:
            z.writestr('node-fixture/node.exe',b'fixture executable')
            z.writestr('node-fixture/LICENSE',b'fixture license')
        sha=hashlib.sha256(payload.getvalue()).hexdigest()
        spec={'node':{'version':'fixture','filename':'node.zip','url':'https://fixture/node.zip','checksumsUrl':'https://fixture/sums'},'model':{'files':{},'repository':'fixture','revision':'fixed'}}
        report={'supported':True,'tools':{x:{'ok':x!='node'} for x in ['node','ffmpeg','ffprobe']},'packages':{'ok':True}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(b,'RUNTIME',Path(tmp)):
            def fetch(url,**kwargs):return io.BytesIO((sha+'  node.zip\n').encode() if url.endswith('sums') else payload.getvalue())
            with patch.object(b.urllib.request,'urlopen',side_effect=fetch):b.repair(report,spec)
            self.assertEqual((Path(tmp)/'tools/node.exe').read_bytes(),b'fixture executable')
            self.assertTrue((Path(tmp)/'node-distribution/fixture/node-fixture/LICENSE').exists())

if __name__=='__main__':unittest.main()
