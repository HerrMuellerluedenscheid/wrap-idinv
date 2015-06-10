#/usr/bin/env python
import logging
import os
import sys
from reader import Reader, load_station_corrections
from rapidizer import RapidinvConfig, MultiEventInversion
from pyrocko.trace import CosFader


pjoin = os.path.join
logging.basicConfig(filename=None, level=logging.WARNING)

"""
VAC.SHN sollte nicht geblacklisted werden
SKC Z soll geblacklisted werden

VAC SHE und SKC SHE sind geflipped

"""
if __name__ == '__main__':
    
    logging.info("start-logging")
    webnet = os.environ['WEBNET']
    traces_blacklist = [('', 'STC', '', 'SHZ'),
                        ('', 'STC', '', 'SHE'),
                        ('', 'STC', '', 'SHN'),
                        ('', 'POC', '', 'SHE'),
                        ('', 'POC', '', 'SHN'),
                        ('', 'POC', '', 'SHZ'),
                        ('', 'ZHC', '', 'SHE'),
                        ('', 'ZHC', '', 'SHN'),
                        ('', 'ZHC', '', 'SHZ'),
                        #('', 'NKC', '', 'SHZ'),
                        #('', 'VAC', '', 'SHN'),
                        ('', 'SKC', '', 'SHE'),
                        ('', 'SKC', '', 'SHZ'), ]
                        #('', 'KRC', '', 'SHZ'),
                        #('', 'KRC', '', 'SHN'),
                        #('', 'KRC', '', 'SHE'),]
    gain = {('','STC','','SHE'):0.4, ('','STC','','SHN'):0.4, ('','STC','','SHZ'):0.4}
    station_corrections = load_station_corrections('/home/marius/src/seismerize/residuals_median_CakeResiduals.dat')
    #station_corrections = None
    taper = CosFader(xfade=3.)
    r = Reader(webnet,
               need_traces=12, 
               #data=['pole_zero/restituted_displacement/2008Oct/*'],
               data=['pole_zero/restituted_displacement/2008Oct/*',
                     'pole_zero/guessed_from_LBC/restituted_displacement/2008Oct/*'],
               #events='catalog/intern/Oct2008_events.pf', 
               #events='meta/events2008.pf', 
               events='/data/webnet/meta/events2008_mt_tunedt.pf',
               #phases='catalog/intern/Oct2008_phases.pf',
               #phases='/data/webnet/meta/phase_markers2008_reassociated_all.pf',
               phases=None,
               event_sorting=lambda x: x.magnitude,
               flip_polarities=[('','VAC','','SHE'), ('', 'SKC','','SHE')],
               traces_blacklist=traces_blacklist,
               taper=taper,
               gain=gain, 
               station_corrections=station_corrections)
    r.start()
    
    # tested depths are to be seen relative to the events source depth and given in km.
    #test_depths = {'dz': 0.4, 'zstart':0.0, 'zstop': 1.2}
    test_depths = None
    config = RapidinvConfig(base_path=pjoin(webnet,
                        'new/corrections_zno_tdom_STCZHCPOCblack'),
                            fn_defaults='rapidinv.local',
                            fn_stations=pjoin(webnet, 'meta/stations.pf'),
                            reset_time=True,
                            test_depths=test_depths)
    
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
                      try_set_sdr=False)

    inversion.run_all(32, do_log=True, do_align=False)
    #inversion.run_all(1, do_log=True, do_align=False)
    logging.info('finished')
