import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('s', ROOT / 'scripts/ae_scorecard.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

class Tests(unittest.TestCase):
    def test_ranking(self):
        p = s.position(5, [9, 5, 5, 1])
        self.assertEqual((p['position'], p['tie_size']), (2, 2))
        self.assertEqual(p['text'], 'joint position 2 of 4 (competition ranking; tie size 2)')
    def test_quantile(self):
        self.assertEqual(s.quantile([0, 10], .25), 2.5)
        self.assertIsNone(s.quantile([], .5))
    def test_duplicates(self):
        rows = [dict(resolved=True, openalex_id=i, works=10, oa_works=3, nonoa_works=2) for i in ['X', 'X', 'Y']]
        v, q = s.cohort(rows)
        self.assertEqual((v['primary']['N'], v['sensitivity']['N'], v['duplicate_profile_count']), (1, 3, 1))
        self.assertEqual(q['primary']['quantiles']['works']['median'], 10)
    def test_denominators(self):
        x = s.shares(3, 2, 10)
        self.assertEqual(x['oa_share_grouped'], .6)
        self.assertEqual(x['oa_share_profile'], .3)
        self.assertEqual(x['oa_share_discrepancy'], .3)
    def test_robots(self):
        r = s.robots((ROOT / 'tests/fixtures/robots.txt').read_text(), ['https://example.org/private'])
        self.assertFalse(r['path_differences']['https://example.org/private']['GPTBot'])
        self.assertTrue(r['root_rules']['Googlebot'])
        self.assertEqual(len(r['content_signal_lines']), 1)
    def test_body(self):
        for body, status, typ, expected in [(b'captcha', 200, 'text/html', 'challenge_page'), (b'', 200, 'text/html', 'empty_body'), (b'failure', 403, 'text/html', 'error_page'), (b'<title>X</title>', 200, 'text/html', 'ok_html_with_title'), (b'{}', 200, 'application/json', 'non_html')]:
            self.assertEqual(s.body_check(body, status, typ), expected)
    def test_json_ld(self):
        x = s.checklist((ROOT / 'tests/fixtures/page.html').read_bytes())
        self.assertEqual(x['types'], ['Dataset', 'Person', 'ScholarlyArticle'])
        self.assertEqual(x['items']['json_ld'], 'pass')
    def test_retrieval(self):
        c = s.read(ROOT / 'config/kaal.json')
        d = s.read(ROOT / 'site/retrieval_template.json')
        d['queries'][0]['results'] = [{'rank': 2, 'url': 'https://wulfkaal.com/paper'}, {'rank': 1, 'url': 'https://wulfkaal.com.evil.org/'}]
        r = s.import_retrieval(d, c)
        self.assertEqual(r['queries'][0]['matching_ranks'], [2])
        self.assertFalse(s.matching('https://papers.ssrn.com/sol3/paper?per_id=123', c))
    def test_no_network_and_no_spoofing_and_no_secret(self):
        class Response(io.BytesIO):
            code = 200
            headers = {'Content-Type': 'text/html'}
        seen = []
        def open_request(req, timeout):
            seen.append(req.get_header('User-agent'))
            return Response(b'<title>Offline</title>')
        # The sentinel is a fixture, never an environment value.
        sentinel = 'fixture-private-token-78219'
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            c = s.Client(temp)
            with patch.object(c.opener, 'open', side_effect=open_request), patch.object(s.time, 'sleep'):
                r, body = c.fetch('https://example.org/')
            self.assertEqual(seen, [s.UA])
            self.assertEqual(r['status'], 200)
            self.assertNotIn(sentinel, ''.join(p.read_text() for p in Path(temp).glob('*.json')))
            self.assertEqual(s.read(Path(temp) / 'exclusion_register.json')['user_agent'], s.UA)
    def test_redirect_and_error(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            c = s.Client(temp)
            with patch.object(c.opener, 'open', side_effect=OSError('offline')), patch.object(s.time, 'sleep'):
                r, b = c.fetch('https://example.org/')
            self.assertIsNone(r['status'])
            self.assertEqual(r['observation'], 'no HTTP response (client error: OSError)')
    def test_manual_redirects(self):
        import urllib.error
        class Response(io.BytesIO):
            code = 200
            headers = {'Content-Type': 'text/html'}
        seen = []
        def fake(req, timeout):
            seen.append((req.full_url, req.get_header('User-agent')))
            if len(seen) == 1:
                raise urllib.error.HTTPError(req.full_url, 302, 'Found', {'Location': '/final'}, io.BytesIO(b''))
            return Response(b'<title>Final</title>')
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            c = s.Client(temp)
            with patch.object(c.opener, 'open', side_effect=fake), patch.object(s.time, 'sleep'):
                r, b = c.fetch('https://example.org/start')
            self.assertEqual([v['status'] for v in r['redirect_chain']], [302, 200])
            self.assertEqual(seen, [('https://example.org/start', s.UA), ('https://example.org/final', s.UA)])

    def test_report_placeholder_and_site_links(self):
        from urllib.parse import urlsplit
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            r = s.report(temp)
            self.assertEqual(r['run_id'], 'offline-placeholder')
            self.assertIn('PLACEHOLDER', (Path(temp) / 'report.md').read_text())
        for file in (ROOT / 'site').glob('*.html'):
            page = s.Page(file.read_text())
            self.assertEqual(page.lang, 'en')
            self.assertTrue(page.title)
            self.assertTrue(all(b['valid'] for b in page.blocks))
            for link in page.links:
                href = link.get('href', '')
                if href and not urlsplit(href).scheme and href not in ('ae_scorecard.py', 'integration.md'):
                    self.assertTrue((file.parent / href).exists(), href)

if __name__ == '__main__': unittest.main()
