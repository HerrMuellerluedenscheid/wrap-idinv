import logging
import os
import sys
from reader import Reader
from rapidizer import RapidinvConfig, MultiEventInversion


pjoin = os.path.join
logging.basicConfig(filename='test.log', level=logging.INFO)


if __name__ == '__main__':
    
    logging.info("start-logging")
    webnet = os.environ['WEBNET']
    r = Reader(webnet,
               data='mseed/2008/*/*',
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
    logging.info('finished')
