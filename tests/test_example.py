"""Distribution fixture must be re-exportable, including its ASR evidence."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from export_pool import export

class ExampleTests(unittest.TestCase):
    def test_full_case_reexports_with_machine_evidence_and_sequences(self):
        case=ROOT/'examples/couple-zodiac'
        with tempfile.TemporaryDirectory() as tmp:
            export(case/'study.final.json',tmp,case/'sequences.json')
            pool=json.loads((Path(tmp)/'asset-pool.json').read_text(encoding='utf-8'))
            self.assertEqual(len(pool['shots']),9)
            self.assertEqual(len(pool['machineTranscript']),10)
            self.assertEqual(len(pool['sequences']),1)
            self.assertTrue((Path(tmp)/'report.html').is_file())

if __name__=='__main__':unittest.main()
