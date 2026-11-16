from measurement_fixture import measurement
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
s=module('fix_s',ROOT/'scripts/ae_scorecard.py')

class Fixes(unittest.TestCase):
    def test_reproduced_malformed_payloads(self):
        self.assertFalse(s.valid_payload('https://api.openalex.org/works?search=x',{'results':[{'authorships':[{}]}]}))
        self.assertFalse(s.valid_payload('https://api.crossref.org/works?rows=0',{'message':{'total-results':-1}}))
        for n in (-1,True,1.5):
            self.assertFalse(s.valid_payload('https://api.openalex.org/works?filter=x',{'meta':{'count':n}}))

    def test_claims_privacy_and_validation(self):
        config=s.read(ROOT/'config/kaal.json');raw=s.read(ROOT/'tests/fixtures/claims.json')
        raw['sample_topics']['PRIVATE_PERSON_MARKER']=1;raw['source_file']='/PRIVATE_PATH_MARKER/private.json';raw['caveats']='PRIVATE_PERSON_MARKER'
        public=s.public_claims(raw,config)
        self.assertEqual(public['sample_topics']['other'],1)
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path=Path(tmp);s.save(path/'claims.json',raw)
            s.report(path)
            for f in path.glob('report*'):
                self.assertNotIn('PRIVATE_PERSON_MARKER',f.read_text());self.assertNotIn('PRIVATE_PATH_MARKER',f.read_text())
        self.assertEqual(public['declared_total'],public['observed_total'])
        raw['declared_total']='private text';self.assertNotIn('declared_total',s.public_claims(raw,config))
        for value in (-1,True,'private text'):
            bad=copy.deepcopy(raw);bad['metrics']['citation']['count']=value
            with self.assertRaises(ValueError): s.public_claims(bad,config)
        raw['metrics']['private text']={'count':1,'n':200}
        with self.assertRaises(ValueError): s.public_claims(raw,config)


    def test_preceding_comparable_per_module(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);results=root/'results';site=root/'site'
            for number,name in enumerate(('baseline','claims-only','monthly')):
                p=results/'runs'/name;s.save(p/'complete.json',{});s.save(p/'report.json',{'date':'2026-0'+str(number+1)+'-01'})
                s.save(p/'measurement.json',measurement())
                if name!='claims-only':
                    s.save(p/'access.json',{'pages':[{'status':200,'body_check':'ok_html_with_title'}]*(number+1)})
                    s.save(p/'retrieval.json',{'queries':[{'q':str(i),'openalex':{'state':'observed','matching_ranks':[1] if i<number else []}} for i in range(12)]})
                s.save(p/'claims.json',{'metrics':{'citation':s.wilson(number+1,10)}})
            data=s.trend(results,site)
            self.assertEqual(data['comparisons']['access']['previous_run_id'],'baseline')
            self.assertEqual(data['comparisons']['claims']['previous_run_id'],'claims-only')
            self.assertEqual(data['changes']['canonical_200_ok']['delta'],2)
            self.assertIn('Wilson 95% interval overlap check',data['changes']['claims_citation']['noise'])
            f=results/'runs/monthly/measurement.json';d=s.read(f);d['modules']['access']['configuration_hash']='b'*64;s.save(f,d)
            data=s.trend(results,site);self.assertEqual(data['comparisons']['access']['state'],'not comparable')
            self.assertIsNone(data['changes']['canonical_200_ok']['delta'])

    def test_tentative_single_topic(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp)
            for i in (1,2):
                p=root/'results/runs'/str(i);s.save(p/'report.json',{'date':str(i)});s.save(p/'complete.json',{})
                s.save(p/'measurement.json',measurement())
                s.save(p/'retrieval.json',{'queries':[{'q':str(n),'openalex':{'state':'observed','matching_ranks':[1] if n<i else []}} for n in range(12)]})
            d=s.trend(root/'results',root/'site')
            self.assertEqual(d['changes']['topics_found']['classification'],'tentative')
            self.assertIn('topics_found (tentative)',(root/'results/monthly_report.md').read_text())





if __name__=='__main__': unittest.main()
