from os.path import join as pjoin
import os
import shutil
import logging
import copy
import numpy as num
from scipy.interpolate import InterpolatedUnivariateSpline
from collections import OrderedDict
from multiprocessing import Process, Pool, Queue, JoinableQueue
from pyrocko.util import time_to_str
from pyrocko import io
from pyrocko import model
from pyrocko import util
from pyrocko import gui_util
from pyrocko import orthodrome
from pyrocko import moment_tensor
from rapidinv import run_rapidinv, MinimizerError

from tunguska import gfdb

mkdir = os.mkdir
        
logger = logging.getLogger('wrapidinv')
class RapidinvDataError(Exception):
    pass

class MyGFDB(gfdb.Gfdb):
    def __init__(self, *args, **kwargs):
        try:
            self.config = kwargs.pop('config')
        except KeyError:
            self.config = None
        gfdb.Gfdb.__init__(self, *args, **kwargs)
        self.maxdist = self.firstx + self.dx*(self.nx-1)
        self.maxdepth = self.firstz + self.dx*(self.nz-1)

    def out_of_bounds(self, event, station):
        dist = orthodrome.distance_accurate50m(event, station)
        return dist<self.firstx or dist>self.maxdist or event.depth<self.firstz or event.depth>self.maxdepth

    def adjust_sampling_rates(self, traces):
        """Equalize sampling rates of all traces according to gfdb"""
        for tr in traces:
            tr.downsample_to(self.dt)
    
    def get_limits(self, in_km=False):
        if in_km is True:
            return self.firstz/1000., self.maxdepth/1000., self.firstx/1000., self.maxdist/1000.
        else:
            return self.firstz, self.maxdepth, self.firstx, self.maxdist

    @classmethod
    def from_config(cls, config):
        return cls(gfdbpath=config['GFDB_STEP1']+'/db', config=config)

def make_sane_directories(directory, force):
    if os.path.exists(directory):
        if force:
            shutil.rmtree(directory)
    mkdir(directory)

class StationConfigurator():
    def __init__(self, fn_stations):
        self.fn_stations = fn_stations
        self.stations = model.load_stations(fn_stations)

    def make_rapidinv_stations_string(self, traces, event, gfdb):
        stats = set([stat for tr in traces for stat in self.stations if
                 util.match_nslc('%s.%s.%s.*'%stat.nsl(), tr.nslc_id )])

        file_str = ''
        oob = []
        num_s = 0
        for i,s in enumerate(stats):
            if not gfdb.out_of_bounds(event, s):
                file_str +='%s   '%(i+1)
                num_s += 1
            else:
                oob.append(s.nsl)
            file_str +='%s   '%s.station
            file_str +='%s   %s\n'%(s.lat, s.lon)
        return num_s, oob, file_str

class FancyFilter():
    def __init__(self, step1, step2=None, step3=None):
        self.defaults = {}
        if not step2:
            step2 = step1

        if not step3:
            step3 = step2
        
        self.defaults['STEP1'] = step1
        self.defaults['STEP2'] = step2
        self.defaults['STEP3'] = step3
        
        self.interp = {}
        self.interpolate()

    def set_filter(self, config, e):
        ''' set filter based on scalar moment. '''
        #mag = pyrocko.moment_tensor.moment_to_magnitude(config['SCAL_MOM_1']+(config['SCAL_MOM_2']-config['SCAL_MOM_1'])/2.)
        mag = e.moment_tensor.magnitude if e.moment_tensor else e.magnitude
        for k, interp in self.interp.items():
            config.parameters[k] = interp(mag)

    def interpolate(self):
        for step, settings in self.defaults.items(): 
            mags = [e[0] for e in settings]
            fcs = num.array([e[1] for e in settings])
            for i in range(4):
                self.interp['BP_F%i_%s' % (i+1, step)] = InterpolatedUnivariateSpline(mags, fcs.T[i], k=2)

class RapidinvConfig():
    def __init__(self,
                 base_path,
                 fn_stations,
                 fn_defaults='rapidinv.defaults',
                 reset_time=False,
                 test_depths=None,
                 filter=None,
                 **kwargs):
        self.test_depths = test_depths
        #self.engine = kwargs['engine']
        #self.store_id = kwargs['store_id']
        self.base_path = base_path
        self.stations = StationConfigurator(fn_stations)
        self.fn_defaults = fn_defaults
        self.parameters = self.load_defaults()
        self.reset_time = reset_time
        self.filter = filter
        self.parameters.update(**kwargs)

    def load_defaults(self):
        defaults = OrderedDict()
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
        """Should be a function defined by the user.
        WATCH OUT: rapidinv accepts depth in km"""
        if not self.test_depths:
            dz = 0.
            z1 = event.depth/1000.
            z2 = event.depth/1000.
        else:
            dz = self.test_depths['dz']
            z1 = event.depth/1000.+self.test_depths['zstart']
            z2 = event.depth/1000.+self.test_depths['zstop']
        return z1, z2, dz 

    def make_rapidinv_stations_string(self, *args, **kwargs):
        return self.stations.make_rapidinv_stations_string(*args, **kwargs)

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
            if isinstance(v, float):
                string+='{0:25s} {1:f}\n'.format(k, v)
            else:
                string+='{0:25s} {1:s}\n'.format(k, v)
        return string

    def set_filter(self, event):
        self.filter.set_filter(self, event)
        

