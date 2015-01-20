from pyrocko import io, model, pile, gui_util
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
        self._data = pjoin(self._base_path, data)

    def start(self):
        self.events = model.load_events(self._meta_events)
        self.phases = gui_util.PhaseMarker.load_markers(self._meta_phases)
        self.assign_events()
        data_paths = glob.glob(self._data)

        data = pile.make_pile(data_paths)
                
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


