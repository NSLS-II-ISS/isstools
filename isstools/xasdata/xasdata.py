import numpy as np
import matplotlib.pyplot as plt
import math
import os
from bluesky.global_state import gs
from databroker import (DataBroker as db, get_events, get_images,
                        get_table, get_fields, restream, process)
from datetime import datetime
from isstools.conversions import xray
from subprocess import call
import re
import collections
import pandas as pd

class XASdata:
    def __init__(self, **kwargs):
        self.energy = np.array([])
        self.data = np.array([])
        self.encoder_file = ''
        self.i0_file = ''
        self.it_file = ''
        self.ir_file = ''
        self.iff_file = ''
        self.data_manager = XASDataManager()
        self.header_read = ''

    def loadADCtrace(self, filename = '', filepath = '/GPFS/xf08id/pizza_box_data/'):
        array_out=[]
        with open(filepath + str(filename)) as f:
            for line in f:
                current_line = line.split()
                current_line[3] = int(current_line[3],0) >> 8
                if current_line[3] > 0x1FFFF:
                    current_line[3] -= 0x40000
                current_line[3] = float(current_line[3]) * 7.62939453125e-05
                array_out.append(
                        [int(current_line[0])+1e-9*int(current_line[1]), current_line[3], int(current_line[2])])
        return np.array(array_out)

    def loadENCtrace(self, filename = '', filepath = '/GPFS/xf08id/pizza_box_data/'):
        array_out = []
        with open(filepath + str(filename)) as f:
            for line in f:  # read rest of lines
                current_line = line.split()
                current_line[2] = int(current_line[2])
                if current_line[2] > 0:
                    current_line[2] = -(current_line[2] ^ 0xffffff - 1)
                array_out.append([int(current_line[0])+1e-9*int(current_line[1]), current_line[2], int(current_line[3])])
        return np.array(array_out)

    def loadTRIGtrace(self, filename = '', filepath = '/GPFS/xf08id/pizza_box_data/'):
        array_out = []
        with open(filepath + str(filename)) as f:
            for line in f:  # read rest of lines
                current_line = line.split()
                if(int(current_line[3]) % 2 == 0):
                    array_out.append([int(current_line[0])+1e-9*int(current_line[1]), int(current_line[3])])
        return np.array(array_out)

    def loadINTERPtrace(self, filename):
        array_timestamp=[]
        array_energy=[]
        array_i0=[]
        array_it=[]
        array_ir=[]
        array_iff=[]
        with open(str(filename)) as f:
            for line in f:
                current_line = line.split()
                if(current_line[0] != '#'):
                    array_timestamp.append(float(current_line[0]))
                    array_energy.append(float(current_line[1]))
                    array_i0.append(float(current_line[2]))
                    array_it.append(float(current_line[3]))
                    if len(current_line) >= 5:
                        array_ir.append(float(current_line[4]))
                    if len(current_line) >= 6:
                        array_iff.append(float(current_line[5]))
        self.header_read = self.read_header(filename)
        ts, energy, i0, it, ir, iff = np.array(array_timestamp), np.array(array_energy), np.array(array_i0), np.array(array_it), np.array(array_ir), np.array(array_iff)

        # Trying to make it compatible with old files (iff = [1, 1, ..., 1, 1]):
        if not len(iff):
            iff = np.ones(len(i0))
        return np.concatenate(([ts], [energy])).transpose(), np.concatenate(([ts], [i0])).transpose(),np.concatenate(([ts], [it])).transpose(), np.concatenate(([ts], [ir])).transpose(), np.concatenate(([ts], [iff])).transpose()
        
    def read_header(self, filename):
        test = ''
        line = '#'
        with open(filename) as myfile:
            while line[0] == '#':
                line = next(myfile)
                test += line
        return test[:-len(line)]


