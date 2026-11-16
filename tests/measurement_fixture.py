"""Complete typed definitions for comparison fixtures."""
def measurement(principal='SYNTHETIC'):
    return {'modules':{name:{'collector_version':'fixture-v1','configuration_hash':'a'*64,
        'principal':principal,'benchmark_definition':{'identity':'fixed fixture'},
        'source_definition':{'identity':'fixture source'},
        'sampling_parameters':{'method':'seeded','size':10,'seed':1}}
        for name in ('access','readability','indexes','retrieval','compare','claims','registry')}}
