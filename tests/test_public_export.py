"""Public workflows operate without historical runs or a network."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_scorecard', ROOT/'scripts/ae_scorecard.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class PublicExport(unittest.TestCase):
    def test_default_compare_uses_published_benchmark(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            with patch.object(s, 'profile_metrics', return_value={'state':'observed', 'metrics':{'works':12}}):
                result = s.run_module('compare', argparse.Namespace(output=tmp), s.read(ROOT/'config/kaal.json'), None)
            self.assertEqual(result['state'], 'observed')
            self.assertEqual(Path(result['benchmark']['path']), ROOT/'site/cohort_values.json')
            self.assertTrue(result['benchmark']['protected'])
            self.assertIn('primary', result['comparison'])

    def test_cohort_build_and_empty_trend_from_fresh_results(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            output = Path(tmp)/'results'
            destination = output/'cohort'
            argv = ['scorecard', '--output', str(output), '--run-id', 'synthetic', 'cohort-build', str(ROOT/'tests/fixtures/cohort_pull_example.json'), '--destination', str(destination)]
            with patch.object(sys, 'argv', argv): s.main()
            exact = s.read(output/'runs/synthetic/cohort_exact.json')
            protected = s.read(destination/'cohort_values.json')
            self.assertEqual(exact['primary']['N'], 10)
            self.assertEqual(protected['primary']['values']['works'][:3], [13]*3)
            self.assertEqual(s.read(destination/'cohort_quantiles.json')['primary']['quantiles']['works']['median'], 14.5)
            with patch.object(sys, 'argv', ['scorecard', '--output', str(output/'fresh'), 'trend']): s.main()
            self.assertEqual(s.read(output/'fresh/trend.json')['observations'], [])
            self.assertTrue((output/'fresh/site/trend.html').is_file())

    def test_cohort_rejects_wrong_envelopes(self):
        for bad in ({'results':[]}, [None], [{'resolved':'yes'}], [{'resolved':True}]):
            with self.assertRaises(ValueError): s.cohort(bad)


if __name__ == '__main__': unittest.main()
