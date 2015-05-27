from pyrocko import io, model, pile, gui_util
import subprocess
import sys
from os.path import join as pjoin
import os
import glob
from collections import defaultdict
import logging



class Reader:
    def __init__(self, basepath, data, events, phases, event_sorting=None,
                 traces_blacklist=None,flip_polarities=None):
        self._flip_polarities = flip_polarities or []
        self._traces_blacklist = traces_blacklist or []
        self._base_path=basepath
        self._meta_events = pjoin(self._base_path, events)
        if phases:
            self._meta_phases = pjoin(self._base_path, phases)
        else:
            self._meta_phases = None
        if isinstance(data, list):
            self._data_paths = [pjoin(self._base_path, p) for p in data]
        else:
            self._data_paths = pjoin(self._base_path, data)
        self._event_sorting = event_sorting

    def start(self):
        self.events = model.load_events(self._meta_events)
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
                logging.debug('could not set event for phase %s'%p)
                i_unassigned += 1
                pass

        logging.info('unassigned/assigned: %s/%s '%(i_unassigned, i_assigned))

    def get_waveforms(self, event, timespan=10., reset_time=False):
        '''request waveforms and equilibrate sampling rates if needed
        
        :param reset_time: if True subtract event time'''
        traces = []
        for traces_segment in self.pile.chopper(event.time, event.time+timespan):
            if reset_time:
                for tr in traces_segment:
                    tr.shift(-event.time)
                    if tr.nslc_id in self._traces_blacklist:
                        continue
                    if tr.nslc_id in self._flip_polarities:
                        tr.set_ydata(tr.get_ydata()*-1)
            
            traces.extend(traces_segment)
        return traces

    def get_phases_of_event(self, event):
        return self._phases[event.time]

