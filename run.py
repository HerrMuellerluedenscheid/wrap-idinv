import os
from reader import Reader
from rapidizer import RapidinvConfig, MultiEventInversion

import logging

pjoin = os.path.join

#needs to be changed for every run
LOG_FILENAME = 'rapidizer.log'
#logging.basicConfig(filename=LOG_FILENAME,
#                    level=logging.INFO)
logging.basicConfig(level=logging.INFO)

_logger = logging.getLogger('rapidinv')

_logger.info('Start logging')

if __name__ == '__main__':
    webnet = os.environ['WEBNET']
    r = Reader(webnet,
               data='mseed/2008/KAC/*',
               events='catalog/intern/Oct2008_events.pf', 
               phases='catalog/intern/Oct2008_phases.pf')
    r.start()

    config = RapidinvConfig(base_path=pjoin(webnet, 'inversions'), 
                            fn_stations=pjoin(webnet, 'meta/stations.pf'),
                            reset_time=True)
    
    inversion = MultiEventInversion(config=config, 
                                    reader=r)
    inversion.prepare(force=True,
                      num_inversions=3)

    inversion.run_all()
_logger.info('finished')
