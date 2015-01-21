from os.path import join as pjoin
import os
import shutil
import logging
import copy
from pyrocko.util import time_to_str
from pyrocko import io
from pyrocko import model
from pyrocko import util

_logger = logging.getLogger('rapidinv')
mkdir = os.mkdir

def make_sane_directories(directory, force):
    if os.path.exists(directory):
        if force:
            shutil.rmtree(directory)
    mkdir(directory)

class StationConfigurator():
    def __init__(self, fn_stations):
        self.fn_stations = fn_stations
        self.stations = model.load_stations(fn_stations)

    def make_rapidinv_stations_file(self, traces):
        stats = [stat for tr in traces for stat in self.stations if
                 util.match_nslc(stat.nsc_string(), tr.nslc )]


class RapidinvConfig():
    def __init__(self,
                 base_path,
                 fn_stations,
                 fn_defaults='rapidinv.defaults',
                 **kwargs):
        
        #self.engine = kwargs['engine']
        #self.store_id = kwargs['store_id']
        self.base_path = base_path
        self.stations = StationConfigurator(fn_stations)
        self.fn_defaults = fn_defaults
        self.parameters = self.load_defaults()
        self.parameters.update(**kwargs)

    def load_defaults(self):
        defaults = {}
        with open(self.fn_defaults, 'r') as f:
            for i, line in enumerate(f.readlines()):
                k, v = line.split()
                defaults[k] = v

        return defaults
    
    def get_rapidinv_config(self):
        config_str = ''
        for k,v in self.parameters.items():
            config_str += '%s   %s\n'%(k,v)
        return config_str

    def get_depths(self, event):
        """Should be a function defined by the user"""
        z1 = event.depth
        z2 = event.depth
        dz = 0.
        return z1, z2, dz 

    def __setitem__(self, key, value):
        """Following substitutions are made:
        inversion_dir will be prepended by base_path

        Following wildcards can be used:
        GFDB_STEP*: sets the same gfdb directory for all 3 steps
        """
        if key=='DATA_DIR':
            value = pjoin(self.base_path, value)
        if key=='INVERSION_DIR':
            value = pjoin(self.base_path, value)
        if key=='GFDB_STEP*':
            for i in [1,2,3]:
                self[key+i] = value
            return 
        self.parameters[key] = value

    def __getitem__(self, key):
        return self.parameters[key]

    def copy(self):
        return copy.deepcopy(self)

class MultiEventInversion():
    def __init__(self, config, reader):
        self.config = config
        self.reader = reader
        self.reader.load_gfdb_info(config)
        self.inversions = []

    def prepare(self, force=False):
        _logger.debug('preparing, force=%s'%force)
        for i, e in enumerate(self.reader.iter_events()):
            local_config = self.config.copy()
            local_config['INVERSION_DIR'] = pjoin(self.out_path(e), 'out')
            local_config['DATA_DIR'] = pjoin(self.out_path(e), 'data')
            local_config['LATITUDE_NORTH'] = e.lat
            local_config['LONGITUDE_EAST'] = e.lon
            local_config['DEPTH_1'], local_config['DEPTH_2'], local_config['DEPTH_STEP'] = self.config.get_depths(e)
            # postponed....
            #dc_settings = self.config.get_dc_settings(e)
            #for component in ['STRIKE', 'DIP', 'RAKE']:
            #    for sub_component in ['1', '2', 'STEP']:
            #        local_config['_'.join(component, sub_component)] = dc_settings.next()

            local_config['DIP'], local_config['DEPTH_2'], local_config['DEPTH_STEP'] = self.config.get_depths(e)
            inversion = Inversion(inversion_id=i, 
                                  config=local_config,
                                  force=force)

            inversion.prepare(self.reader, e)
            self.inversions.append(inversion)

    def run_all(self):
        for i in self.inversions:
            i.run()

    def out_path(self, event):
        file_path = '_'.join(event.time_as_string().split())
        file_path = file_path.replace(':', '')
        file_path = file_path.replace('.', '_')
        return file_path


class Inversion():
    def __init__(self, inversion_id, config, force=False):
        self.config = config
        self.force = force
        
    def prepare(self, reader, event):
        self.make_directories()
        self.make_data(reader, event)
        self.make_station_file()

    def make_directories(self):
        base_path = self.config['INVERSION_DIR'].rsplit('/', 1)[0] 
        _logger.info('creating output directory: %s'%base_path)
        make_sane_directories(base_path, self.force)
        make_sane_directories(self.config['INVERSION_DIR'], self.force)
        make_sane_directories(self.config['DATA_DIR'], self.force)
    
    def run(self):
        _logger.info('starting inversion %s'%self.inversion_id)

    def make_data(self, reader, event):
        self.traces = reader.get_waveforms(event, timespan=20.)
        for tr in self.traces:
            io.save(tr, pjoin(self.config['DATA_DIR'],
                              '%network.%station.%location.%channel.mseed'))

    def make_station_file(self):
        # TODO: Check that this method works, tomorrow first
        self.config.make_rapidinv_stations_file(self.traces)
        self.config['STAT_INP_FILE']
