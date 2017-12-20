import numpy as np
import matplotlib.pyplot as plt
import math
import os
import os.path as op
from datetime import datetime
from isstools.conversions import xray
from subprocess import call
import re
import collections
import pandas as pd
import h5py
from pathlib import Path

class XASdata:
    def __init__(self, db = None, **kwargs):
        self.energy = np.array([])
        self.data = np.array([])
        self.encoder_file = ''
        self.i0_file = ''
        self.it_file = ''
        self.ir_file = ''
        self.iff_file = ''
        self.data_manager = XASDataManager()
        self.header_read = ''
        self.db = db

    def loadADCtrace(self, filename = '', filepath = '/GPFS/xf08id/pizza_box_data/'):
        keys = ['times', 'timens', 'counter', 'adc']
        if os.path.isfile('{}{}'.format(filepath, filename)):
            df = pd.read_table('{}{}'.format(filepath, filename), delim_whitespace=True, comment='#', names=keys, index_col=False)
            df['timestamp'] = df['times'] + 1e-9 * df['timens']
            #del df['times']
            #del df['timens']
            df['adc'] = df['adc'].apply(lambda x: (int(x, 16) >> 8) - 0x40000 if (int(x, 16) >> 8) > 0x1FFFF else int(x, 16) >> 8) * 7.62939453125e-05
            return df.iloc[:, 4:1:-1]
        else:
            return -1

    def loadADCtraceDB(self, uid, stream_name):
        hdr = self.db[uid]
        dd = [_['data'] for _ in self.db.get_events(hdr, stream_name=stream_name, fill=True)]
        result = {}
        for chunk in dd:
            for key in chunk.keys():
                if key in result:
                    result[key] = np.concatenate((result[key], chunk[key]))
                    continue
                result[key] = chunk[key]
        columns = list(dd[0][stream_name][0]._asdict().keys())
        df = pd.DataFrame(result[stream_name], columns=columns)
        df['timestamp'] = df['ts_s'] + 1e-9 * df['ts_ns']
        df['adc'] = df['adc'].apply(lambda x: (x >> 8) - 0x40000 if (x >> 8) > 0x1FFFF else x >> 8) * 7.62939453125e-05
        return df

    def loadENCtrace(self, filename = '', filepath = '/GPFS/xf08id/pizza_box_data/'):
        keys = ['times', 'timens', 'encoder', 'counter', 'di']
        if os.path.isfile('{}{}'.format(filepath, filename)):
            df = pd.read_table('{}{}'.format(filepath, filename), delim_whitespace=True, comment='#', names=keys, index_col=False)
            df['timestamp'] = df['times'] + 1e-9 * df['timens']
            df['encoder'] = df['encoder'].apply(lambda x: int(x) if int(x) <= 0 else -(int(x) ^ 0xffffff - 1))
            return df.iloc[:, [5, 2]]
        else:
            return -1

    def loadENCtraceDB(self, uid, stream_name):
        hdr = self.db[uid]
        dd = [_['data'] for _ in self.db.get_events(hdr, stream_name=stream_name, fill=True)]
        result = {}
        for chunk in dd:
            for key in chunk.keys():
                if key in result:
                    result[key] = np.concatenate((result[key], chunk[key]))
                    continue
                result[key] = chunk[key]
        columns = list(dd[0][stream_name][0]._asdict().keys())
        df = pd.DataFrame(result[stream_name], columns=columns)
        df['timestamp'] = df['ts_s'] + 1e-9 * df['ts_ns']
        df['encoder'] = df['encoder'].apply(lambda x: x if x <= 0 else -(x ^ 0xffffff - 1))
        return df.iloc[:, [5, 2]]


    def loadTRIGtrace(self, filename = '', filepath = '/GPFS/xf08id/pizza_box_data/'):
        keys = ['times', 'timens', 'encoder', 'counter', 'di']
        if os.path.isfile('{}{}'.format(filepath, filename)):
            df = pd.read_table('{}{}'.format(filepath, filename), delim_whitespace=True, comment='#', names=keys, index_col=False)
            df['timestamp'] = df['times'] + 1e-9 * df['timens']
            df = df.iloc[::2]
            #df = df[df['counter'] % 2 == 0]
            return df.iloc[:, [5, 3]]
        else:
            return -1

    def loadTRIGtraceDB(self, uid, stream_name):
        hdr = self.db[uid]
        dd = [_['data'] for _ in self.db.get_events(hdr, stream_name=stream_name, fill=True)]
        result = {}
        for chunk in dd:
            for key in chunk.keys():
                if key in result:
                    result[key] = np.concatenate((result[key], chunk[key]))
                    continue
                result[key] = chunk[key]
        columns = list(dd[0][stream_name][0]._asdict().keys())
        df = pd.DataFrame(result[stream_name], columns=columns)
        df['timestamp'] = df['ts_s'] + 1e-9 * df['ts_ns']
        df = df.iloc[::2]
        return df.iloc[:, [5, 3]]


    def read_header(self, filename):
        test = ''
        line = '#'
        with open(filename) as myfile:
            while line[0] == '#':
                line = next(myfile)
                test += line
        return test[:-len(line)]


