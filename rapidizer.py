from os.path import join as pjoin
import logging
from pyrocko.util import time_to_str

_logger = logging.getLogger('rapidinv')

class RapidinvConfig():
    def __init__(self,
                 base_path,
                 fn_stations,
                 fn_defaults='rapidinv.defaults',
                 **kwargs):

        self.base_path = base_path
        self.fn_stations = fn_stations
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
    
    def __setitem__(self, key, value):
        """Following substitutions are made:
        inversion_dir will be prepended by base_path

        Following wildcards can be used:
        GFDB_STEP*: sets the same gfdb directory for all 3 steps
        """
        if key=='INVERSION_DIR':
            value = pjoin(self.base_path, value)
        if key=='GFDB_STEP*':
            for i in [1,2,3]:
                self[key+i] = value
            return 
        self.parameters[key] = value


class Inversion():
    def __init__(self, config, reader):
        self.config = config
        self.reader = reader

    def prepare(self):
        for e in self.reader.iter_events():
            self.config['INVERSION_DIR'] = self.out_path(e)
            self.config['LATITUDE_NORTH'] = e.lat
            self.config['LONGITUDE_EAST'] = e.lon

    def run(self):
        pass

    def out_path(self, event):
        file_path = '_'.join(event.time_as_string().split())
        file_path = file_path.replace(':', '')
        file_path = file_path.replace('.', '_')
        _logger.info('output directory: %s'%file_path)
        return file_path


        

        
