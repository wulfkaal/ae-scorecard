from measurement_fixture import measurement
import argparse
import ast
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_s',ROOT/'scripts/ae_scorecard.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class AuditTests(unittest.TestCase):
    def test_ownership_negative_cases(self):
        c=s.read(ROOT/'config/kaal.json');c['dois']=['10.1234/owner']
        for u in ['https://researchonline.stthomas.edu/esploro/profile/other','https://evil.example/?x=A5085764841','https://doi.org/10.1234/owner-extra','https://evil.example/10.1234/owner','https://orcid.org/0009-0008-7840-1847-extra','https://papers.ssrn.com/other?per_id=460345','https://wulfkaal.com.evil.example/','file:///wulfkaal.com']:
            self.assertFalse(s.matching(u,c),u)
        for u in c['owner_profile_urls']+['https://doi.org/10.1234/owner','https://orcid.org/'+c['orcid'],'https://openalex.org/authors/'+c['openalex_author_id']]: self.assertTrue(s.matching(u,c),u)

    def test_import_schema_rejects(self):
        c=s.read(ROOT/'config/kaal.json');base=s.read(ROOT/'site/retrieval_template.json')
        variations=[]
        for key,value in [('cutoff',True),('cutoff',0),('date','2026-02-30'),('agent',{}),('queries',{})]:
            d=copy.deepcopy(base);d[key]=value;variations.append(d)
        for rank in [0,-1,True,1.5]:
            d=copy.deepcopy(base);d['queries'][0]['results'][0]['rank']=rank;variations.append(d)
        d=copy.deepcopy(base);d['queries'][0]['results']*=2;variations.append(d)
        d=copy.deepcopy(base);d['queries'][0]['results'][0]['url']='javascript:bad';variations.append(d)
        for d in variations:
            with self.assertRaises((ValueError,TypeError)): s.import_retrieval(d,c)

    def test_body_failure_retains_status_and_headers(self):
        class Response(io.BytesIO):
            code=200;headers={'Content-Type':'text/html'}
            def read(self,*args): raise OSError('fixture')
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            c=s.Client(tmp)
            with patch.object(c.opener,'open',return_value=Response()),patch.object(s.time,'sleep'):
                r,_=c.fetch('https://example.org/')
            self.assertEqual(r['status'],200);self.assertTrue(r['body_read_error'])
            self.assertEqual(r['content_type'],'text/html')
            self.assertNotIn('no HTTP response',r['observation'])

    def test_redirect_bounds_and_scheme(self):
        class Response(io.BytesIO):
            code=302;headers={'Location':'/again','Content-Type':'text/plain'}
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            c=s.Client(tmp)
            with patch.object(c.opener,'open',side_effect=lambda *a,**k:Response()),patch.object(s.time,'sleep'):
                r,_=c.fetch('https://example.org/')
            self.assertEqual(len(r['redirect_chain']),6)
            self.assertEqual(s.read(Path(tmp)/'request_log.json')[-1]['error_type'],'RedirectLimit')
            self.assertEqual(r['location'],'https://example.org/again')
            r,_=c.fetch('file:///etc/hosts');self.assertEqual(r['error_type'],'InvalidScheme')

    def test_oversize(self):
        class Response(io.BytesIO):
            code=200;headers={'Content-Type':'text/plain'}
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            c=s.Client(tmp)
            with patch.object(c.opener,'open',return_value=Response(b'x'*32000001)),patch.object(s.time,'sleep'):
                r,body=c.fetch('https://example.org/')
            self.assertEqual(r['body_check'],'truncated');self.assertEqual(len(body),32000000)

    def test_payload_validation_and_partial_comparison(self):
        for url in ['https://api.openalex.org/works?search=x','https://api.openalex.org/works?group_by=x','https://api.openalex.org/works?filter=x','https://api.crossref.org/works?query.bibliographic=x']:
            self.assertFalse(s.valid_payload(url,{}))
        self.assertTrue(s.valid_payload('https://api.openalex.org/works?search=x',{'results':[]}))
        responses=[{'state':'observed','data':{'id':'https://openalex.org/SYNTHETIC','works_count':10,'cited_by_count':5,'summary_stats':{'h_index':2}}},{'state':'unknown','data':None},{'state':'observed','data':{'meta':{}}}]
        with patch.object(s,'api',side_effect=responses): r=s.profile_metrics(None,'SYNTHETIC')
        self.assertEqual(r['metrics']['works'],10);self.assertIsNone(r['metrics']['oa_recent']);self.assertNotIn('oa_works',r['metrics'])
        self.assertEqual(r['state'],'partial')
        v,_=s.cohort([{'resolved':True,'openalex_id':'SYNTHETIC','works':10}]);self.assertEqual(v['primary']['values']['oa_share_grouped'],[])

    def test_public_protection_preserves_exact_and_quantiles(self):
        values=s.read(ROOT/'tests/fixtures/cohort_exact.json');original=copy.deepcopy(values)
        pub=s.protect_cohort(values);self.assertEqual(values,original)
        for label in ('primary','sensitivity'):
            for m,v in pub[label]['values'].items():
                self.assertEqual(v[:3],[v[3]]*3);self.assertEqual(v[-3:],[v[-4]]*3)
                if m.startswith('oa_share'): self.assertTrue(all(x==round(x,2) for x in v))
                self.assertEqual(s.cohort_quantiles(pub)[label]['quantiles'][m]['max'],max(v))

    def test_insertion_semantics(self):
        self.assertEqual(s.insertion_position(0,[1,2])['position'],3)
        p=s.insertion_position(2,[2,2,3]);self.assertEqual((p['position'],p['N'],p['tie_size']),(2,3,3))

    def test_run_isolation_and_sealed_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            def module(name,args,config,client):
                s.save(Path(args.output)/(name+'.json'),{'run_id':client.run_id,'state':'unknown'})
            argv=['ae','--output',tmp,'--run-id','fixture','access']
            with patch.object(sys,'argv',argv),patch.object(s,'run_module',side_effect=module): s.main()
            f=Path(tmp)/'runs/fixture/report.json';before=f.read_bytes()
            s.report(f.parent);self.assertEqual(f.read_bytes(),before)
            with patch.object(sys,'argv',argv),self.assertRaises(FileExistsError): s.main()
            with tempfile.TemporaryDirectory(dir=ROOT) as bad:
                s.save(Path(bad)/'access.json',{'run_id':'one'});s.save(Path(bad)/'compare.json',{'run_id':'two'})
                with self.assertRaises(ValueError): s.report(bad)

    def test_report_semantics_and_entry_points(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            s.save(Path(tmp)/'access.json',{'pages':[{'url':'https://researchonline.stthomas.edu/esploro/profile/wulf_kaal','status':403,'body_check':'error_page'}]})
            s.report(tmp);text=(Path(tmp)/'report.html').read_text()
            self.assertIn('<section>',text);self.assertIn('<table>',text);self.assertNotIn('<pre>',text)
            self.assertIn('does not establish treatment of another client',text)
            self.assertIn('no owner DOIs are configured',text)
            self.assertLess((Path(tmp)/'report-summary.md').stat().st_size,6000)

    def test_claims_sample_and_live_checks(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            source=Path(tmp)/'index.json'
            records=[{'id':str(i),'url':'https://example.org/claims/'+str(i),'citation':'SSRN: https://ssrn.com/abstract=123','source_sha256':'a'*64,'topics':['topic']} for i in range(10)]
            records.append(records[0]);s.save(source,{'claims':records,'count':11})
            c=s.Client(tmp)
            a=s.claims(str(source),c,5,42);b=s.claims(str(source),c,5,42)
            self.assertEqual(a['metrics'],b['metrics']);self.assertIsNone(a['live_200_ok'])
            self.assertEqual(a['duplicates']['id'],1);self.assertEqual(a['metrics']['citation']['count'],5)
            with patch.object(c,'fetch',return_value=({'status':200,'body_check':'ok_html_with_title'},b'')) as fetch:
                live=s.claims(str(source),c,5,42,True)
            self.assertEqual(fetch.call_count,5);self.assertEqual(live['live_200_ok']['count'],5)
            self.assertEqual(s.wilson(0,0)['wilson_95'],None)
            self.assertAlmostEqual(s.wilson(0,10)['wilson_95'][1],.27753,places=4)

    def test_trend_unknown_noise_and_monthly_lines(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);out=root/'results';site=root/'site'
            for i in (1,2):
                p=out/'runs'/str(i)
                s.save(p/'report.json',{'date':'2026-0'+str(i)+'-01'})
                s.save(p/'complete.json',{})
                s.save(p/'measurement.json',measurement())
                queries=[{'q':str(n),'openalex':{'state':'observed','matching_ranks':[1] if n<i else []}} for n in range(12)]
                s.save(p/'retrieval.json',{'queries':queries})
            t=s.trend(out,site)
            self.assertEqual(t['changes']['topics_found']['delta'],1)
            self.assertIn('noise',t['changes']['topics_found']['noise'])
            self.assertIsNone(t['observations'][-1]['metrics']['registry_known'])
            self.assertIn('<svg',(site/'trend.html').read_text())
            self.assertLessEqual(len((out/'monthly_report.md').read_text().splitlines()),15)

    def test_metadata_privacy_and_deployment_instructions(self):
        page=s.Page((ROOT/'site/method.html').read_text())
        graph=[b['data']['@graph'] for b in page.blocks if '@graph' in b['data']][0]
        for node in graph:
            self.assertNotIn('contentUrl',node)
            self.assertIn('@id',node)
            if node['@type']=='Dataset': self.assertEqual(node['distribution']['@type'],'DataDownload')
        index=s.Page((ROOT/'site/index.html').read_text());canonical=[x['href'] for x in index.links if x.get('rel')=='canonical']
        self.assertEqual(canonical,['https://wulfkaal.com/agent-engagement/scorecard/'])
        self.assertIn('hosting infrastructure may retain request logs',(ROOT/'site/index.html').read_text())
        self.assertIn('Do not publish',(ROOT/'site/index.html').read_text())

    def test_python39_syntax(self):
        for p in (ROOT/'scripts').glob('*.py'): ast.parse(p.read_text(),feature_version=(3,9))

    def test_monthly_full_offline_partial_failure_and_registry(self):
        mspec=importlib.util.spec_from_file_location('monthly',ROOT/'scripts/monthly_run.py')
        m=importlib.util.module_from_spec(mspec)
        with patch.dict(sys.modules,{'ae_scorecard':s}): mspec.loader.exec_module(m)
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);(root/'config').mkdir();(root/'site').mkdir()
            cfg=s.read(ROOT/'config/kaal.json');cfg['canonical_urls']=['https://example.org/'];cfg['topic_queries']=['topic '+str(i) for i in range(12)]
            s.save(root/'config/kaal.json',cfg)
            s.save(root/'claims/index.json',{'claims':[{'id':'c1','url':'https://example.org/claims/c1','citation':'citation'}]})
            def offline(client,url,accept=None):
                # Fixture transport models a complete network outage, never opens a socket.
                return {'url':url,'status':None,'body_check':'unknown','content_type':'','error_type':'URLError'},b''
            argv=['monthly','--output',str(root/'results'),'--config',str(root/'config/kaal.json'),'--claims-source',str(root)]
            with patch.object(s,'ROOT',root),patch.object(s.Client,'fetch',offline),patch.object(sys,'argv',argv): m.main()
            run=next((root/'results/runs').iterdir())
            self.assertTrue((run/'complete.json').exists())
            for name in ('access','readability','indexes','retrieval','compare','claims','registry'):
                self.assertEqual(s.read(run/(name+'.json'))['run_id'],run.name)
            self.assertEqual(s.read(run/'registry.json')['state'],'unknown')
            self.assertFalse((root/'results/trend.json').exists())
            self.assertFalse((root/'site/claims-summary.json').exists())
            with patch.object(s,'ROOT',root),patch.object(sys,'argv',argv),self.assertRaises(FileExistsError): m.main()