class XASdataGeneric(XASdata):
    def __init__(self, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.arrays = {}
        self.interp_arrays = {}
        self.db = db
        self.uid = ''
        
    def process(self, uid):
        self.load(uid)
        self.uid = uid
        self.interpolate()
        #sself.plot()

    def load(self, uid):
        self.arrays = {}
        self.interp_arrays = {}
        self.uid = uid
        has_encoder = False
        for i in self.db[uid]['descriptors']:
            if 'filename' in i['data_keys'][i['name']]:
                name = i['name']
                if name == 'pb9_enc1' or name == 'hhm_theta':
                    has_encoder = name
                if 'devname' in i['data_keys'][i['name']]:
                    name = i['data_keys'][i['name']]['devname']
                    if name == 'hhm_theta':
                        has_encoder = name
                    
                if i['data_keys'][i['name']]['source'] == 'pizzabox-di-file':
                    data = self.loadTRIGtrace(i['data_keys'][i['name']]['filename'], '')
                if i['data_keys'][i['name']]['source'] == 'pizzabox-adc-file':
                    data = self.loadADCtrace(i['data_keys'][i['name']]['filename'], '')
                    if i['name'] + ' offset' in self.db[uid]['start']:
                        data[:, 1] = data[:, 1] - self.db[uid]['start'][i['name'] + ' offset']
                if i['data_keys'][i['name']]['source'] == 'pizzabox-enc-file':
                    data = self.loadENCtrace(i['data_keys'][i['name']]['filename'], '')
                self.arrays[name] = data
        
        if has_encoder is not False:
            energy = np.copy(self.arrays.get(has_encoder))
            if 'angle_offset' in self.db[uid]['start']:
                energy[:, 1] = xray.encoder2energy(energy[:, 1], - float(self.db[uid]['start']['angle_offset']))
            del self.arrays[has_encoder]
            self.arrays['energy'] = energy

        
    def read_header(self, filename):
        test = ''
        line = '#'
        with open(filename) as myfile:
            while line[0] == '#':
                line = next(myfile)
                test += line
        return test[:-len(line)]

    def loadInterpFile(self, filename):
        self.arrays = {}
        self.interp_arrays = {}

        header = self.read_header(filename)
        self.uid = header[header.find('UID') + 5: header.find('\n', header.find('UID'))]

        keys = re.sub('  +', '  ', header[header.rfind('# '):][2:-1]).split('  ')
        timestamp_index = -1
        if 'Timestamp (s)' in keys:
            timestamp_index = keys.index('Timestamp (s)')
        elif 'timestamp' in keys:
            timestamp_index = keys.index('timestamp')
        
        matrix = np.loadtxt(filename)
        for i in range(matrix.shape[1]):
            if i != timestamp_index:
                self.interp_arrays[keys[i]] = np.array([matrix[:, timestamp_index], matrix[:, i]]).transpose()
        self.interp_arrays['1'] = np.array([matrix[:, timestamp_index], np.ones(len(matrix[:, 0]))]).transpose()


    def interpolate(self, key_base = 'i0'):
        min_timestamp = max([self.arrays.get(key)[0, 0] for key in self.arrays])
        max_timestamp = min([self.arrays.get(key)[len(self.arrays.get(key)) - 1, 0] for key in self.arrays])
        
        try:
            if key_base not in self.arrays.keys():
                raise ValueError('Could not find "{}" in the loaded scan. Pick another key_base for the interpolation.'.format(key_base))
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return
        
        timestamps = self.arrays[key_base][:,0]
        
        condition = timestamps < min_timestamp
        timestamps = timestamps[np.sum(condition):]
        
        condition = timestamps > max_timestamp
        timestamps = timestamps[: len(timestamps) - np.sum(condition)]
        
        for key in self.arrays.keys():
            self.interp_arrays[key] = np.array([timestamps, np.interp(timestamps, self.arrays.get(key)[:,0], self.arrays.get(key)[:,1])]).transpose()
        self.interp_arrays['1'] = np.array([timestamps, np.ones(len(self.interp_arrays[list(self.interp_arrays.keys())[0]]))]).transpose()


    def get_plot_info(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        pass


    def plot(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        pass

    def export_trace(self, filename, filepath = '/GPFS/xf08id/Sandbox/', overwrite = False):
        suffix = '.txt'
        fn = filepath + filename + suffix
        if not overwrite:
            repeat = 1
            while(os.path.isfile(fn)):
                repeat += 1
                fn = filepath + filename + '-' + str(repeat) + suffix

        pi = self.db[self.uid]['start']['PI']
        proposal = self.db[self.uid]['start']['PROPOSAL']
        saf = self.db[self.uid]['start']['SAF']
        comment = self.db[self.uid]['start']['comment']
        year = self.db[self.uid]['start']['year']
        cycle = self.db[self.uid]['start']['cycle']
        scan_id = self.db[self.uid]['start']['scan_id']
        real_uid = self.db[self.uid]['start']['uid']
        start_time = self.db[self.uid]['start']['time']
        stop_time = self.db[self.uid]['stop']['time']
        human_start_time = str(datetime.fromtimestamp(start_time).strftime('%m/%d/%Y  %H:%M:%S'))
        human_stop_time = str(datetime.fromtimestamp(stop_time).strftime('%m/%d/%Y  %H:%M:%S'))
        human_duration = str(datetime.fromtimestamp(stop_time - start_time).strftime('%M:%S'))
        if hasattr(self.db[self.uid]['start'], 'trajectory_name'):
            trajectory_name = self.db[self.uid]['start']['trajectory_name']
        else:
            trajectory_name = ''
        copy_interp = collections.OrderedDict(sorted(self.interp_arrays.items())).copy()
        #copy_interp = self.interp_arrays.copy()
        if '1' in copy_interp:
            del copy_interp['1']
        keys = copy_interp.keys()
        matrix = [self.interp_arrays[list(self.interp_arrays.keys())[0]][:,0]]
        energy_header = ''
        if 'energy' in copy_interp.keys():
            matrix.append(copy_interp['energy'][:,1])
            del copy_interp['energy']
            energy_header = 'energy'
        elif 'En. (eV)' in copy_interp.keys():
            matrix.append(copy_interp['En. (eV)'][:,1])
            del copy_interp['En. (eV)']
            energy_header = 'En. (eV)'

        i0_header = ''
        if 'i0' in copy_interp.keys():
            matrix.append(copy_interp['i0'][:,1])
            del copy_interp['i0']
            i0_header = 'i0'
        elif 'i0 (V)' in copy_interp.keys():
            matrix.append(copy_interp['i0 (V)'][:,1])
            del copy_interp['i0 (V)']
            i0_header = 'i0 (V)'

        it_header = ''
        if 'it' in copy_interp.keys():
            matrix.append(copy_interp['it'][:,1])
            del copy_interp['it']
            it_header = 'it'
        elif 'it(V)' in copy_interp.keys():
            matrix.append(copy_interp['it(V)'][:,1])
            del copy_interp['it(V)']
            it_header = 'it(V)'

        ir_header = ''
        if 'ir' in copy_interp.keys():
            matrix.append(copy_interp['ir'][:,1])
            del copy_interp['ir']
            ir_header = 'ir'
        elif 'ir(V)' in copy_interp.keys():
            matrix.append(copy_interp['ir(V)'][:,1])
            del copy_interp['ir(V)']
            ir_header = 'ir(V)'

        iff_header = ''
        if 'iff' in copy_interp.keys():
            matrix.append(copy_interp['iff'][:,1])
            del copy_interp['iff']
            iff_header = 'iff'
        elif 'iff(V)' in copy_interp.keys():
            matrix.append(copy_interp['iff(V)'][:,1])
            del copy_interp['iff(V)']
            iff_header = 'iff(V)'
        

        for key in copy_interp.keys():
            matrix.append(copy_interp[key][:,1])
        matrix = np.array(matrix).transpose()

        fmt = ' '.join(['%12.6f' for key in copy_interp.keys()])
        header = '  '.join(copy_interp.keys())
        if iff_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(iff_header, header)
        if ir_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(ir_header, header)
        if it_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(it_header, header)
        if i0_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(i0_header, header)
        if energy_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(energy_header, header)
        fmt = '{} {}'.format('%17.6f', fmt)
        header = '{}  {}'.format('timestamp', header)

        np.savetxt(fn, 
                   matrix, 
                   fmt=fmt, 
                   delimiter=" ", 
                   header = header,
                   comments = '# Year: {}\n'\
                              '# Cycle: {}\n'\
                              '# SAF: {}\n'\
                              '# PI: {}\n'\
                              '# PROPOSAL: {}\n'\
                              '# Scan ID: {}\n'\
                              '# UID: {}\n'\
                              '# Trajectory name: {}\n'\
                              '# Start time: {}\n'\
                              '# Stop time: {}\n'\
                              '# Total time: {}\n#\n# '.format(year, 
                                                               cycle, 
                                                               saf, 
                                                               pi, 
                                                               proposal, 
                                                               scan_id, 
                                                               real_uid, 
                                                               trajectory_name, 
                                                               human_start_time, 
                                                               human_stop_time, 
                                                               human_duration))
        call(['setfacl', '-m', 'g:iss-staff:rwX', fn])
        call(['chmod', '770', fn])
        return fn

    def get_energy_string(self, possibilities = ['energy', 'En. (eV)']):

        try:
            energy_string = ''
            for string in possibilities:
                if string in self.interp_arrays.keys():
                    return string
            raise ValueError('Could not find energy'\
                             ' in the header of the'\
                             ' loaded scan. Sorry for that.')
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return -1



    def bin_equal(self, en_spacing = 2):

        try:
            energy_string = ''
            if 'energy' in self.interp_arrays.keys():
                energy_string = 'energy'
            elif 'En. (eV)' in self.interp_arrays.keys():
                energy_string = 'En. (eV)'
            else:
                raise ValueError('Could not find energy'\
                                 ' in the header of the'\
                                 ' loaded scan. Sorry for that.')
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return -1

        return self.data_manager.process_equal(self.interp_arrays,
                                            energy_string = energy_string,
                                            delta_en = en_spacing)

    def bin(self, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk):

        try:
            energy_string = ''
            if 'energy' in self.interp_arrays.keys():
                energy_string = 'energy'
            elif 'En. (eV)' in self.interp_arrays.keys():
                energy_string = 'En. (eV)'
            else:
                raise ValueError('Could not find energy'\
                                 ' in the header of the'\
                                 ' loaded scan. Sorry for that.')
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return    

        return self.data_manager.process(self.interp_arrays, 
                                             e0, edge_start, edge_end,
                                             preedge_spacing, xanes, 
                                             exafsk, energy_string = energy_string)









# Constants for converting from hwhm -> gaussian parameters
GAUSS_SIGMA_FACTOR = 1 / (2*(2*np.log(2))**.5)

def generate_sampled_gauss_window(x, fwhm, x0):
    sigma = fwhm * GAUSS_SIGMA_FACTOR
    a = 1 / (sigma * (2*np.pi)**.5)
    data_y = a * np.exp(-.5 * ((x - x0) / sigma) ** 2)
    data_y = np.array(data_y) #/ np.sum(data_y))
    #data_y = np.array(data_y / np.sum(data_y))
    return data_y

def _compute_window_width(sample_points):
    '''Given smaple points compute windows via approx 1D voronoi

    Parameters
    ----------
    sample_points : array
        Assumed to be monotonic

    Returns
    -------
    windows : array
        Average of distances to neighbors
    '''
    d = np.diff(sample_points)
    fw = (d[1:] + d[:-1]) / 2
    return np.concatenate((fw[0:1], fw, fw[-1:]))

def _gen_convolution_bin_matrix(sample_points, data_x):
    fwhm = _compute_window_width(sample_points)
    delta_en = _compute_window_width(data_x)
    
    mat = generate_sampled_gauss_window(data_x.reshape(1, -1),
                                        fwhm.reshape(-1, 1),
                                        sample_points.reshape(-1, 1))
    mat *= delta_en.reshape(1, -1)
    return mat

def convolution_bin(sample_points, data_x, data_y):
    mat = _gen_convolution_bin_matrix(sample_points, data_x)
    return mat @ data_y.reshape(-1, 1)

def sort_bunch_of_array(index, *args):
    indx = np.argsort(index)
    return tuple(a[indx] for a in (index,) + args)

class XASDataManager:
    def __init__(self, *args, **kwargs):
        self.data_arrays = {}
        self.binned_eq_arrays = {}
        self.binned_arrays = {}

    def delta_energy(self, array):
        diff = np.diff(array)
        diff = np.concatenate((diff,[diff[len(diff)-1]]))
        out = (np.concatenate(([diff[0]], diff[:len(diff)-1])) + diff)/2
        return out
    
    def sort_data(self, matrix, column_to_sort):
        return matrix[matrix[:,column_to_sort].argsort()]
    
    def energy_grid_equal(self, array, interval):
        return np.arange(np.min(array), np.max(array) + interval/2, interval)
    
    def energy_grid(self, array, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk):
        preedge = np.arange(np.min(array), edge_start, preedge_spacing)
        edge = np.arange(edge_start, edge_end, xanes)

        eenergy = xray.k2e(xray.e2k(edge_end, e0), e0)
        postedge = np.array([])

        while(eenergy < np.max(array)):
            kenergy = xray.e2k(eenergy, e0)
            kenergy += exafsk
            eenergy = xray.k2e(kenergy, e0)
            postedge = np.append(postedge, eenergy)

        return np.append(np.append(preedge, edge), postedge)

    def get_k_data(self, e0, edge_end, exafsk, y_data, energy_array, en_orig, data_orig, pow = 1):
        e_interval = self.get_k_interval(energy_array, e0, e0 + edge_end, exafsk)
        k_interval = xray.e2k(e_interval, e0) #e0 + edge_end)

        condition = en_orig >= e0 + edge_end 
        en_orig = np.extract(condition, en_orig)
        data_orig = np.extract(condition, data_orig)
        polyfit = np.polyfit(en_orig, data_orig, 2) #2 is ok?
        p = np.poly1d(polyfit)
        calibration = p(e_interval)

        y_data = y_data[-len(k_interval):] - calibration
        data = y_data[-len(k_interval):] * (k_interval ** pow)
        return np.array([k_interval, data])


    def get_k_interval(self, energy_array, e0, edge_end, exafsk):
        iterator = exafsk
        kenergy = 0
        postedge = np.array([])
        
        while(kenergy + edge_end < np.max(energy_array)):
            kenergy = xray.k2e(iterator, e0) - e0
            postedge = np.append(postedge, edge_end + kenergy)
            iterator += exafsk

        return postedge
 

    def get_plotk_info(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        if len(plotting_dic) > 0:
            self.num_orig = plotting_dic['original_numerator']
            self.den_orig = plotting_dic['original_denominator']
            self.log = plotting_dic['log']
            division = self.num_orig/self.den_orig
            if self.log:
                division = np.log(division)
            self.abs = division

        else:
            self.abs = np.log(self.i0_interp / self.it_interp)
        
        #ax.plot(self.en_grid, self.abs, color)
        #ax.grid(True)
        xlabel = 'Energy (eV)'
        ylabel = 'Log(i0 / it)'

        return [self.en_grid, self.abs, color, xlabel, ylabel, ax]
    

    def gauss(self, x, fwhm, x0):
        sigma = fwhm / (2 * ((np.log(2)) ** (1/2)))
        a = 1/(sigma * ((2 * np.pi) ** (1/2)))
        data_y = a * np.exp(-.5 * np.float64(np.float64(x - x0) / sigma) ** 2)
        data_y = np.array(data_y) #/ np.sum(data_y))
        #data_y = np.array(data_y / np.sum(data_y))
        return data_y
    
    def bin(self, en_st, data_x, data_y):
        buf = self.delta_energy(en_st)
        delta_en = self.delta_energy(data_x)
        mat = []
        for i in range(len(buf)):
            line = self.gauss(data_x, buf[i], en_st[i])
            mat.append(line)
        self.mat = mat
        data_st = np.matmul(np.array(delta_en * mat), data_y)
        return data_st.transpose()

  

    def get_derivative(self, array):
        derivative = np.diff(array)
        derivative = np.append(array[0], derivative)
        return derivative


    def export_dat(self, filename):
        comments = XASdataGeneric.read_header(None, filename)
        comments = comments[0: comments.rfind('#')] + '# '

        filename = filename[0: len(filename) - 3] + 'dat'

        copy_interp = collections.OrderedDict(sorted(self.binned_arrays.items())).copy()
        if '1' in copy_interp:
            del copy_interp['1']
        keys = copy_interp.keys()
        matrix = []

        energy_header = ''
        if 'energy' in copy_interp.keys():
            matrix.append(copy_interp['energy'])
            del copy_interp['energy']
            energy_header = 'energy'
        elif 'En. (eV)' in copy_interp.keys():
            matrix.append(copy_interp['En. (eV)'])
            del copy_interp['En. (eV)']
            energy_header = 'En. (eV)'

        i0_header = ''
        if 'i0' in copy_interp.keys():
            matrix.append(copy_interp['i0'])
            del copy_interp['i0']
            i0_header = 'i0'
        elif 'i0 (V)' in copy_interp.keys():
            matrix.append(copy_interp['i0 (V)'])
            del copy_interp['i0 (V)']
            i0_header = 'i0 (V)'

        it_header = ''
        if 'it' in copy_interp.keys():
            matrix.append(copy_interp['it'])
            del copy_interp['it']
            it_header = 'it'
        elif 'it(V)' in copy_interp.keys():
            matrix.append(copy_interp['it(V)'])
            del copy_interp['it(V)']
            it_header = 'it(V)'

        ir_header = ''
        if 'ir' in copy_interp.keys():
            matrix.append(copy_interp['ir'])
            del copy_interp['ir']
            ir_header = 'ir'
        elif 'ir(V)' in copy_interp.keys():
            matrix.append(copy_interp['ir(V)'])
            del copy_interp['ir(V)']
            ir_header = 'ir(V)'

        iff_header = ''
        if 'iff' in copy_interp.keys():
            matrix.append(copy_interp['iff'])
            del copy_interp['iff']
            iff_header = 'iff'
        elif 'iff(V)' in copy_interp.keys():
            matrix.append(copy_interp['iff(V)'])
            del copy_interp['iff(V)']
            iff_header = 'iff(V)'


        for key in copy_interp.keys():
            matrix.append(copy_interp[key])
        matrix = np.array(matrix).transpose()

        fmt = ' '.join(['%12.6f' for key in copy_interp.keys()])
        header = '  '.join(copy_interp.keys())

        if iff_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(iff_header, header)
        if ir_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(ir_header, header)
        if it_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(it_header, header)
        if i0_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(i0_header, header)
        if energy_header:
            fmt = '{} {}'.format('%12.6f', fmt)
            header = '{}  {}'.format(energy_header, header)

        np.savetxt(filename,
                   matrix,
                   fmt=fmt,
                   delimiter=" ",
                   header = header,
                   comments = comments)
        call(['setfacl', '-m', 'g:iss-staff:rwX', filename])
        call(['chmod', '770', filename])
        return filename




        call(['setfacl', '-m', 'g:iss-staff:rwX', filename])
        call(['chmod', '770', filename]) 


    def process(self, interp_dict, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk, energy_string = 'energy'):

        self.matrix = interp_dict[energy_string][:, 1]

        self.matrix = np.vstack((self.matrix, np.array([interp_dict[array][:, 1] for array in list(interp_dict.keys()) if array != energy_string]))).transpose()
        self.sorted_matrix = self.sort_data(self.matrix, 0)
        self.en_grid = self.energy_grid(self.sorted_matrix[:, 0], e0, edge_start, edge_end, preedge_spacing, xanes, exafsk)

        self.data_matrix = self.average_points(self.sorted_matrix, 0)
        self.data_arrays = {energy_string: self.data_matrix[:, 0]}

        keys = [array for array in list(interp_dict.keys()) if array != energy_string]
        for i in range(len(keys)):
            self.data_arrays[keys[i]] = self.data_matrix[:, i + 1]

        self.binned_arrays = {energy_string: self.en_grid}
        for i in range(len(keys) + 1):
            if list(self.data_arrays.keys())[i] != energy_string:
                self.binned_arrays[list(self.data_arrays.keys())[i]] = self.bin(self.en_grid, self.data_arrays[energy_string], self.data_arrays[list(self.data_arrays.keys())[i]])

        return self.binned_arrays



    def process_equal(self, interp_dict, energy_string = 'energy', delta_en = 2):
        E = interp_dict[energy_string][:, 1]
        df = pd.DataFrame({k: v[:, 1] for k, v in interp_dict.items()}).sort_values(energy_string)
        self.data_arrays = df
        en_grid = self.energy_grid_equal(df[energy_string], delta_en)
        self.en_grid = en_grid
        convo_mat = _gen_convolution_bin_matrix(en_grid, E)
        ret = {k: convo_mat @ v.values for k, v in df.items() if k != energy_string}
        ret[energy_string] = en_grid
        self.binned_eq_arrays = ret
        return ret


    def average_points(self, matrix, energy_column = 0):
        i = 0
        listenergy = []
        indexes = list(range(len(matrix[0])))
        indexes.remove(energy_column)
        lists = [list() for i in range(len(indexes))]

        energy = matrix[:,0]
        diff = np.diff(matrix[:,0])
        diff_indexes = np.where(diff==0)[0]
        diff2 = np.diff(diff_indexes)

        import time
        while len(diff[diff==0]) > 0:
            diff_index = np.where(diff==0)[0]
            last_i = diff_index[len(diff_index) - 1] + 2
            for i in diff_index[::-1]:
                if i < last_i - 1:
                    energy = matrix[:,0]
                    condition = (energy[i] == energy)
                    energy_interval = np.extract(condition, energy)
                    energy_index = np.where(energy == energy_interval[0])[0]
                    for j in range(len(matrix[0])):
                        matrix[i, j] = np.mean(np.extract(condition, matrix[:,j]))
                    matrix = np.delete(matrix, energy_index[1:], 0)
                last_i = i
            diff = np.diff(matrix[:,0])
        
        return matrix


    def get_edge_index(self, abs):
        abs_der = np.diff(abs)
        abs_der = np.append(abs_der[0], abs_der)

        abs_der2 = np.diff(abs_der)
        abs_der2 = np.append(abs_der2[0], abs_der2)

        abs_der[0:int(len(abs_der) * 0.005)] = 0
        abs_der2[0:int(np.round(len(abs_der2) * 0.005))] = 0
        for i in range(len(abs_der)):
            # Get der max
            max_index_der = np.where(max(np.abs(abs_der)) == np.abs(abs_der))[0][0]
        
            # Get der2 max
            max_index_der2 = np.where(max(abs_der2) == abs_der2)[0][0]
        
            # Get der2 min
            min_index_der2 = np.where(min(abs_der2) == abs_der2)[0][0]
        
            if max_index_der >= min([min_index_der2, max_index_der2]) and max_index_der <= max([min_index_der2, max_index_der2]):
                print('Found the edge! (I think...)')
                return max_index_der - 1
        
            else:
                print('Still looking for the edge...')
                abs_der[min([min_index_der2, max_index_der2]) : max([min_index_der2, max_index_der2]) + 1] = 0
                abs_der2[min([min_index_der2, max_index_der2]) : max([min_index_der2, max_index_der2]) + 1] = 0

        return -1
