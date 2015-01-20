import os
from reader import Reader
from rapidizer import RapidinvConfig, Inversion

import logging
#needs to be changed for every run
LOG_FILENAME = 'rapidizer.log'
logging.basicConfig(filename=LOG_FILENAME,
                    level=logging.INFO)

_logger = logging.getLogger('rapidinv')

_logger.info('Start logging')

if __name__ == '__main__':
    webnet = os.environ['WEBNET']
    print webnet
    r = Reader(webnet,
               data='mseed/2008/KAC/*Z*.mseed',
               events='catalog/intern/March2013_events.pf',
               phases='catalog/intern/March2013_phases.pf')
    r.start()

    config = RapidinvConfig(base_path=webnet)
    
    inversion = Inversion(config=config, 
                          reader=r)
    inversion.prepare()
    inversion.run()
