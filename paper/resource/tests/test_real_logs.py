import json
from collections import Counter
from pathlib import Path
import unittest
from gemma4_verified_context import compress_log,diagnostic_lines


FIXTURES=Path(__file__).parent/"fixtures"

class AuthenticPytestFixtureTests(unittest.TestCase):
    def test_eleven_genuine_red_logs_evidence_preserved(self):
        cases=[]
        for name in ("real_logs_8.json","real_logs_3.json"):
            d=json.loads((FIXTURES/name).read_text())
            red={k:v for k,v in d['fixtures'].items() if k.endswith('/red')}
            cases.extend((k,v['text']) for k,v in red.items())
        self.assertEqual(len(cases),11)
        for key,raw in cases:
            with self.subTest(case=key):
                result=compress_log(raw)
                self.assertTrue(result.evidence_preserved)
                self.assertLessEqual(result.output_bytes,result.raw_bytes)
                original=diagnostic_lines(raw)
                packed=diagnostic_lines(result.text)
                self.assertTrue(all(packed[x]>=n for x,n in original.items()))
                self.assertEqual(result.raw_bytes,len(raw.encode('utf-8')))
    def test_holdout_three_genuine_green_and_red(self):
        d=json.loads((FIXTURES/'real_logs_3.json').read_text())
        self.assertEqual(len(d['fixtures']),6)
        for name,x in d['fixtures'].items():
            self.assertIn('text',x)
            if name.endswith('/red'):
                self.assertIn('1 failed',x['text'])
            if name.endswith('/green'):
                self.assertIn('1 passed',x['text'])
    def test_aggregate_b2_positive_byte_savings(self):
        raw=packed=0
        for file in ('real_logs_8.json','real_logs_3.json'):
            d=json.loads((FIXTURES/file).read_text())
            for key,item in d['fixtures'].items():
                if key.endswith('/red'):
                    log=item['text']
                    result=compress_log(log)
                    raw+=result.raw_bytes
                    packed+=result.output_bytes
        self.assertGreater(raw,packed)
        self.assertGreater(100*(raw-packed)/raw,50.0)

if __name__=="__main__":
    unittest.main()