def worker(tasks, num_tasks):
    i = 0
    for task in iter(tasks.get, 'stop'):
        i+=1
        logger.info('get task %s: %s'%(i, task))
        try:
            thread = Process(target=run_rapidinv, args=(task,))
            logger.info('start thread %s'%thread.name) 
            #thread.deamon = True
            thread.deamon = False
            thread.start()
            
            thread.join()
            thread.terminate()
            logger.info('terminated %s'%thread.name) 
        except MinimizerError:
            logger.info('WARNING: got MinimizerError in thread %s' %thread.name)
            continue
    return True

class MultiEventInversion():
    def __init__(self, config, reader, blacklist=None, left_shift=None):
        self.left_shift = left_shift
        self.blacklist = blacklist or []
        self.config = config
        self.reader = reader
        self.gfdb = MyGFDB.from_config(config)
        self.inversions = []

    def prepare(self, force=False, num_inversions=99999999, try_set_sdr=False):
        """ Prepare inversions.

        :param force: (default False) force overwrite of existing directory
        :param num_inversions: number of inversions to be done
        :param try_set_sdr: if the underlying event contains MT information, use
        those in the rapidinv input file (default False). Mostly for debugging
        and testing.
        """
        logger.debug('preparing, force=%s'%force)
        make_sane_directories(self.config.base_path, force)
        for i, e in enumerate(self.reader.iter_events()):
            if self.out_path(e) in self.blacklist:
                continue
            local_config = self.config.copy()
            local_config['INVERSION_DIR'] = pjoin(self.out_path(e), 'out')
            local_config['DATA_DIR'] = pjoin(self.out_path(e),  'data')
            local_config['LATITUDE_NORTH'] = e.lat
            local_config['LONGITUDE_EAST'] = e.lon
            if e.moment_tensor is not None:
                local_config['SCAL_MOM_1'], local_config['SCAL_MOM_2'] =\
                    [e.moment_tensor.moment]*2
            elif e.magnitude is not None:
                local_config['SCAL_MOM_1'], local_config['SCAL_MOM_2'] =\
                    [moment_tensor.magnitude_to_moment(e.magnitude)]*2
            if try_set_sdr and e.moment_tensor is not None:
                sdr = e.moment_tensor.both_strike_dip_rake()[0]
                local_config['STRIKE_1'], local_config['STRIKE_2'] = [float(sdr[0])]*2
                local_config['DIP_1'], local_config['DIP_2'] = [float(sdr[1])]*2
                local_config['RAKE_1'], local_config['RAKE_2'] = [float(sdr[2])]*2
                for key in ['STRIKE_STEP', 'DIP_STEP', 'RAKE_STEP']:
                    local_config[key] = 1.
            local_config['SCAL_MOM_STEP'] = 0.

            local_config['DEPTH_1'], local_config['DEPTH_2'], local_config['DEPTH_STEP'] = self.config.get_depths(e)
            # Is the ORIG_TIME in seconds after 01011970? Doesnt seem to be
            # working
            #local_config['ORIG_TIME'] = e.time
            # postponed....
            #dc_settings = self.config.get_dc_settings(e)
            #for component in ['STRIKE', 'DIP', 'RAKE']:
            #    for sub_component in ['1', '2', 'STEP']:
            #        local_config['_'.join(component, sub_component)] = dc_settings.next()

            local_config['DEPTH_1'], local_config['DEPTH_2'], local_config['DEPTH_STEP'] = self.config.get_depths(e)

            local_config['DEPTH_UPPERLIM'], local_config['DEPTH_BOTTOMLIM'], local_config['EPIC_DIST_MIN'], local_config['EPIC_DIST_MAX'] = self.gfdb.get_limits(in_km=True)
            local_config['EPIC_DIST_MAXLOC'] = local_config['EPIC_DIST_MAX']
            local_config['EPIC_DIST_MAXKIN'] = local_config['EPIC_DIST_MAX']
            local_config.set_filter(e)
            inversion = Inversion(parent=self, 
                                  config=local_config,
                                  inversion_id=i, 
                                  force=force,
                                  picks=self.reader.get_phases_of_event(e))

            ready = inversion.prepare(self.reader, e)
            if ready:
                i += 1
                self.inversions.append(inversion)
                if i>=num_inversions:
                    logger.info('reached max number of wanted inversion %s'%num_inversions)
                    break
            else:
                logger.info('not preparing %s'%inversion)
                continue

    def run_all(self, ncpus=1, log_level=logging.DEBUG, do_log=False, do_align=False):
        # Auswirkung von maxtaskperchild testen
        file_paths = []
        log_file_paths = []
        pouts = []
        for inv in self.inversions:
            file_paths.append(inv.get_execute_filename())
            log_file_paths.append(inv.get_log_filename())
        log_levels = [log_level]*len(self.inversions)
        do_align = [do_align]*len(self.inversions)
        do_log = [do_log]*len(self.inversions)
        
        args = zip(file_paths, log_file_paths, log_levels, do_align, do_log)
        processes = []
        if ncpus!=1:
            logger.info("starting parallel %s+1 processes"%(ncpus))
            tasks = Queue()

            for i in range(ncpus+1):
                p = Process(target=worker, args=(tasks, len(args)))
                p.start()
                processes.append(p)
            
            for iarg, arg in enumerate(args):
                tasks.put(arg)
            
            tasks.put('stop')
            tasks.close()

            for p in processes:
                p.join()
                p.terminate()

        else:
            map(run_rapidinv, args)
        
    def out_path(self, event):
        file_path = '_'.join(event.time_as_string().split())
        file_path = file_path.replace(':', '')
        file_path = file_path.replace('.', '_')
        return file_path


