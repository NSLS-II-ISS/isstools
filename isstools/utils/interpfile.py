import os.path as op
import re
import pandas as pd
import numpy as np

def loadInterpFile(filename):
    ''' load the interp file'''
    arrays = {}
    interp_arrays = {}

    if not op.exists(filename):
        raise IOError(f'The requested file {filename} does not exist.')

    header = read_header(filename)

    keys = header[-1].split()
    timestamp_index = -1
    if 'Timestamp (s)' in keys:
        timestamp_index = keys.index('Timestamp (s)')
    elif 'timestamp' in keys:
        timestamp_index = keys.index('timestamp')

    df = pd.read_table(filename, delim_whitespace=True, comment='#', names=keys, index_col=False).sort_values(keys[1])
    df['1'] = pd.Series(np.ones(len(df.iloc[:, 0])), index=df.index)
    interp_df = df
    return interp_df

def read_header(filename):
    line = '#'
    lines = list()
    with open(filename) as myfile:
        for line in myfile:
            if line[0] == '#':
                lines.append(line[1:].strip())
            else:
                break
    return lines
