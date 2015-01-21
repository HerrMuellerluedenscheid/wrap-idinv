from pyrocko import io, model, pile, gui_util
import subprocess
import sys
from os.path import join as pjoin
import os
import glob

import logging

#needs to be changed for every run
_logger = logging.getLogger('rapidinv')

class Reader:
    def __init__(self, basepath, data, events, phases):
        self._base_path=basepath
        self._meta_events = pjoin(self._base_path, events)
        self._meta_phases = pjoin(self._base_path, phases)
        self._data_path = pjoin(self._base_path, data)
        self._gfdb_info = {}

    def start(self):
        self.events = model.load_events(self._meta_events)
        self.phases = gui_util.PhaseMarker.load_markers(self._meta_phases)
        self.assign_events()
        data_paths = glob.glob(self._data_path)

        self.pile = pile.make_pile(data_paths)
                
    def iter_events_and_markers(self):
        for e in self.iter_events():
            phases = filter

    def iter_events(self):
        for e in self.events:
            yield e

    def assign_events(self):
        hashs = {}
        for e in self.iter_events():
            hashs[e.get_hash()] = e
        i_unassigned = 0
        i_assigned = 0
        for p in self.phases:
            try:
                p.set_event(hashs[p.get_event_hash()])
                i_assigned += 1
            except KeyError:
                _logger.debug('could not set event for phase %s'%p)
                i_unassigned += 1
                pass

        _logger.info('unassigned/assigned: %s/%s '%(i_unassigned, i_assigned))

    def get_waveforms(self, event, timespan=10.):
        '''request waveforms and equilibrate sampling rates if needed'''
        traces = list(self.pile.chop(event.time, event.time+timespan))
        self.adjust_sampling_rates(traces)

    def adjust_sampling_rates(self, traces):
        '''Downsample traces to gfdb sampling rate. Raise an exception when
        sampling rate of traces smaller than sampling rate of GFDB'''
        for tr_segment in traces:
            for tr in tr_segment:
                if tr.deltat-self._gfdb_info['dt']>tr.deltat*0.1:
                    _logger.debug('downsampling trace %s to dt=%s'%(tr,
                                                                    self._gfdb_info['dt']))
                    tr.downsample_to(self._gfdb_info['dt'])
                
                if self._gfdb_info['dt']-tr.deltat<tr.deltat*0.1:
                    raise Exception('dt of trace %s bigger than dt of GFDB'%(tr.self._gfdb_info['dt']))

    def load_gfdb_info(self, config, GFDB_id='GFDB_STEP1'):
        p = subprocess.Popen(["gfdb_info", config[GFDB_id]],
                             stdout=subprocess.PIPE)
        out,err = p.communicate()
        if err==None and out=='':
            raise Exception('Could not find GFDB %s'%config["GFDB_STEP1"])
    
        else:
            for info_field in out.split('\n'):
                if info_field=='':
                    continue
                k,v = info_field.split('=')
                self._gfdb_info[k] = float(v)

