#/usr/bin/env python
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
               #data=['pole_zero/restituted_displacement/2008Oct/*'],
               data=['pole_zero/restituted_displacement/2008Oct/*',
                     'pole_zero/guessed_from_LBC/restituted_displacement/2008Oct/*'],
               #events='catalog/intern/Oct2008_events.pf', 
               events='/data/webnet/meta/events2008_mt_tunedt.pf',
               #phases='catalog/intern/Oct2008_phases.pf',
               phases='/data/webnet/meta/phase_markers2008_mt_associated.pf',
               event_sorting=lambda x: -1*x.magnitude)
    r.start()

    config = RapidinvConfig(base_path=pjoin(webnet, 'inversion_mt_nolog_doalign'),
                            fn_defaults='rapidinv.local',
                            fn_stations=pjoin(webnet, 'meta/stations.pf'),
                            reset_time=True)
    
    # a list of events as expected output dir name
    blacklist = ['2008-10-10_080846_240',
                 '2008-10-10_080846_391',
                 '2008-10-12_063948_631']
    inversion = MultiEventInversion(config=config, 
                                    reader=r, 
                                    blacklist=blacklist)
    inversion.prepare(force=True,
                      num_inversions=70, 
                      try_set_sdr=False)

    inversion.run_all(8, do_log=False, do_align=True)
    logging.info('finished')