class XASdataGeneric(XASdata):
    def __init__(self, pulses_per_deg, db = None, db_analysis = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.arrays = {}
        self.interp_arrays = {}
        self.db = db
        self.db_analysis = db_analysis
        self.pulses_per_deg = pulses_per_deg
        #if self.db is None:
        #    print('The databroker was not passed as argument to the parser.\nSome features will be disabled.')
        self.uid = ''

    def process(self, uid):
        self.load(uid)
        self.uid = uid
        self.interpolate()

    def load(self, uid):
        #if self.db is None:
        #    raise Exception('The databroker was not passed as argument to the parser. This feature is disabled.')
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
                    if i['name'] + ' offset' in self.db[uid]['start'] and type(data) == pd.core.frame.DataFrame:
                        data.iloc[:, 1] = data.iloc[:, 1] - self.db[uid]['start'][i['name'] + ' offset']
                if i['data_keys'][i['name']]['source'] == 'pizzabox-enc-file':
                    data = self.loadENCtrace(i['data_keys'][i['name']]['filename'], '')
                #if type(data) == np.ndarray:
                self.arrays[name] = data

        if has_encoder is not False:
            energy = self.arrays.get(has_encoder).copy()
            if 'angle_offset' in self.db[uid]['start']:
                energy.iloc[:, 1] = xray.encoder2energy(energy.iloc[:, 1], self.pulses_per_deg, -float(self.db[uid]['start']['angle_offset']))
                energy.columns = ['timestamp', 'energy']
            del self.arrays[has_encoder]
            self.arrays['energy'] = energy

    def loadDB(self, uid):
        # if self.db is None:
        #    raise Exception('The databroker was not passed as argument to the parser. This feature is disabled.')
        self.arrays = {}
        self.interp_arrays = {}
        self.uid = uid
        has_encoder = False
        for i in self.db[uid]['descriptors']:
            stream_name = i['name']
            name = i['name']
            if name == 'pb9_enc1' or name == 'hhm_theta':
                has_encoder = name
            if 'devname' in i['data_keys'][i['name']]:
                name = i['data_keys'][i['name']]['devname']
                if name == 'hhm_theta':
                    has_encoder = name

            if i['data_keys'][i['name']]['source'] == 'pizzabox-di-file':
                data = self.loadTRIGtraceDB(uid, stream_name)
            if i['data_keys'][i['name']]['source'] == 'pizzabox-adc-file':
                data = self.loadADCtraceDB(uid, stream_name)
                if i['name'] + ' offset' in self.db[uid]['start'] and type(data) == pd.core.frame.DataFrame:
                    data.iloc[:, 1] = data.iloc[:, 1] - self.db[uid]['start'][i['name'] + ' offset']
            if i['data_keys'][i['name']]['source'] == 'pizzabox-enc-file':
                data = self.loadENCtraceDB(uid, stream_name)
            # if type(data) == np.ndarray:
            self.arrays[name] = data

        if has_encoder is not False:
            energy = self.arrays.get(has_encoder).copy()
            if 'angle_offset' in self.db[uid]['start']:
                energy.iloc[:, 1] = xray.encoder2energy(energy.iloc[:, 1], self.pulses_per_deg,
                                                        -float(self.db[uid]['start']['angle_offset']))
                energy.columns = ['timestamp', 'energy']
            del self.arrays[has_encoder]
            self.arrays['energy'] = energy

    def read_header(self, filename):
        if filename[-3:] == 'txt' or filename[-3:] == 'dat':
            test = ''
            line = '#'
            with open(filename) as myfile:
                while line[0] == '#':
                    line = next(myfile)
                    test += line
            return test[:-len(line)]

        elif filename[-4:] == 'hdf5':
            f = h5py.File(filename, mode='r')
            header = dict(f.attrs)
            f.close()
            del header['start_time']
            del header['stop_time']
            del header['name']
            header = '\n'.join([f'# {key}: {header[key]}' for key in header]) + '\n#\n#'
            return header


    def loadInterpFile(self, filename):
        self.arrays = {}
        self.interp_arrays = {}

        if not op.exists(filename):
            raise IOError(f'The requested file {filename} does not exist.')

        header = self.read_header(filename)
        self.uid = header[header.find('UID') + 5: header.find('\n', header.find('UID'))]

        keys = re.sub('  +', '  ', header[header.rfind('# '):][2:-1]).split('  ')
        timestamp_index = -1
        if 'Timestamp (s)' in keys:
            timestamp_index = keys.index('Timestamp (s)')
        elif 'timestamp' in keys:
            timestamp_index = keys.index('timestamp')

        df = pd.read_table(filename, delim_whitespace=True, comment='#', names=keys, index_col=False).sort_values(keys[1])
        df['1'] = pd.Series(np.ones(len(df.iloc[:, 0])), index=df.index)
        self.interp_df = df
        for index, key in enumerate(df.keys()):
            if index != timestamp_index:
                self.interp_arrays[key] = np.array([df.iloc[:, timestamp_index].values, df.iloc[:, index]]).transpose()
        self.interp_arrays['1'] = np.array([df.iloc[:, timestamp_index].values, np.ones(len(df.iloc[:, 0]))]).transpose()

    def loadInterpFileHDF5(self, filename):
        self.arrays = {}
        self.interp_arrays = {}

        if not op.exists(filename):
            raise IOError(f'The requested file {filename} does not exist.')

        # opening a file:
        f = h5py.File(filename, mode='r')
        df = pd.DataFrame({key: value for key, value in zip(f.keys(), f.values())})
        self.interp_df = df
        self.md = dict(f.attrs)
        self.uid = self.md['real_uid']
        #for attr in f.attrs:
        #    print(attr, f.attrs[attr])

        keys = list(f.keys())
        if 'timestamp' in keys:
            timestamp_index = keys.index('timestamp')
        for index, key in enumerate(df.keys()):
            if index != timestamp_index:
                self.interp_arrays[key] = np.array([df.iloc[:, timestamp_index].values, df.iloc[:, index]]).transpose()
        self.interp_arrays['1'] = np.array([df.iloc[:, timestamp_index].values, np.ones(len(df.iloc[:, 0]))]).transpose()

        f.close()


    def loadInterpFromDB(self, uid):
        if self.db_analysis is None:
            raise IOError('No db_analysis was passed to the parser in the initialization')

        hdr = self.db_analysis[uid]
        dd = [_['data'] for _ in self.db_analysis.get_events(hdr, stream_name='interpolated', fill=True)]
        result = {}
        for chunk in [chunk['interpolated'] for chunk in dd]:
            for key in chunk.keys():
                if key in result:
                    result[key] = np.concatenate((result[key], chunk[key]))
                    continue
                result[key] = chunk[key]
        df = pd.DataFrame(result)
        if 'Ones' in df.columns:
            new_keys = list(df.columns)
            new_keys[new_keys.index('Ones')] = '1'
            df.columns = new_keys

        self.interp_df = df

        keys = list(df.keys())
        if 'timestamp' in keys:
            timestamp_index = keys.index('timestamp')
        for index, key in enumerate(df.keys()):
            if index != timestamp_index:
                self.interp_arrays[key] = np.array([df.iloc[:, timestamp_index].values, df.iloc[:, index]]).transpose()
        self.interp_arrays['1'] = np.array([df.iloc[:, timestamp_index].values, np.ones(len(df.iloc[:, 0]))]).transpose()


    def interpolate(self, key_base = 'i0'):
        min_timestamp = max([self.arrays.get(key).iloc[0, 0] for key in self.arrays])
        max_timestamp = min([self.arrays.get(key).iloc[len(self.arrays.get(key)) - 1, 0] for key in
                             self.arrays if len(self.arrays.get(key).iloc[:, 0]) > 5])

        try:
            if key_base not in self.arrays.keys():
                raise ValueError('Could not find "{}" in the loaded scan. Pick another key_base for the interpolation.'.format(key_base))
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return

        timestamps = self.arrays[key_base].iloc[:,0]

        condition = timestamps < min_timestamp
        timestamps = timestamps[np.sum(condition):]

        condition = timestamps > max_timestamp
        timestamps = timestamps[: len(timestamps) - np.sum(condition)]

        #time = [np.mean(array) for array in np.array_split(self.arrays[key_base][:,0], len(timestamps))]

        for key in self.arrays.keys():
            if len(self.arrays.get(key).iloc[:, 0]) > 5 * len(timestamps):
                time = [np.mean(array) for array in np.array_split(self.arrays.get(key).iloc[:, 0].values, len(timestamps))]
                val = [np.mean(array) for array in np.array_split(self.arrays.get(key).iloc[:, 1].values, len(timestamps))]
                self.interp_arrays[key] = np.array([timestamps, np.interp(timestamps, time, val)]).transpose()
            else:
                self.interp_arrays[key] = np.array([timestamps, np.interp(timestamps, self.arrays.get(key).iloc[:,0].values, self.arrays.get(key).iloc[:,1])]).transpose()
        self.interp_arrays['1'] = np.array([timestamps, np.ones(len(self.interp_arrays[list(self.interp_arrays.keys())[0]]))]).transpose()
        self.interp_df = pd.DataFrame(np.vstack((timestamps, np.array([self.interp_arrays[array][:, 1] for
                                                                       array in self.interp_arrays]))).transpose())
        keys = ['timestamp']
        keys.extend(self.interp_arrays.keys())
        self.interp_df.columns = keys


    def get_plot_info(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        pass


    def plot(self, plotting_dic = dict(), ax = plt, color = 'r', derivative = True ):
        pass

    def export_trace(self, filename, filepath = '/GPFS/xf08id/Sandbox/', overwrite = False):
        if self.db is None:
            raise Exception('The databroker was not passed as argument to the parser. This feature is disabled.')
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
        name = self.db[self.uid]['start']['name']
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
        if 'trajectory_name' in self.db[self.uid]['start']:
            trajectory_name = self.db[self.uid]['start']['trajectory_name']
        else:
            trajectory_name = ''

        if 'element' in self.db[self.uid]['start']:
            element = self.db[self.uid]['start']['element']
        else:
            element = ''

        if 'edge' in self.db[self.uid]['start']:
            edge = self.db[self.uid]['start']['edge']
        else:
            edge = ''

        if 'e0' in self.db[self.uid]['start']:
            e0 = self.db[self.uid]['start']['e0']
        else:
            e0 = ''

        cols = self.interp_df.columns.tolist()
        cols.remove('1')

        index = 1
        for pair in [['energy', 'En. (eV)'], ['i0', 'i0 (V)'], ['it', 'it(V)'], ['ir', 'ir(V)'], ['iff', 'iff(V)']]:
            if pair[0] in cols:
                cols.remove(pair[0])
                cols.insert(index, pair[0])
                index += 1
            elif pair[1] in cols:
                cols.remove(pair[1])
                cols.insert(index, pair[1])
                index += 1

        fmt = ' '.join(['%12.6f' for key in cols])
        fmt = '%17.6f ' + fmt[7:]
        header = '  '.join(cols)

        cols.append('1')
        self.interp_df = self.interp_df[cols]


        np.savetxt(fn,
                   self.interp_df.iloc[:,:-1].values,
                   fmt=fmt,
                   delimiter=" ",
                   header = header,
                   comments = '# Year: {}\n' \
                              '# Cycle: {}\n' \
                              '# SAF: {}\n' \
                              '# PI: {}\n' \
                              '# PROPOSAL: {}\n' \
                              '# Scan ID: {}\n' \
                              '# UID: {}\n' \
                              '# Comment: {}\n' \
                              '# Trajectory name: {}\n' \
                              '# Element: {}\n' \
                              '# Edge: {}\n' \
                              '# E0: {}\n' \
                              '# Start time: {}\n' \
                              '# Stop time: {}\n' \
                              '# Total time: {}\n#\n# '.format(year,
                                                               cycle,
                                                               saf,
                                                               pi,
                                                               proposal,
                                                               scan_id,
                                                               real_uid,
                                                               comment,
                                                               trajectory_name,
                                                               element,
                                                               edge,
                                                               e0,
                                                               human_start_time,
                                                               human_stop_time,
                                                               human_duration))

        call(['setfacl', '-m', 'g:iss-staff:rwX', fn])
        call(['chmod', '770', fn])
        return fn

    def export_trace_hdf5(self, filename, filepath = '/GPFS/xf08id/Sandbox/', overwrite = False):
        if self.db is None:
            raise Exception('The databroker was not passed as argument to the parser. This feature is disabled.')
        suffix = '.hdf5'
        fn = filepath + filename + suffix
        if not overwrite:
            repeat = 1
            while(os.path.isfile(fn)):
                repeat += 1
                fn = filepath + filename + '-' + str(repeat) + suffix

        md = {}

        md['pi'] = self.db[self.uid]['start']['PI']
        md['proposal'] = self.db[self.uid]['start']['PROPOSAL']
        md['saf'] = self.db[self.uid]['start']['SAF']
        md['name'] = self.db[self.uid]['start']['name']
        md['comment'] = self.db[self.uid]['start']['comment']
        md['year'] = self.db[self.uid]['start']['year']
        md['cycle'] = self.db[self.uid]['start']['cycle']
        md['scan_id'] = self.db[self.uid]['start']['scan_id']
        md['real_uid'] = self.db[self.uid]['start']['uid']
        md['start_time'] = self.db[self.uid]['start']['time']
        md['stop_time'] = self.db[self.uid]['stop']['time']
        md['human_start_time'] = str(datetime.fromtimestamp(md['start_time']).strftime('%m/%d/%Y  %H:%M:%S'))
        md['human_stop_time'] = str(datetime.fromtimestamp(md['stop_time']).strftime('%m/%d/%Y  %H:%M:%S'))
        md['human_duration'] = str(datetime.fromtimestamp(md['stop_time'] - md['start_time']).strftime('%M:%S'))
        if 'trajectory_name' in self.db[self.uid]['start']:
            md['trajectory_name'] = self.db[self.uid]['start']['trajectory_name']
        else:
            md['trajectory_name'] = ''

        if 'element' in self.db[self.uid]['start']:
            md['element'] = self.db[self.uid]['start']['element']
        else:
            md['element'] = ''

        if 'edge' in self.db[self.uid]['start']:
            md['edge'] = self.db[self.uid]['start']['edge']
        else:
            md['edge'] = ''

        if 'e0' in self.db[self.uid]['start']:
            md['e0'] = self.db[self.uid]['start']['e0']
        else:
            md['e0'] = ''

        cols = self.interp_df.columns.tolist()
        cols.remove('1')

        index = 1
        for pair in [['energy', 'En. (eV)'], ['i0', 'i0 (V)'], ['it', 'it(V)'], ['ir', 'ir(V)'], ['iff', 'iff(V)']]:
            if pair[0] in cols:
                cols.remove(pair[0])
                cols.insert(index, pair[0])
                index += 1
            elif pair[1] in cols:
                cols.remove(pair[1])
                cols.insert(index, pair[1])
                index += 1

        fmt = ' '.join(['%12.6f' for key in cols])
        fmt = '%17.6f ' + fmt[7:]
        header = '  '.join(cols)

        cols.append('1')
        self.interp_df = self.interp_df[cols]

        f = h5py.File(fn, mode='w')
        for key in self.interp_df.keys():
            dset = f.create_dataset(key, data=self.interp_df[key], compression='gzip')
        for data in md:
            f.attrs[data] = md[data]
        f.close()

        # opening a file:
        # import h5py
        # import pandas as pd
        # f = h5py.File('/GPFS/xf08id/Sandbox/test.hdf5', mode='r')
        # df = pd.DataFrame({key: value for key, value in zip(f.keys(), f.values())})
        # for attr in f.attrs:
        #     print(attr, f.attrs[attr]) 
        # f.close()

        call(['setfacl', '-m', 'g:iss-staff:rwX', fn])
        call(['chmod', '770', fn])
        return fn

    def get_energy_string(self, possibilities = ['energy', 'En. (eV)']):

        try:
            energy_string = ''
            for string in possibilities:
                if string in self.interp_df.keys():
                    return string
            raise ValueError('Could not find energy' \
                             ' in the header of the' \
                             ' loaded scan. Sorry for that.')
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return -1



    def bin_equal(self, en_spacing = 2):

        try:
            energy_string = ''
            if 'energy' in self.interp_df.keys():
                energy_string = 'energy'
            elif 'En. (eV)' in self.interp_df.keys():
                energy_string = 'En. (eV)'
            else:
                raise ValueError('Could not find energy' \
                                 ' in the header of the' \
                                 ' loaded scan. Sorry for that.')
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return -1

        return self.data_manager.process_equal(self.interp_df,
                                               energy_string = energy_string,
                                               delta_en = en_spacing)

    def bin(self, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk):

        try:
            energy_string = ''
            if 'energy' in self.interp_df.keys():
                energy_string = 'energy'
            elif 'En. (eV)' in self.interp_df.keys():
                energy_string = 'En. (eV)'
            else:
                raise ValueError('Could not find energy' \
                                 ' in the header of the' \
                                 ' loaded scan. Sorry for that.')
        except ValueError as err:
            print(err.args[0], '\nAborted...')
            return

        return self.data_manager.process(self.interp_df,
                                         e0, edge_start, edge_end,
                                         preedge_spacing, xanes,
                                         exafsk, energy_string = energy_string)








import numexpr as ne
# Constants for converting from hwhm -> gaussian parameters
GAUSS_SIGMA_FACTOR = 1 / (2*(2*np.log(2))**.5)

def generate_sampled_gauss_window(x, fwhm, x0):
    sigma = fwhm * GAUSS_SIGMA_FACTOR
    a = 1 / (sigma * (2*np.pi)**.5)
    data_y = ne.evaluate('a * exp(-.5 * ((x - x0) / sigma) ** 2)')
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

    def get_k_data(self, e0, edge_end, exafsk, y_data, interp_dict, en_orig, data_orig, pow = 1, energy_string = 'energy'):
        df = pd.DataFrame({k: v[:, 1] for k, v in interp_dict.items()}).sort_values(energy_string)
        energy_array = df[energy_string].values
        e_interval = self.get_k_interval(energy_array, e0, e0 + edge_end, exafsk)
        k_interval = xray.e2k(e_interval, e0) #e0 + edge_end)

        condition = en_orig >= e0 + edge_end 
        en_orig = np.extract(condition, en_orig)
        data_orig = np.extract(condition, data_orig)
        try:
            polyfit = np.polyfit(en_orig, data_orig, 2) #2 is ok?
        except Exception as exc:
            print(exc)
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
        derivative = np.append(derivative[0], derivative)
        return derivative


    def export_dat(self, filename, e0_bin):
        for extension in ['txt', 'dat', 'hdf5']:
            if op.isfile(filename + extension):
                filename = filename + extension
                break

        comments = XASdataGeneric.read_header(None, filename)
        comments = comments[0: comments.rfind('#')] + '# '
        comments = comments[:comments.rfind('#', 0, -2)] + f'# e0_bin: {e0_bin}\n#\n#'

        filename = filename[:filename.rfind('.') + 1] + 'dat'
        filename = XASDataManager.get_new_filename(filename)

        cols = self.binned_df.columns.tolist()
        cols.remove('1')
        cols.remove('timestamp')

        index = 0
        for pair in [['energy', 'En. (eV)'], ['i0', 'i0 (V)'], ['it', 'it(V)'], ['ir', 'ir(V)'], ['iff', 'iff(V)']]:
            if pair[0] in cols:
                cols.remove(pair[0])
                cols.insert(index, pair[0])
                index += 1
            elif pair[1] in cols:
                cols.remove(pair[1])
                cols.insert(index, pair[1])
                index += 1

        fmt = ' '.join(['%12.6f' for key in cols])
        header = '  '.join(cols)

        cols.append('timestamp')
        cols.append('1')
        self.binned_df = self.binned_df[cols]

        np.savetxt(filename,
                   self.binned_df.iloc[:,:-2].values,
                   fmt=fmt,
                   delimiter=" ",
                   header = header,
                   comments = comments)
        call(['setfacl', '-m', 'g:iss-staff:rwX', filename])
        call(['chmod', '770', filename])
        return filename

    def get_new_filename(filename):
        for extension in ['.txt', '.dat', '.hdf5']:
            if filename[-len(extension):] == extension:
                filename = filename[:-len(extension)]
                break

        if op.exists(Path(filename + extension)):
            iterator = 2

            while True:
                new_filename = f'{filename}-{iterator}{extension}'
                if not op.isfile(new_filename):
                    return new_filename
                iterator += 1
        return filename

    def process(self, interp_df, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk, energy_string = 'energy'):
        if len(interp_df[list(interp_df.keys())[0]].shape) > 1:
            df = interp_df.copy().sort_values(energy_string)#pd.DataFrame({k: v[:, 1] for k, v in interp_dict.items()}).sort_values(energy_string)
        else:
            df = interp_df.copy().sort_values(energy_string)#pd.DataFrame({k: v for k, v in interp_dict.items()}).sort_values(energy_string)
        self.data_arrays = df
        en_grid = self.energy_grid(df[energy_string].values, e0, edge_start, edge_end, preedge_spacing, xanes, exafsk)
        self.en_grid = en_grid
        convo_mat = _gen_convolution_bin_matrix(en_grid, df[energy_string].values)
        ret = {k: convo_mat @ v.values for k, v in df.items() if k != energy_string}
        ret[energy_string] = en_grid
        self.binned_arrays = ret
        self.binned_df = pd.DataFrame(ret)
        return self.binned_df


    def process_equal(self, interp_df, energy_string = 'energy', delta_en = 2):
        df = interp_df.copy().sort_values(energy_string)
        self.data_arrays = df
        en_grid_eq = self.energy_grid_equal(df[energy_string], delta_en)
        self.en_grid_eq = en_grid_eq
        convo_mat = _gen_convolution_bin_matrix(en_grid_eq, df[energy_string].values)
        ret = {k: convo_mat @ v.values for k, v in df.items() if k != energy_string}
        ret[energy_string] = en_grid_eq
        self.binned_eq_arrays = ret
        self.binned_eq_df = pd.DataFrame(ret)
        return self.binned_eq_df


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




