#!/usr/bin/env python3
"""Unattended monthly observations; transport failures remain unknown."""
import argparse
import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ae_scorecard as s


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(s.ROOT/'results'))
    parser.add_argument('--config',default=str(s.ROOT/'config/kaal.json'))
    parser.add_argument('--claims-source',default='https://wulfkaal.github.io/')
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    run=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m')+'-run'
    prior=sys.argv
    try:
        sys.argv=[prior[0],'--run-id',run,'--output',args.output,'--config',args.config,'all','--claims-source',args.claims_source]+(['--live'] if args.live else [])
        s.main()
    finally: sys.argv=prior

if __name__=='__main__': main()
