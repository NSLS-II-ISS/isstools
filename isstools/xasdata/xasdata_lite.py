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


def xasdata_load_dataset_from_files(db,uid):


    def load_adc_trace(filename=''):
        df=pd.DataFrame()
        keys = ['times', 'timens', 'counter', 'adc']
        if os.path.isfile(filename):
            df_raw = pd.read_table(filename, delim_whitespace=True, comment='#', names=keys, index_col=False)
            df['timestamp'] = df_raw['times'] + 1e-9 * df_raw['timens']
            df['adc'] = df_raw['adc'].apply(lambda x: (int(x, 16) >> 8) - 0x40000 if (int(x, 16) >> 8) > 0x1FFFF else int(x, 16) >> 8) * 7.62939453125e-05
            return df
        else:
            return -1

    def load_enc_trace(filename=''):
        df = pd.DataFrame()
        keys = ['times', 'timens', 'encoder', 'counter', 'di']
        if os.path.isfile(filename):
            df_raw = pd.read_table(filename, delim_whitespace=True, comment='#', names=keys, index_col=False)
            df['timestamp'] = df_raw['times'] + 1e-9 * df_raw['timens']
            df['encoder'] = df_raw['encoder'].apply(lambda x: int(x) if int(x) <= 0 else -(int(x) ^ 0xffffff - 1))
            return df
        else:
            return -1

    def load_trig_trace(filename=''):
        keys = ['times', 'timens', 'encoder', 'counter', 'di']
        if os.path.isfile(filename):
            df = pd.read_table(filename, delim_whitespace=True, comment='#', names=keys,
                               index_col=False)
            df['timestamp'] = df['times'] + 1e-9 * df['timens']
            df = df.iloc[::2]
            return df.iloc[:, [5, 3]]
        else:
            return -1

    arrays = {}
    record = db[uid]
    for stream in record['descriptors']:
        data = pd.DataFrame()
        stream_device = stream['name']
        stream_name = stream['data_keys'][stream['name']]['devname']
        stream_source = stream['data_keys'][stream['name']]['source']
        stream_file = stream['data_keys'][stream['name']]['filename']
        print(stream_file)

        if stream_source == 'pizzabox-di-file':
            data = load_trig_trace(stream_file)
        if stream_source == 'pizzabox-adc-file':
            print(stream_device)
            data = load_adc_trace(stream_file)
            stream_offset = f'{stream_device} offset'
            if stream_offset in db[uid]['start']:
                print("subtracting offset")
                data.iloc[:, 1] = data.iloc[:, 1] - record['start'][stream_offset]

        if stream_source == 'pizzabox-enc-file':
            data = load_enc_trace(stream_file)
            print(stream_name)
            if stream_name =='hhm_theta':
                data.iloc[:,1] = xray.encoder2energy(data['encoder'], 360000,
                                                       -float(record['start']['angle_offset']))
                stream_name = 'energy'
                print(stream_name)

        arrays[stream_name] = data

    return arrays


def xasdata_interpolate_dataset(dataset,key_base = 'i0'):
    interpolated_dataset = {}
    min_timestamp = max([dataset.get(key).iloc[0, 0] for key in dataset])
    max_timestamp = min([dataset.get(key).iloc[len(dataset.get(key)) - 1, 0] for key in
                         dataset if len(dataset.get(key).iloc[:, 0]) > 5])

    try:
        if key_base not in dataset.keys():
            raise ValueError('Could not find "{}" in the loaded scan. Pick another key_base'
                             ' for the interpolation.'.format(key_base))
    except ValueError as err:
        print(err.args[0], '\nAborted...')
        return

    timestamps = dataset[key_base].iloc[:,0]

    condition = timestamps < min_timestamp
    timestamps = timestamps[np.sum(condition):]

    condition = timestamps > max_timestamp
    timestamps = timestamps[: len(timestamps) - np.sum(condition)]

    for key in dataset.keys():
        if len(dataset.get(key).iloc[:, 0]) > 5 * len(timestamps):
            time = [np.mean(array) for array in np.array_split(dataset.get(key).iloc[:, 0].values, len(timestamps))]
            val = [np.mean(array) for array in np.array_split(dataset.get(key).iloc[:, 1].values, len(timestamps))]
            interpolated_dataset[key] = np.array([timestamps, np.interp(timestamps, time, val)]).transpose()
        else:
            interpolated_dataset[key] = np.array([timestamps, np.interp(timestamps, dataset.get(key).iloc[:,0].values,
                                                                        dataset.get(key).iloc[:,1])]).transpose()
    #interpolated_dataset['1'] = np.array([timestamps, np.ones(len(interpolated_dataset
    #                                                              [list(interpolated_dataset.keys())[0]]))]).transpose()
    intepolated_dataframe = pd.DataFrame(np.vstack((timestamps, np.array([interpolated_dataset[array][:, 1] for
                                                                            array in interpolated_dataset]))).transpose())
    keys = ['timestamp']
    keys.extend(interpolated_dataset.keys())
    intepolated_dataframe.columns = keys
    return intepolated_dataframe.sort_values('energy')



def xasdata_bin_dataset(interpolated_dataset, e0, edge_start, edge_end, preedge_spacing, xanes_spacing, exafs_k_spacing):

    def energy_grid(energy_range, e0, edge_start, edge_end, preedge_spacing, xanes_spacing, exafs_k_spacing):
        energy_range_lo= np.min(energy_range)
        energy_range_hi = np.max(energy_range)

        preedge = np.arange(energy_range_lo, e0 + edge_start-1, preedge_spacing)

        before_edge = np.arange(e0+edge_start,e0 + edge_start+7, 1)

        edge = np.arange(e0+edge_start+7, e0+edge_end-7, xanes_spacing)

        after_edge = np.arange( e0 + edge_end-7,e0 + edge_end, 0.7)


        eenergy = xray.k2e(xray.e2k(e0+edge_end, e0), e0)
        post_edge = np.array([])

        while (eenergy < energy_range_hi):
            kenergy = xray.e2k(eenergy, e0)
            kenergy += exafs_k_spacing
            eenergy = xray.k2e(kenergy, e0)
            post_edge = np.append(post_edge, eenergy)
        return  np.concatenate((preedge, before_edge, edge, after_edge, post_edge))



        #return np.append(np.append(preedge,before_edge, edge, after_edge), postedge)


    en_grid = energy_grid(interpolated_dataset['energy'].values, e0, edge_start, edge_end,
                          preedge_spacing, xanes_spacing, exafs_k_spacing)
    return en_grid





