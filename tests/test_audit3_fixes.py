import argparse
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from measurement_fixture import measurement

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fix3',ROOT/'scripts/ae_scorecard.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class Audit3(unittest.TestCase):




    def test_comparability_requires_principal_and_complete_definitions(self):
        for older,newer in ((measurement('SYNTHETIC-ONE'),measurement('SYNTHETIC-TWO')),({'configuration':{}},{'configuration':{}})):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                root=Path(tmp)
                for i,definition in enumerate((older,newer)):
                    p=root/'results/runs'/str(i)
                    s.save(p/'complete.json',{});s.save(p/'report.json',{'date':str(i)})
                    s.save(p/'measurement.json',definition)
                    s.save(p/'compare.json',{'metrics':{'works':10+90*i}})
                data=s.trend(root/'results',root/'site')
                self.assertEqual(data['comparisons']['compare']['state'],'not comparable')
                self.assertTrue(all(v['delta'] is None for v in data['changes'].values()))

    def test_effective_author_is_recorded_for_every_module(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            def collect(name,args,config,client):
                s.save(Path(args.output)/(name+'.json'),{'run_id':client.run_id,'state':'unknown'})
            argv=['scorecard','--output',tmp,'--run-id','principal-fixture','compare','--author','SYNTHETIC']
            with patch.object(sys,'argv',argv),patch.object(s,'run_module',collect): s.main()
            definitions=s.read(Path(tmp)/'runs/principal-fixture/measurement.json')['modules']
            self.assertEqual(len(definitions),7)
            for definition in definitions.values(): self.assertEqual(definition['principal'],'SYNTHETIC')

    def test_missing_or_mistyped_definition_fields(self):
        for field in measurement()['modules']['compare']:
            for malformed in (None,[],True):
                with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                    root=Path(tmp)
                    for i in (0,1):
                        definition=measurement();definition['modules']['compare'][field]=malformed
                        p=root/'results/runs'/str(i)
                        s.save(p/'complete.json',{});s.save(p/'report.json',{'date':str(i)})
                        s.save(p/'measurement.json',definition)
                        s.save(p/'compare.json',{'metrics':{'works':i}})
                    data=s.trend(root/'results',root/'site')
                    self.assertEqual(data['comparisons']['compare']['state'],'not comparable',field)

    def test_attribution_empty_missing_and_mixed(self):
        usable={'authorships':[{'author':{'id':'https://openalex.org/A5085764841'}}]}
        for work in ({'authorships':[]},{'authorships':[{}]},{'authorships':[{'author':{}}]},{}):
            for results in ([work],[usable,work],[work,usable]):
                self.assertFalse(s.valid_payload('https://api.openalex.org/works?search=x',{'results':results}))
        self.assertTrue(s.valid_payload('https://api.openalex.org/works?search=x',{'results':[usable]}))

    def test_static_claims_caveats(self):
        raw=s.read(ROOT/'tests/fixtures/claims.json');raw['caveats']='untrusted'
        public=s.public_claims(raw,s.read(ROOT/'config/kaal.json'))
        self.assertEqual(public['caveats'],s.CLAIMS_CAVEATS)
        page=(ROOT/'site/claims-summary.html').read_text()
        self.assertIn(s.CLAIMS_CAVEATS,page);self.assertNotIn('<p></p>',page)
        self.assertIn('href="claims_design.md"',page)

if __name__=='__main__': unittest.main()
