from datetime import datetime
import os
from subprocess import call
import numpy as np



def validate_file_exists(path_to_file):
    if os.path.isfile(path_to_file):
        (path, extension) = os.path.splitext(path_to_file)
    if op.exists(Path(filename + extension)):
        iterator = 2

        while True:
            new_filename = f'{filename}-{iterator}{extension}'
            if not op.isfile(new_filename):
                return new_filename
            iterator += 1
    return filename + extension

def validate_path_exists(path):
    if not os.path.isdir(path):
        os.mkdir(path)
    else:
        print('...........Path exists')


def save_interpolated_df_as_file(db, uid, df):
    path_to_file = db[uid].start['interp_filename']
    (path, filename) = os.path.split(path_to_file)
    validate_path_exists(path)
    #path_to_file = validate_file_exists(path_to_file)

    pi = db[uid]['start']['PI']
    proposal = db[uid]['start']['PROPOSAL']
    saf = db[uid]['start']['SAF']

    comment = db[uid]['start']['comment']
    year = db[uid]['start']['year']
    cycle = db[uid]['start']['cycle']
    scan_id = db[uid]['start']['scan_id']
    real_uid = db[uid]['start']['uid']
    start_time = db[uid]['start']['time']
    stop_time = db[uid]['stop']['time']
    human_start_time = str(datetime.fromtimestamp(start_time).strftime('%m/%d/%Y  %H:%M:%S'))
    human_stop_time = str(datetime.fromtimestamp(stop_time).strftime('%m/%d/%Y  %H:%M:%S'))
    human_duration = str(datetime.fromtimestamp(stop_time - start_time).strftime('%M:%S'))

    if 'trajectory_name' in db[uid]['start']:
        trajectory_name = db[uid]['start']['trajectory_name']
    else:
        trajectory_name = ''

    if 'element' in db[uid]['start']:
        element = db[uid]['start']['element']
    else:
        element = ''

    if 'edge' in db[uid]['start']:
        edge = db[uid]['start']['edge']
    else:
        edge = ''

    if 'e0' in db[uid]['start']:
        e0 = db[uid]['start']['e0']
    else:
        e0 = ''

    cols = df.columns.tolist()
    print(cols)
    fmt = '%17.6f ' + '%12.6f ' + (' '.join(['%12.6e' for i in range(len(cols)-2)]))
    header = '  '.join(cols)

    print(f'Format {fmt}')

    df = df[cols]

    np.savetxt(path_to_file,
               df.values,
               fmt=fmt,
               delimiter=" ",
               header=header,
               comments='# Year: {}\n' \
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

    print("changing permissions to 774")
    call(['chmod', '774', path_to_file])

    # call(['setfacl', '-m', 'g:iss-staff:rwX', fn])
    return path_to_file