class Inversion(Process):
    def __init__(self, parent, config, inversion_id=None, force=False,
                 picks=None):
        Process.__init__(self)
        self.parent = parent
        self.config = config
        self.force = force
        self.inversion_id = inversion_id
        self.picks = picks
    
        self.event = None
    
    def prepare(self, reader, event):
        self.event = event
        status = self.make_data(reader)
        if status==True:
            self.make_directories()
            try:
                self.make_station_file()
            except RapidinvDataError:
                return False
            self.write_data()
            self.write_pyrocko_event()
            self.make_rapidinv_file()
            self.write_picks()
            return True
        else:
            return False

    def make_directories(self):
        self.base_path = self.config['INVERSION_DIR'].rsplit('/', 1)[0] 
        logger.info('creating output directory: %s'%self.base_path)
        make_sane_directories(self.base_path, self.force)
        make_sane_directories(self.config['INVERSION_DIR'], self.force)
        make_sane_directories(self.config['DATA_DIR'], self.force)
    
    def get_execute_filename(self):
        return pjoin(self.base_path, 'rapid.inp')

    def get_log_filename(self):
        return pjoin(self.base_path, 'rapid.log')

    def make_data(self, reader):
        self.traces = reader.get_waveforms(self.event, timespan=20.,
                                           reset_time=self.config.reset_time, 
                                           left_shift=self.parent.left_shift)
        self.parent.gfdb.adjust_sampling_rates(self.traces)
        if self.traces==None:
            logger.debug('No Data found %s'%self.event)
            return False
        
        if len(self.traces)<reader._need_traces:
            logger.debug('Not enough traces available %s' % self.event)
            return False

        if self.traces==None:
            logger.debug('No Data found %s'%self.event)
            return False
        else:
            logger.info('Found Data %s'%self.event.time_as_string())
            return True

    def make_station_file(self):
        num_stations, self.out_of_bounds, stats = self.config.make_rapidinv_stations_string(self.traces,
                                                        self.event, 
                                                        self.parent.gfdb)
        
        fn = pjoin(self.base_path, 'data', 'stations.txt')
        self.config['STAT_INP_FILE'] = fn
        with open(fn, 'w') as f:
            f.write(stats)

        logger.debug('ID %s -  station file: %s'%(self.inversion_id, fn))
        if num_stations<2:
            raise RapidinvDataError

    def write_data(self):
        for tr in self.traces:
            fn = 'DISPL.%s.%s'%(tr.station, tr.channel)
            if tr.nslc_id[::3] in self.out_of_bounds:
                fn = 'OOB.' + fn
            fn = pjoin(self.config['DATA_DIR'], fn)
            io.save(tr, fn)
    
    def write_pyrocko_event(self):
        fn = pjoin(self.config['DATA_DIR'], 'event.pf')
        if self.config.reset_time:
            self.event.time = 0.
        model.dump_events([self.event], fn)

    def write_picks(self):
        fn = pjoin(self.config['DATA_DIR'], 'phase_picks.pf')
        gui_util.save_markers(self.picks, fn)

    def make_rapidinv_file(self):
        fn = pjoin(self.base_path, 'rapid.inp')
        with open(fn, 'w') as f:
            f.write(self.config.make_rapidinv_input())

    def __str__(self):
        return "id %s, %s"%(self.inversion_id, self.config.base_path)
