from os.path import join as pjoin
import os
import shutil
import logging
import copy
from pyrocko.util import time_to_str
from pyrocko import io
from pyrocko import model
from pyrocko import util
from rapidinv import run_rapidinv

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

    def make_rapidinv_stations_file(self, traces, reader):
        stats = set([stat for tr in traces for stat in self.stations if
                 util.match_nslc('%s.%s.%s.*'%stat.nsl(), tr.nslc_id )])
        
        file_str = ''
        for i,s in enumerate(stats):
            if not reader.out_of_bounds(s):
                file_str +='%s   '%(i+1)
            file_str +='%s   '%s.station
            file_str +='%s   %s\n'%(s.lat, s.lon)
        return file_str

class RapidinvConfig():
    def __init__(self,
                 base_path,
                 fn_stations,
                 fn_defaults='rapidinv.defaults',
                 reset_time=False,
                 **kwargs):
        
        #self.engine = kwargs['engine']
        #self.store_id = kwargs['store_id']
        self.base_path = base_path
        self.stations = StationConfigurator(fn_stations)
        self.fn_defaults = fn_defaults
        self.parameters = self.load_defaults()
        self.reset_time = reset_time
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
        dz = 0.
        z1 = event.depth
        z2 = event.depth
        return z1, z2, dz 

    def make_rapidinv_stations_file(self, *args, **kwargs):
        return self.stations.make_rapidinv_stations_file(*args, **kwargs)

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

    def make_rapidinv_input(self):
        string = ''
        for k,v in self.parameters.items():
            string+='%s   %s\n'%(k, v)
        return string

class MultiEventInversion():
    def __init__(self, config, reader):
        self.config = config
        self.reader = reader
        self.reader.load_gfdb_info(config)
        self.inversions = []

    def prepare(self, force=False, num_inversions=99999999):
        _logger.debug('preparing, force=%s'%force)
        for i, e in enumerate(self.reader.iter_events()):
            local_config = self.config.copy()
            local_config['INVERSION_DIR'] = pjoin(self.out_path(e), 'out')
            local_config['DATA_DIR'] = pjoin(self.out_path(e),  'data')
            local_config['LATITUDE_NORTH'] = e.lat
            local_config['LONGITUDE_EAST'] = e.lon
            local_config['DEPTH_1'], local_config['DEPTH_2'], local_config['DEPTH_STEP'] = self.config.get_depths(e)
            # Is the ORIG_TIME in seconds after 01011970? Doesnt seem to be
            # working
            #local_config['ORIG_TIME'] = e.time
            
            # postponed....
            #dc_settings = self.config.get_dc_settings(e)
            #for component in ['STRIKE', 'DIP', 'RAKE']:
            #    for sub_component in ['1', '2', 'STEP']:
            #        local_config['_'.join(component, sub_component)] = dc_settings.next()

            local_config['DIP'], local_config['DEPTH_2'], local_config['DEPTH_STEP'] = self.config.get_depths(e)
            inversion = Inversion(config=local_config,
                                  inversion_id=i, 
                                  force=force)

            ready = inversion.prepare(self.reader, e)
            if ready:
                i += 1
                if i>=num_inversions:
                    break
                self.inversions.append(inversion)
            else:
                continue

    def run_all(self):
        for i in self.inversions:
            i.run()

    def out_path(self, event):
        file_path = '_'.join(event.time_as_string().split())
        file_path = file_path.replace(':', '')
        file_path = file_path.replace('.', '_')
        return file_path


class Inversion():
    def __init__(self, config, inversion_id=None, force=False):
        self.config = config
        self.force = force
        self.inversion_id = inversion_id
        self.out_of_bounds = []
        
    def prepare(self, reader, event):
        status = self.make_data(reader, event)
        if status==True:
            self.make_directories()
            self.make_station_file(reader)
            self.write_data(reader)
            self.make_rapidinv_file()
            return True
        else:
            return False

    def make_directories(self):
        self.base_path = self.config['INVERSION_DIR'].rsplit('/', 1)[0] 
        _logger.info('creating output directory: %s'%self.base_path)
        make_sane_directories(self.base_path, self.force)
        make_sane_directories(self.config['INVERSION_DIR'], self.force)
        make_sane_directories(self.config['DATA_DIR'], self.force)
    
    def run(self):
        _logger.info('starting inversion %s'%self.inversion_id)
        fn = pjoin(self.base_path, 'rapid.inp')
        run_rapidinv(fn)

    def make_data(self, reader, event):
        self.traces = reader.get_waveforms(event, timespan=20.,
                                           reset_time=self.config.reset_time)
        if self.traces==None:
            _logger.debug('No Data found %s'%event)
            return False
        else:
            _logger.info('Found Data %s'%event.time_as_string())
            return True

    def make_station_file(self, reader):
        stats = self.config.make_rapidinv_stations_file(self.traces, reader)
        fn = pjoin(self.base_path, 'data', 'stations.txt')
        self.config['STAT_INP_FILE'] = fn
        with open(fn, 'w') as f:
            f.write(stats)

        _logger.debug('ID %s -  station file: %s'%(self.inversion_id, fn))

    def out_of_bounds(self, tr):
        return tr.nslc_id in self.out_of_bounds

    def write_data(self, reader):
        for tr in self.traces:
            fn = 'DISPL.%s.%s'%(tr.station, tr.channel)
            if self.out_of_bounds(tr):
                fn = 'OOB.' + fn
            fn = pjoin(self.config['DATA_DIR'], fn)
            io.save(tr, fn)
    
    def make_rapidinv_file(self):
        fn = pjoin(self.base_path, 'rapid.inp')
        with open(fn, 'w') as f:
            f.write(self.config.make_rapidinv_input())
