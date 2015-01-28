from pyrocko import io, model, pile, gui_util
import subprocess
import sys
from os.path import join as pjoin
import os
import glob

import logging


class Reader:
    def __init__(self, basepath, data, events, phases):
        self._base_path=basepath
        self._meta_events = pjoin(self._base_path, events)
        self._meta_phases = pjoin(self._base_path, phases)
        self._data_path = pjoin(self._base_path, data)

    def start(self):
        self.events = model.load_events(self._meta_events)
        self.phases = gui_util.PhaseMarker.load_markers(self._meta_phases)
        self.assign_events()
        data_paths = glob.glob(self._data_path)

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
            
            traces.extend(traces_segment)
        return traces

