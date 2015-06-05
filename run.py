#/usr/bin/env python
import logging
import os
import sys
from reader import Reader
from rapidizer import RapidinvConfig, MultiEventInversion
from pyrocko.trace import CosFader


pjoin = os.path.join
logging.basicConfig(filename=None, level=logging.WARNING)


if __name__ == '__main__':
    
    logging.info("start-logging")
    webnet = os.environ['WEBNET']
    traces_blacklist = [('','STC','','SHZ'), ('','VAC','','SHN'), ('', 'SKC', '', 'SHZ')]
    gain = {('','STC','','SHE'):0.4, ('','STC','','SHN'):0.4, ('','STC','','SHZ'):0.4}
    taper = CosFader(xfade=1.)
    r = Reader(webnet,
               #data=['pole_zero/restituted_displacement/2008Oct/*'],
               data=['pole_zero/restituted_displacement/2008Oct/*',
                     'pole_zero/guessed_from_LBC/restituted_displacement/2008Oct/*'],
               #events='catalog/intern/Oct2008_events.pf', 
               #events='meta/events2008.pf', 
               events='/data/webnet/meta/events2008_mt_tunedt.pf',
               #phases='catalog/intern/Oct2008_phases.pf',
               #phases='/data/webnet/meta/phase_markers2008_reassociated_all.pf',
               phases=None,
               event_sorting=lambda x: -1*x.magnitude,
               flip_polarities=[('','VAC','','SHE'), ],
               traces_blacklist=traces_blacklist,
               taper=taper,
               gain=gain)
    r.start()

    config = RapidinvConfig(base_path=pjoin(webnet,
                                            'new/bp3012hz_nodweight_SKCZbl_alex_cc3'),
                            fn_defaults='rapidinv.local',
                            fn_stations=pjoin(webnet, 'meta/stations.pf'),
                            reset_time=True)
    
    # a list of events as expected output dir name
    blacklist = ['2008-10-10_080846_240',
                 '2008-10-10_080846_391',
                 '2008-10-12_063948_631']
    inversion = MultiEventInversion(config=config, 
                                    reader=r, 
                                    blacklist=blacklist,
                                    left_shift=0.40)
    inversion.prepare(force=True,
                      num_inversions=400, 
                      try_set_sdr=True)

    inversion.run_all(32, do_log=True, do_align=False)
    logging.info('finished')
