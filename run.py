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
               data='mseed/2008/KAC/*Z*.mseed',
               events='catalog/intern/March2013_events.pf',
               phases='catalog/intern/March2013_phases.pf')
    r.start()

    config = RapidinvConfig(base_path=webnet, 
                            fn_stations=pjoin(webnet, 'meta/stations.pf'))
    
    inversion = MultiEventInversion(config=config, 
                                    reader=r)
    inversion.prepare(force=True)

_logger.info('finished')
