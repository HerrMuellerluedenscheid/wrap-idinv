from pyrocko import io, model, pile, gui_util
import subprocess
import sys
from os.path import join as pjoin
import os
import glob
from collections import defaultdict
import logging
import numpy as num

logger = logging.getLogger('wrapidinv')

def load_station_corrections(fn, combine_channels=True):
    """
    :param combine_channels: if True, return one correction per station, which is the
                             mean of all phases"""
    corrections = {}
    with open(fn, 'r') as f:
        for l in f.readlines():
            nslc_id, phasename, residual = l.split()
            nslc_id = tuple(nslc_id.split('.'))
            if not nslc_id in corrections.keys():
                corrections[nslc_id] = {}
            if residual=='None':
                residual = None
            else:
                residual = float(residual)

            corrections[nslc_id][phasename] = residual

    if combine_channels:
        combined = {}
        for nslc_id, phasename_residual in corrections.items():
            d = num.array(phasename_residual.values())
            d = d[d!=num.array(None)]
            combined[nslc_id[:3]] = num.mean(d)
        return combined
    else:
        return corrections

class Reader:
    def __init__(self, basepath, data, events, phases, need_traces=None, event_sorting=None,
                 traces_blacklist=None, flip_polarities=None, 
                 taper=None, gain=None, station_corrections=None, filter=None, exclude=None):
        self._need_traces = need_traces or 0
        self._station_corrections = station_corrections or {}
        self._gain = gain or {}
        self._taper = taper 
        self._flip_polarities = flip_polarities or []
        self._traces_blacklist = traces_blacklist or []
        self._base_path=basepath
        self._meta_events = pjoin(self._base_path, events)
        self._filter = filter
        self._exclude = exclude or {}
        if phases:
            self._meta_phases = pjoin(self._base_path, phases)
        else:
            self._meta_phases = None
        if isinstance(data, list):
            self._data_paths = [pjoin(self._base_path, p) for p in data]
        else:
            self._data_paths = pjoin(self._base_path, data)
        self._event_sorting = event_sorting

        self.log()

    def start(self):
        self.events = model.load_events(self._meta_events)
        if self._filter:
            self.events = filter(self._filter, self.events)
        for i in range(len(self.events)):
            e = self.events[i]
            if e.magnitude is None and e.moment_tensor is not None:
                e.magnitude = e.moment_tensor.magnitude
        if self._event_sorting is not None:
            self.events.sort(key=self._event_sorting)
        
        if self._meta_phases:
            self.phases = gui_util.PhaseMarker.load_markers(self._meta_phases)
        else:
            self.phases = []
        self.assign_events()
        data_paths = []
        for p in self._data_paths:
            data_paths.extend(glob.glob(p))

        self.pile = pile.make_pile(data_paths)
        self.clear_events()

    def clear_events(self):
        """remove all events which are out of the piles scope"""
        self.events = filter(lambda e: e.time>self.pile.tmin and
                             e.time<self.pile.tmax, self.events)

    def iter_events_and_markers(self):
        for e in self.iter_events():
            phases = filter

    def iter_events(self):
        for e in self.events:
            yield e

    def assign_events(self):
        # doesn't work: probably an error when assigning hashes at write time
        #hashs = {}
        #for e in self.iter_events():
        #    hashs[e.get_hash()] = e
        events_by_time = {}
        for e in self.iter_events():
            events_by_time[e.time] = e
        i_unassigned = 0
        i_assigned = 0
        self._phases = defaultdict(list)
        for p in self.phases:
            try:
                event_identifier = p.get_event_time()
                p.set_event(events_by_time[event_identifier])
                p.tmin -= p.get_event().time
                p.tmax -= p.get_event().time
                self._phases[event_identifier].append(p)
                i_assigned += 1
            except KeyError:
                logger.debug('could not set event for phase %s'%p)
                i_unassigned += 1
                pass

        logger.info('unassigned/assigned: %s/%s '%(i_unassigned, i_assigned))

    def get_waveforms(self, event, timespan=20., reset_time=False, left_shift=None):
        '''request waveforms and equilibrate sampling rates if needed
        
        :param reset_time: if True subtract event time
        :param left_shift: 0.-1. if 1:shift targeted time window 100% of window length left'''
        traces = []
        if left_shift:
            tshift = timespan*left_shift
        else:
            tshift = 0.
        for traces_segment in self.pile.chopper(event.time-tshift, event.time+timespan-tshift):
            for tr in traces_segment:
                if tr.nslc_id in self._traces_blacklist:
                    continue
                if reset_time:
                    tr.shift(-event.time)
                if tr.nslc_id in self._flip_polarities:
                    tr.set_ydata(tr.get_ydata()*-1)
                
                if tr.nslc_id in self._gain.keys():
                    tr.set_ydata(tr.get_ydata()*self._gain[tr.nslc_id])
                
                if tr.nslc_id[:3] in self._station_corrections.keys():
                    tr.shift(self._station_corrections[tr.nslc_id[:3]])
                if tr.nslc_id in self._exclude.keys():
                    tmin, tmax = self._exclude[tr.nslc_id]
                    if event.time >= tmin and event.time<=tmax:
                        continue 


                if self._taper:
                    tr.taper(self._taper)

                traces.append(tr)
        
        return traces

    def get_phases_of_event(self, event):
        return self._phases[event.time]
    
    def log(self):
        for k,v in self.__dict__.iteritems():
            logger.info("%s: %s" % (k,v))
