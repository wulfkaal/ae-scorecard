import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('s', ROOT / 'scripts/ae_scorecard.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

class Regressions(unittest.TestCase):
    def test_malformed_retrieval_and_query_isolation(self):
        config = s.read(ROOT / 'config/kaal.json')
        config['topic_queries'] = ['bad', 'malformed', 'good']
        malformed = s.read(ROOT / 'tests/fixtures/malformed_api.json')
        def fake(client, url):
            if 'bad' in url: raise AttributeError('fixture')
            if 'openalex' in url: return {'state': 'observed', 'data': malformed['openalex']}
            return {'state': 'observed', 'data': malformed['crossref']}
        with tempfile.TemporaryDirectory(dir=ROOT) as temp, patch.object(s, 'api', side_effect=fake):
            r = s.run_module('retrieval', argparse.Namespace(output=temp, command='all'), config, None)
            self.assertEqual(len(r['queries']), 3)
            self.assertEqual(r['queries'][0]['error'], 'AttributeError')
            self.assertEqual(r['queries'][2]['openalex']['matching_ranks'], [3])

    def test_compare_always_written(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp, patch.object(s, 'profile_metrics', side_effect=ValueError):
            r = s.run_module('compare', argparse.Namespace(output=temp), s.read(ROOT / 'config/kaal.json'), None)
            self.assertEqual(s.read(Path(temp) / 'compare.json'), r)
            self.assertEqual(r['state'], 'unknown')


    def test_all_continues_and_passes_default(self):
        seen = []
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            def run(name, args, config, client):
                seen.append(name)
                self.assertEqual(args.cohort, str(ROOT / 'site/cohort_values.json'))
                if name == 'retrieval': raise OSError()
                s.save(Path(args.output) / (name + '.json'), {'run_id':client.run_id,'state': 'unknown'})
            with patch.object(sys, 'argv', ['ae_scorecard', '--output', temp, 'all']), patch.object(s, 'run_module', side_effect=run), patch.object(s, 'claims', side_effect=lambda source,client,*a: {'run_id':client.run_id,'state':'unknown'}):
                s.main()
            self.assertIn('compare', seen)
            self.assertEqual(len(list((Path(temp)/'runs').glob('*/report.json'))), 1)

    def test_summary_privacy_and_size(self):
        d = {'orcid-identifier': {'path': 'id'}, 'person': {'name': 'PRIVATE', 'emails': ['PRIVATE'], 'external-identifiers': {'external-identifier': [1, 2]}}, 'activities-summary': {'works': {'group': [1, 2, 3]}, 'employments': 'PRIVATE'}, 'history': {'last-modified-date': {'value': 123}}}
        r = s.index_summary('orcid', d)
        self.assertEqual(r['work_group_count'], 3)
        self.assertEqual(r['external_identifier_count'], 2)
        self.assertNotIn('PRIVATE', json.dumps(r))
        self.assertNotIn('counts_by_year', s.index_summary('openalex', {'counts_by_year': [{}] * 21}))
        self.assertEqual(s.index_summary('crossref', {'message': {'total-results': 42, 'items': ['PRIVATE']}}), {'total_results': 42})
        if (ROOT / 'results/report.json').exists(): self.assertLess((ROOT / 'results/report.json').stat().st_size, 400000)

    def test_fake_key_redacted_everywhere(self):
        fake_key = 'fake-key-ONLY-984125'
        class Response(io.BytesIO):
            code = 200
            headers = {'Content-Type': 'application/json'}
        with tempfile.TemporaryDirectory(dir=ROOT) as temp, patch.dict(os.environ, {'OPENALEX_API_KEY': fake_key}):
            client = s.Client(temp)
            seen = []
            def request(req, timeout):
                seen.append(req.full_url)
                if len(seen) == 2: raise OSError('api_key=' + fake_key)
                return Response(json.dumps({'display_name': fake_key}).encode())
            with patch.object(client.opener, 'open', side_effect=request), patch.object(s.time, 'sleep'), patch('sys.stdout', new_callable=io.StringIO) as stdout:
                observation, _ = client.fetch('https://api.openalex.org/authors/SYNTHETIC')
                client.fetch('https://api.openalex.org/authors/SYNTHETIC')
                s.save(Path(temp) / 'indexes.json', {'observation': observation, 'echoed_key': fake_key})
                s.report(temp)
                self.assertNotIn(fake_key, stdout.getvalue())
            self.assertIn('api_key=' + fake_key, seen[0])
            for p in Path(temp).iterdir(): self.assertNotIn(fake_key, p.read_text(), p.name)
            self.assertIn('api_key=REDACTED', (Path(temp) / 'request_log.json').read_text())
            self.assertNotIn(fake_key, json.dumps(s.redact({'error': 'api_key=' + fake_key})))

    def test_page_applicability(self):
        body = b'<title>Home</title><meta name="citation_title" content="Title">'
        self.assertEqual(s.checklist(body, 'home')['items']['highwire'], 'not_applicable')
        self.assertEqual(s.checklist(body, 'article')['items']['highwire'], 'fail')
        self.assertEqual(s.checklist(body + b'<meta name="citation_author" content="Author">', 'article')['items']['highwire'], 'pass')
        r = s.checklist(b'{}', 'machine_file', 'application/json')
        self.assertEqual(set(r['items']), {'parses', 'content_type', 'size'})
        wrong = s.checklist(b'{', 'machine_file', 'text/plain', 'json')
        self.assertEqual(wrong['items']['parses'], 'fail')
        self.assertEqual(wrong['items']['content_type'], 'fail')
        self.assertEqual(s.checklist(b'{', 'machine_file', 'application/json')['items']['parses'], 'fail')

    def test_compact_robots(self):
        r = s.robots('User-agent: *\nAllow: /', ['https://example.org/', 'https://example.org/about'])
        self.assertEqual(r['path_differences'], {})
        self.assertEqual(len(r['root_rules']), 15)


    def test_missing_robots_is_not_permission(self):
        config = {'canonical_urls': ['https://example.org/']}
        class Client:
            def fetch(self, url):
                return {'url': url, 'status': 404, 'content_type': 'text/plain'}, b''
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            r = s.run_module('access', argparse.Namespace(output=temp), config, Client())
            robots = r['policies'][0]['robots']
            self.assertEqual(robots['state'], 'no_restrictions_published')
            self.assertEqual(robots['http_status'], 404)
            self.assertNotIn('root_rules', robots)
