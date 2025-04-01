import numpy as np


bender_current_position = bender.pos.user_readback.get()

bender_positions = bender_current_position + np.arange(-15, 20, 5)
x = xlive_gui.widget_run

for bender_position in bender_positions:
    RE(bps.mv(bender.pos, bender_position))
    RE(bps.sleep(3))
    loading = bender.load_cell.get()
    x.parameter_values[0].setText(f'Pd foil - {loading} N - {bender_position} um')
    x.run_scan()



###############################################


def wakeup():
    cur_energy = hhm.energy.user_readback.get()
    for i in range(3):
        RE(bps.mv(hhm.energy, 10000))
        RE(bps.sleep(3))
        RE(bps.mv(hhm.energy, 5000))
        RE(bps.sleep(3))
    RE(bps.mv(hhm.energy, cur_energy))




xes_2perc = np.zeros(energy.size)
_xes = np.array([x[-i].mu for i in range(1+25, 26+25)]).T
_bkg = np.array([x[-i].mu for i in range(1, 26)]).T
for i in range(energy.size):
    this_xes = _xes[i, :]
    this_bkg = _bkg[i, :]
    mask = this_xes < 5.2
    xes_2perc[i] = np.mean((this_xes - this_bkg)[mask])

xes_2perc_norm = xes_2perc/np.max(xes_2perc)


def subscription(value, old_value, **kwargs):
    print(old_value, value)

hhm.fb_heartbeat.subscribe(subscription)


############

tt = hhm_feedback._timestamps.copy()
# mask = tt != 0
tt -= tt[0]
mask = tt > 154.5

plt.figure()
plt.subplot(211)
plt.plot(tt[mask], hhm_feedback._centers[mask])

plt.subplot(212)
plt.plot(tt[mask], hhm_feedback._pitch_vals[mask])
# plt.plot(hhm_feedback._pitch_vals[mask], hhm_feedback._centers[mask])

###############################################

#    energy     hhmy     hhrmy                              hhmy uid
# 0    4800  9.71275  44.32849  b15096a9-b8c2-4d80-9b96-9e77c8d11db3
# 1    5000  9.62515  44.47808  d1e1d57a-993d-4544-bab9-1728bb1244d4
# 2    6000  9.36450  44.47766  eba4afe2-1979-4052-b59f-8293213d5a8b
# 3    7000  9.20200  44.47720  823fcc86-ce58-4b62-af8b-fb9d0bd61fed
# 4    8000  9.09365  45.07057  661f371e-450f-4104-8929-0d823f48c36f
# 5    9000  9.03125  44.52051  262ca0b4-8fb3-4c3f-ab4e-50190e2f6c14
# 6   10000  8.99405  44.49507  9be0cad8-7a92-4c6d-96ae-89b08968369c
# 7   11000  8.93730  44.49468  d4723408-3fbc-41d5-aacc-70622e4ace2f
# 8   12000  8.93780  44.44428  776ac759-1e46-4e09-9e05-c93649e9e079

# energy   hhmy     hhrmy                               hhmy uid
#  4800  9.71275  44.32849  b15096a9-b8c2-4d80-9b96-9e77c8d11db3
#  5000  9.62515  44.47808  d1e1d57a-993d-4544-bab9-1728bb1244d4
#  6000  9.36450  44.47766  eba4afe2-1979-4052-b59f-8293213d5a8b
#  7000  9.20200  44.47720  823fcc86-ce58-4b62-af8b-fb9d0bd61fed
#  8000  9.09365  45.07057  661f371e-450f-4104-8929-0d823f48c36f
#  9000  9.03125  44.52051  262ca0b4-8fb3-4c3f-ab4e-50190e2f6c14
# 10000  8.99405  44.49507  9be0cad8-7a92-4c6d-96ae-89b08968369c
# 11000  8.93730  44.49468  d4723408-3fbc-41d5-aacc-70622e4ace2f
# 12000  8.93780  44.44428  776ac759-1e46-4e09-9e05-c93649e9e079
# 13000  8.86945  44.32427  8fb01e5c-a79b-4fe2-8f51-ed4695f4ea90
# 15000  8.84420  44.22385  f54ca7d6-50bf-4b6f-923b-1c4f346f5fcb
# 17500  8.68795  44.60157  65a901c7-26b7-412b-b854-cba17fc7cf21
# 20000  8.70085  44.15118  1fca3c7f-de67-4ab3-9798-f350ae2927b3
# 22500  8.62675  44.10076  6cc04ec4-3891-49b0-90c1-49fafb263999
# 25000  8.65015  44.10035  4c90368e-d476-46f4-86d1-21fd582e9959
# 27500  8.55135  44.12496  7f425a01-7fe6-485d-8c8d-1ef6fba2c0b4
# 30000  8.55645  44.04957  c09dd8b9-dd39-4135-9f63-b9104725e05f


#

# df = pd.read_json('/nsls2/xf08id/Sandbox/Beamline_components/2021_09_09_beamline_tabulation/beamline_hhmy_hhrmy_tabulation.json')
# df2 = pd.read_json('/nsls2/xf08id/Sandbox/Beamline_components/2021_09_09_beamline_tabulation/beamline_hhmy_hhrmy_tabulation_high_energies.json')


df = pd.read_json('/nsls2/xf08id/Sandbox/Beamline_components/2022_02_10_beamline_tabulation/beamline_hhmy_tabulation_att2.json')
df2 = pd.read_json('/nsls2/xf08id/Sandbox/Beamline_components/2022_02_10_beamline_tabulation/beamline_hhmy_tabulation_att2_high_energies.json')
df_all = df.append(df2)

# df = pd.read_json('/nsls2/data/iss/legacy/xf08id/calibration/beamline_hhmy_tabulation_2022_05_19.json')
# df2 = pd.read_json('/nsls2/data/iss/legacy/xf08id/calibration/beamline_hhmy_tabulation_2022_05_19_high_energies.json')
# df3 = pd.read_json('/nsls2/data/iss/legacy/xf08id/calibration/beamline_hhmy_tabulation_2022_05_19_high_energies_2.json')
# df_all = df.append(df2)
# df_all = df_all.append(df3)

energy = df_all.energy.values
hhmy = df_all.hhmy.values
from xas.xray import energy2angle

def get_matrix_from_energy(energy_in, offset=0):
    theta_deg = energy2angle(energy_in)
    V = 1 / np.cos(np.deg2rad(theta_deg - offset))
    A = np.vstack((V, energy_in, np.ones(V.size))).T
    return A

def fit_hhmy(offset=0):

    A = get_matrix_from_energy(energy, offset=offset)
    energy_grid = np.linspace(4000, 33000, 1001)
    A_grid = get_matrix_from_energy(energy_grid, offset=offset)
    c, _, _, _ = np.linalg.lstsq(A, hhmy, rcond=-1)
    hhmy_fit = A @ c
    hhmy_fit_grid = A_grid @ c

    p = np.polyfit(energy, hhmy, 2)
    hhmy_fit_grid_poly = np.polyval(p, energy_grid)

    plt.figure(1)
    # plt.clf()
    plt.plot(energy, hhmy, 'm.')
    plt.plot(energy_grid, hhmy_fit_grid, 'b-')
    # plt.plot(energy_grid, hhmy_fit_grid_poly, 'b-')

fit_hhmy(offset=0)


###
mylist = []
for element in elements_data:
    sym = element['symbol']
    edges = ['K', 'L1', 'L2', 'L3']
    for edge in edges:
        lines = xraydb.xray_lines(sym, edge)

        d = {'symbol': sym, 'name': element['name']}

        if 'Ka1' in lines.keys():
            energy = 2/3 * lines['Ka1'].energy + 1/3 * lines['Ka2'].energy
            energy = 2 / 3 * lines['Ka1'].energy + 1 / 3 * lines['Ka2'].energy
            d['Ka'] = energy
            d['Kb1'] = lines['Kb1'].energy
        elif 'La1' in lines.keys():
            energy = lines['La1'].energy
            d['La1'] = energy
        else:
            energy = 0
        # print(sym, edge, energy)

        if (energy > 4500) and (energy < 32000):
            print(sym, edge, energy)
            mylist.append(d)

with open('/home/xf08id/Repos/isstools/isstools/fluorescence_lines.json', 'w') as f:
    f.write(json.dumps(mylist))




        # for  key, line in lines.items():

################

uids = ('41026319-8d79-4736-b9cd-46c96fcebc7a',
 '16a7cece-aeae-4697-8e04-7c23b4e72b5d',
 '03af26a7-bc91-4982-a0e7-d1b2f4fe25e9',
 '5c62ba14-88be-4dd1-8ebc-99f7135847e6',
 'dc543da3-194f-4294-8270-23ded48c8b62',
 'b9e9a783-c1d3-4497-b13f-0ab2a252b9ad',
 '3894aa1d-52a9-4d64-a546-f45ba879d679',
 'b92041f8-1c91-452e-8151-31b001092944',
 '4da971b2-3915-438c-9e28-ea58acd79c30',
 '22499df4-ccc7-4c1f-a20a-d0498d6c0d34',
 '8d21733a-fb20-49e3-a0ae-9388c7e8fdce',
 'f6938a2e-f7f2-4051-8a19-75d2184482ff',
 'd6a84011-0502-4242-85f4-0b7bc860bbbb',
 '387d914a-a9d4-4015-8f5d-cb69bda7b36e',
 '41560a18-efda-4bb9-a4bc-da6dd8eb7378',
 '3781ac8a-b5a6-442f-b0cd-478fcd62b5c5')


from xas.fitting import fit_gaussian_with_estimation, fit_gaussian

energies = []
peaks = []

plt.figure()

for uid in uids:
    t = db[uid].table(fill=True)
    data = []
    energy = t.hhm_energy
    energies.append(energy.values)


    these_peaks = []
    for i in range(4):
        ch = f'ch_{i+1}'
        data =t.xs_channel1[1][ch]
        x = np.arange(data.size)
        # roi_idx = []
        roi_min = int(energy/10)-20
        roi_max = int(energy/10)+20
        roi_peak = roi_min + np.argmax(data[roi_min : roi_max])

        x_roi = x[roi_peak-20 : roi_peak+20]
        data_roi = data[roi_peak-20 : roi_peak+20]

        # _x = fit_gaussian_with_estimation(x_roi, data_roi)
        _x = fit_gaussian(x_roi, data_roi/data_roi.max(), roi_peak, 35)

        these_peaks.append(_x[0], )

        plt.plot(x_roi, _x[-1], 'k-')
        plt.plot(x_roi, data_roi/data_roi.max())



        plt.vlines(_x[0], 0, 1, colors='k')

    peaks.append(these_peaks)


peaks_array = np.array(peaks)
E = np.array(energies).ravel()

c_k, _, _, _ = np.linalg.lstsq(E[:, None], peaks_array, rcond=-1)
c_kb, _, _, _ = np.linalg.lstsq(np.hstack((E[:, None], np.ones((E.size, 1)))), peaks_array, rcond=-1)

E_fit = np.linspace(0, E.max(), 101)

peaks_k = E[:, None] @ c_k
peaks_kb = np.hstack((E[:, None], np.ones((E.size, 1)))) @ c_kb

peaks_fit_k = E_fit[:, None] @ c_k
peaks_fit_kb = np.hstack((E_fit[:, None], np.ones((E_fit.size, 1)))) @ c_kb

plt.figure()

plt.subplot(211)
plt.plot(E, peaks_array*10, '.-')
plt.plot(E_fit, peaks_fit*10, 'k-')
plt.axis('square')


plt.subplot(212)

plt.plot(E, (peaks_array - peaks_k)*10, 'k.-')
plt.plot(E, (peaks_array - peaks_kb)*10, 'r.-')


xs_calibration = pd.DataFrame({'energy' : E, 'ch_1' : peaks_array[:, 0],
                                               'ch_2': peaks_array[:, 1],
                                               'ch_3': peaks_array[:, 2],
                                               'ch_4': peaks_array[:, 3]})




uids = ( '3e35770b-8052-4f70-aa70-07e1923b01de',
         'bc3c6560-4af9-4793-84bc-cb7265abda17',
         'a363ac15-2f8b-4abd-8f1e-937d41dd3452',
         'a31b9d88-4b06-4992-8abd-40af3f0d9c78',
         '995c01f9-6768-4fa6-82c9-0183b108b97f',
         '1cb70050-a16e-4d70-b099-562cf51b9554')




plt.figure()
ch1_offset = 10.358600616455078 # apb_ave.ch1_offset.get()

i0 = []
peaks_i0 = []
amps_i0 = []
totals_i0 = []
for uid in uids:
    t = db[uid].table(fill=True)
    data = []
    i0.append(t.apb_ave_ch1[1] - ch1_offset)

    these_peaks = []
    these_amps = []
    these_totals = []
    for i in range(4):
        ch = f'ch_{i+1}'
        data =t.xs_channel1[1][ch]
        x = np.arange(data.size)
        # roi_idx = []
        droi_lo = 20
        droi_hi = 20
        roi_min = int(24350/10)-droi_lo
        roi_max = int(24350/10)+droi_hi
        roi_peak = roi_min + np.argmax(data[roi_min : roi_max])

        x_roi = x[roi_peak-droi_lo : roi_peak+droi_hi]
        data_roi = data[roi_peak-droi_lo : roi_peak+droi_hi]
        peak_intensity = np.sum(data_roi)
        total_intensity = np.sum(data)
        # _x = fit_gaussian_with_estimation(x_roi, data_roi)
        _x = fit_gaussian(x_roi, data_roi/data_roi.max(), roi_peak, 35)

        these_peaks.append(_x[0])
        these_amps.append(peak_intensity)
        these_totals.append(total_intensity)

        plt.plot(x_roi, _x[-1], 'k-')
        plt.plot(x_roi, data_roi/data_roi.max())



        plt.vlines(_x[0], 0, 1, colors='k')

    peaks_i0.append(these_peaks)
    amps_i0.append(these_amps)
    totals_i0.append(these_totals)

peaks_i0_arr = np.array(peaks_i0)
amps_i0_arr = np.array(amps_i0)
totals_i0_arr = np.array(totals_i0)
i0_arr = np.array(i0)

plt.figure();

plt.plot(i0_arr, peaks_i0_arr*10, '.-')
plt.ylabel('Peak positoion')

# plt.plot(i0_arr, amps_i0_arr, '.-')
# plt.ylabel('Elastic intensity')

# plt.plot(i0_arr, totals_i0_arr, '.-')
# plt.ylabel('Total counts')

# plt.xlabel('I0')

plt.figure();
plt.plot(totals_i0_arr, amps_i0_arr, '.-')
plt.xlabel('Total counts')
plt.ylabel('Elastic intensity')










#################


def infinite_plan():
    itr = 1
    value = 0.5
    while True:
        print(itr)
        yield from bps.mvr(hhrm.y, value)
        value *= -1
        itr += 1


######################################
# give the scans names
sample_name_list = ['Co3MnO4 VTC try1', 'Co4O4 VTC try3']
# sample_name_list = ['Co4O4Ground VTC try2']
# give the corrresponding raster files
#sample_reg_path_list = ['/nsls2/xf08id/users/2021/2/308230/Co4O4_raster.json', '/nsls2/xf08id/users/2021/2/308230/Co4Mn4_raster.json']
# sample_reg_path_list = ['/nsls2/xf08id/users/2021/2/308230/Co4O4Ground_raster.json']

sample_reg_path_list = ['/nsls2/xf08id/users/2021/2/308230/Co3MnO4_try2_raster.json',
                        '/nsls2/xf08id/users/2021/2/308230/Co4O4_try2_raster.json']

# sample_name_list = ['Co4O4 VTC']
# sample_reg_path_list = ['/nsls2/xf08id/users/2021/2/308230/Co4O4_raster.json']


x_run = xlive_gui.widget_run
x_camera = xlive_gui.widget_camera


for sample_name, sreg_path in zip(sample_name_list, sample_reg_path_list):
    x_camera.lineEdit_sreg_file.setText(sreg_path)
    x_camera._sreg_load_file()

    # !!!!!!!!!! CHoose number of scans per sample - currently it is set to exhaust the entire sample
    #points_left = len([1 for i in sample_registry.position_list if not i['exposed']])
    points_left = 70

    while points_left > 0:
        if points_left % 2 == 0:
            x_run.parameter_values[0].setText(sample_name + ' even')
            x_run.parameter_values[5].setValue(7670)
            x_run.parameter_values[6].setValue(7680)
            x_run.parameter_values[7].setValue(7710)
            x_run.parameter_values[8].setValue(7725)
        else:
            x_run.parameter_values[0].setText(sample_name + ' odd')
            x_run.parameter_values[5].setValue(7671)
            x_run.parameter_values[6].setValue(7680.25)
            x_run.parameter_values[7].setValue(7710.25)
            x_run.parameter_values[8].setValue(7726)

        x_run.run_scan()
        points_left -= 1

dump_data_to_json()


#####

def get_data():
    files = [x.working_folder + '/' + i.text() for i in x.list_data.selectedItems()]
    dfs_odd = []
    dfs_even = []
    for f in files:
        _df, _ = load_binned_df_from_file(f)
        if 'even' in f:
            dfs_even.append(_df)
        else:
            dfs_odd.append(_df)

    data_even = np.vstack([-(_df['pil100_ROI1']/_df['i0']).values for _df in dfs_even]).T
    data_odd = np.vstack([-(_df['pil100_ROI1']/_df['i0']).values for _df in dfs_odd]).T
    energy_even = dfs_even[0]['energy'].values
    energy_odd = dfs_odd[0]['energy'].values

    energy = np.hstack((energy_even, energy_odd))
    data_even_av = np.mean(data_even, axis=1)
    data_odd_av = np.mean(data_odd, axis=1)
    data_av = np.hstack((data_even_av, data_odd_av))

    plt.figure(); plt.plot(energy_even, '.-'); plt.plot(energy_odd, '.-')
    idx_ord = np.argsort(energy)
    return energy[idx_ord], data_av[idx_ord]


p_bkg = np.polyfit(energy[energy_mask], data_av[energy_mask], 15)
bkg = np.polyval(p_bkg, energy)

plt.figure(); plt.plot(energy, data_av, 'k.-')
plt.plot(energy, bkg, 'r-')

#######

from PIL import Image
h5_file_path = '/nsls2/xf08id/users/2021/2/308437/'
process_filepath = h5_file_path + 'tiff_storage/'
h5_files = [f for f in os.listdir(h5_file_path) if f.endswith('.h5')]
# os.mkdir(h5_file_path + 'tiff_storage/')
def parse_hdf5_file(h5_file):
    table = pd.read_hdf(h5_file_path + h5_file)
    table_red = table[['hhm_energy', 'apb_ave_ch1', 'apb_ave_ch2', 'apb_ave_ch3', 'apb_ave_ch4']]
    table_red.rename(columns={'hhm_energy': 'energy', 'apb_ave_ch1': 'i0', 'apb_ave_ch2': 'it', 'apb_ave_ch3': 'ir',
                              'apb_ave_ch4': 'iff'})
    scan_name = h5_file[:-3]
    dat_file_fpath = process_filepath + scan_name + '.dat'
    print(f'dat will be saved in {dat_file_fpath}')
    # table_red.to_csv(dat_file_fpath)
    image_folder = process_filepath + scan_name + '/'
    try:
        os.mkdir(image_folder)
    except FileExistsError:
        print('Warning Folder exists')
    for i, im in enumerate(table['pil100k_image']):
        image_from_h5 = Image.fromarray(im)

        tiff_filename = '{}{:04d}{}'.format('image', i+1, '.tiff')
        tiff_path = image_folder + tiff_filename
        print(f'tiff will be saved in {tiff_path}')
        image_from_h5.save(tiff_path)

    table_red.to_csv(dat_file_fpath, sep='\t', index=False)


for h5_file in h5_files:
    parse_hdf5_file(h5_file)
        # image_from_h5.save('test.tif')
        # '{}-{}{:04d}{}'.format(path, prefix, iterator, extension)


#####

####

# pil_data = []
# ts_data = []

plt.figure(1);
plt.clf()

for i in range(-10, 0):
    hdr = db[i]
    df, _ = load_interpolated_df_from_file(hdr.start['interp_filename'])
    e = df['energy'].values
    d = df['pil100k_ROI1'].values
    plt.plot(e, d/np.mean(d[-100:]))
    # t = hdr.table(stream_name='pil100k_hdf5_stream', fill=True)
    # _d = np.array([i['pil100k_ROI1'] for i in t['pil100k_hdf5_stream']])
    #
    #
    # _ts = load_apb_trig_dataset_from_db(db, i, use_fall=True, stream_name = 'apb_trigger_pil100k')
    #
    # plt.plot(_ts[:len(_d)] - _ts[0], _d / np.mean(_d[:100]))
    #
    # pil_data.append(_d)
    # ts_data.append(_d)

def c():
    file = '/nsls2/xf08id/users/2021/2/308230/Co4O4Ground_RIXS_2_data.json'
    d = {}
    for k in x.rixs_dict.keys():
        if type(x.rixs_dict[k]) == np.ndarray:
            d[k] = x.rixs_dict[k].tolist()
        else:
            d[k] = x.rixs_dict[k]
        with open(file, 'w') as fp:
            json.dump(d, fp)



#######

# mixing samples in a fun way

from isstools.elements.batch_elements import _create_new_sample


def load_samples():
    x = xlive_gui.widget_batch_mode.widget_batch_manual
    folder = '/nsls2/xf08id/Sandbox/'
    fnames = ['MoO2_dilute_Hadt_2021_11_3_try2.smpl',
              'MoO3_dilute_Hadt_2021_11_3.smpl',
              '2H-MoS2_dilute_Hadt_2021_11_3.smpl'
              ]

    samples_dict = {}

    b_size = 5
    n_reps = 30
    samples = []
    names = []
    for file in fnames:
        with open(folder + file, 'r') as f:
            samples_dict[file] = json.loads(f.read())
    idx = 0
    for i in range(n_reps):
        for key, item in samples_dict.items():
            samples.extend(item[idx : (idx + b_size)])
        idx += b_size

    for sample in samples:
        print(sample)
        names.append(sample['name'])
        _create_new_sample(sample['name'], sample['comment'], sample['x'], sample['y'], model=x.model_samples)

    x.listView_samples.setModel(x.model_samples)
    return names


names = load_samples()

#%%% SCRATCH FOR DENIS XES PROCESSING

# Co foil
from xas.file_io import load_interpolated_df_from_file
x = xview_gui.project
files = [f[2:] for f in x[-1].md['merged files'].split('\n')[1:-1]]
for f in [files[0]]:
    df, header = load_interpolated_df_from_file(f)
    uid = header[1477:1513].split(' ')[1]




PIL100k_HDF_DATA_KEY = 'entry/instrument/NDAttributes'
from databroker.assets.handlers import HandlerBase, PilatusCBFHandler, AreaDetectorTiffHandler, Xspress3HDF5Handler
class ISSPilatusHDF5Handler(Xspress3HDF5Handler): # Denis: I used Xspress3HDF5Handler as basis since it has all the basic functionality and I more or less understand how it works
    specs = {'PIL100k_HDF5'} | HandlerBase.specs
    HANDLER_NAME = 'PIL100k_HDF5'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, key=PIL100k_HDF_DATA_KEY, **kwargs)
        self._roi_data = None
        self.hdfrois = [f'ROI{i + 1}' for i in range(4)]
        self.chanrois = [f'pil100k_ROI{i + 1}' for i in range(4)]


    def _get_dataset(self):
        if self._dataset is not None:
            return

        _data_columns = [self._file[self._key + f'/_{chanroi}Total'][()] for chanroi in self.hdfrois]
        data_columns = np.vstack(_data_columns).T
        self._image_data = self._file['entry/data/data'][()]
        # n_images = images.shape[0]
        # self._image_data = pd.DataFrame({'image' : [images[i, :, :].squeeze() for i in range(n_images)]})
        self._roi_data = pd.DataFrame(data_columns, columns=self.chanrois)
        self._dataset = data_columns

    def __call__(self, *args, frame=None,  **kwargs):
        self._get_dataset()
        return_dict = {chanroi: self._roi_data[chanroi][frame] for chanroi in self.chanrois}
        return_dict['image'] = self._image_data[frame, :, :].squeeze()
        return return_dict
        # return self._roi_data

db.reg.register_handler('PIL100k_HDF5',
                         ISSPilatusHDF5Handler, overwrite=True)


from xas.db_io import load_apb_trig_dataset_from_db, load_apb_dataset_from_db
from xas.file_io import load_interpolated_df_from_file
from xas.bin import _generate_convolution_bin_matrix

def load_pil100k_dataset_from_db(db, uid, apb_trig_timestamps):
    hdr = db[uid]
    # spectra = {}
    # images = {}

    t = hdr.table(stream_name='pil100k_stream', fill=True)['pil100k_stream']
    n_images = t.shape[0]
    _image = t[1]['image']

    pil100k_timestamps = apb_trig_timestamps[:n_images]
    # keys = t[1].keys()
    keys = [k for k in t[1].keys() if ('roi' in k.lower())] # do only those with roi in the name
    # _spectra = np.zeros((n_images, len(keys)))
    _images = np.zeros((n_images, *_image.shape))
    for i in range(0, n_images):
        for j, key in enumerate(keys):
            # _spectra[i, j] = t[i+1][key]
            _images[i, :, :] = t[i+1]['image']
    # for j, key in enumerate(keys):
        # spectra[key] = pd.DataFrame(np.vstack((pil100k_timestamps, _spectra[:, j])).T,
        #                             columns=['timestamp', f'pil100k_ROI{j + 1}'])
        # images[key] = pd.DataFrame(np.vstack((pil100k_timestamps, _images[:, j])).T,
        #                             columns=['timestamp', f'pil100k_ROI{j + 1}'])

    return pil100k_timestamps, _images


#foil_uids
uids = ['b46dd539-2d9e-4610-8665-ffe59002234']


def bin_fly_pilatus_images_for_scan(db, uid):
    apb_dataset, energy_dataset, angle_offset = load_apb_dataset_from_db(db, uid)
    enc = energy_dataset['encoder'].apply(lambda x: int(x) if int(x) <= 0 else -(int(x) ^ 0xffffff - 1))
    energy = pd.DataFrame()
    energy['timestamp'] = energy_dataset['ts_s'] + 1e-9 * energy_dataset['ts_ns']
    energy['energy'] = xray.encoder2energy(enc, 360000, angle_offset)
    energy_timestamps = energy['timestamp'].values
    energy_raw = energy['energy'].values
    apb_trig_timestamps = load_apb_trig_dataset_from_db(db, uid,
                                                        use_fall=True,
                                                        stream_name='apb_trigger_pil100k')
    pil100k_timestamps, images_raw = load_pil100k_dataset_from_db(db, uid, apb_trig_timestamps)

    hdr = db[uid]
    df, header = load_interpolated_df_from_file(hdr.start['interp_filename'][:-3] + 'dat')
    energy_bin = np.sort(df['energy'].values)
    energy_edges = energy_bin[:-1] - 0.5 * np.diff(energy_bin)
    # energy_edges = np.hstack((energy_edges,
    #                           energy_bin[-1] - (energy_bin[-1] - energy_bin[-2]) / 2,
    #                           energy_bin[-1] + (energy_bin[-1] - energy_bin[-2]) / 2))
    # images = np.zeros((energy_bin.size, *images_raw.shape[1:]))
    pil100k_energy = np.interp(pil100k_timestamps, energy_timestamps, energy_raw)
    convo_mat = _generate_convolution_bin_matrix(energy_bin, pil100k_energy)
    images = -np.tensordot(convo_mat, images_raw, (1, 0))
    return images


def process_step_xes_johann_scan(db, uid):
    hdr = db[uid]
    t = hdr.table(fill=True)



for uid in uids:
    apb_dataset, energy_dataset, angle_offset = load_apb_dataset_from_db(db, uid)
    enc = energy_dataset['encoder'].apply(lambda x: int(x) if int(x) <= 0 else -(int(x) ^ 0xffffff - 1))
    energy = pd.DataFrame()
    energy['timestamp'] = energy_dataset['ts_s'] + 1e-9 * energy_dataset['ts_ns']
    energy['energy'] = xray.encoder2energy(enc, 360000, angle_offset)
    energy_timestamps = energy['timestamp'].values
    energy_raw = energy['energy'].values
    apb_trig_timestamps = load_apb_trig_dataset_from_db(db, uid,
                                                        use_fall=True,
                                                        stream_name='apb_trigger_pil100k')
    pil100k_timestamps, images_raw = load_pil100k_dataset_from_db(db, uid, apb_trig_timestamps)

    hdr = db[uid]
    df, header = load_interpolated_df_from_file(hdr.start['interp_filename'][:-3] + 'dat')
    energy_bin = np.sort(df['energy'].values)
    energy_edges = energy_bin[:-1] - 0.5 * np.diff(energy_bin)
    # energy_edges = np.hstack((energy_edges,
    #                           energy_bin[-1] - (energy_bin[-1] - energy_bin[-2]) / 2,
    #                           energy_bin[-1] + (energy_bin[-1] - energy_bin[-2]) / 2))
    # images = np.zeros((energy_bin.size, *images_raw.shape[1:]))
    pil100k_energy = np.interp(pil100k_timestamps, energy_timestamps, energy_raw)
    convo_mat = _generate_convolution_bin_matrix(energy_bin, pil100k_energy)
    images = -np.tensordot(convo_mat, images_raw, (1, 0))


####
# reprocessing of Lynne's data from 2021-1
# pwd /nsls2/xf08id/users/2021/2/308301
from xas.file_io import load_interpolated_df_from_file, load_binned_df_from_file, save_binned_df_as_file
x = xview_gui
working_folder = x.widget_data.working_folder
files = [f for f in x.widget_data.file_list if ('210720 CoNC Kb-XES ' in f) and ('_bkg_upd' not in f)][::-1]
roi_vals = (60, 360, 90, 100)
keys = list(set([f.split(' ')[3] for f in files]))

# files = [f for f in x.widget_data.file_list if ('Fephen-NC XES ' in f) and ('00mV ' in f) and ('_bkg_upd' not in f)][::-1]
# roi_vals = (40, 70, 120, 40)
# keys = list(set([f.split(' ')[2] for f in files[:30]] + [f.split(' ')[3] for f in files[30:]]))

xes_dict = {}
xes_no_bkg_dict = {}

I0_list = []
for k in keys:
    xes_dict[k] = []
    xes_no_bkg_dict[k] = []


# for f in [files[0]]:
# # for f in files:
#     # df, header = load_interpolated_df_from_file(f)
#     print(f'Processing file: {f}')
#     fpath = (working_folder + '/' + f)
#     fkey = f.split(' ')[3]
#
#     df, header = load_binned_df_from_file(fpath)
#     uid = header.split('\n# ')[-3].split(' ')[1]
#     hdr = db[uid]
#     t = hdr.table(fill=True)

# for f in [files[0]]:
for f in files:
    # df, header = load_interpolated_df_from_file(f)
    print(f'Processing file: {f}')
    fpath = (working_folder + '/' + f)
    # fkey = f.split(' ')[3]
    fkey = keys[[k in f for k in keys].index(True)]

    df, header = load_binned_df_from_file(fpath)
    uid = header.split('\n# ')[-3].split(' ')[1]
    hdr = db[uid]
    t = hdr.table(fill=True)

    roi1 = []
    roi1_no_bkg = []
    for i in t.index:
        _roi_sum = pil100k_roi_sum(t.pil100k_image[i].squeeze(), roi_vals)
        _roi_sum_no_bkg = pil100k_roi_sum_w_bkg_removed(t.pil100k_image[i].squeeze(), roi_vals, dw=20)
        roi1.append(_roi_sum)
        roi1_no_bkg.append(_roi_sum_no_bkg)

    roi1 = np.array(roi1)
    roi1_no_bkg = np.array(roi1_no_bkg)

    df['pil100_ROI1_new'] = roi1
    df['pil100_ROI1_new_no_bkg'] = roi1_no_bkg

    cols = df.columns.tolist()
    cols = cols[1:] + cols[:1]

    save_binned_df_as_file(fpath[:-4] + '_bkg_upd.dat', df[cols], header)
    I0_list = I0_list + df.i0.tolist()
    emission_energy = t.motor_emission_energy.values
    xes_dict[fkey].append(-roi1 / df.i0.values)
    xes_no_bkg_dict[fkey].append(-roi1_no_bkg / df.i0.values)
    # plt.figure(5)
    # plt.clf()
    #
    # plt.subplot(211)
    # plt.plot(emission_energy, roi1, 'k.-')
    # plt.plot(emission_energy, roi1_no_bkg, 'r-')


for key in keys:
    key_av = key+'_av'
    key_err = key + '_err'

    spectra = []
    for i in range(len(xes_dict[key])):
        _spectrum = xes_dict[key][i]
        _spectrum = _spectrum / np.trapz(_spectrum, emission_energy)
        spectra.append(_spectrum)
    xes_dict[key_av] = np.mean(np.array(spectra), axis=0)
    xes_dict[key_err] = np.std(np.array(spectra), axis=0) / np.sqrt(len(spectra))

    spectra = []
    for i in range(len(xes_no_bkg_dict[key])):
        _spectrum = xes_no_bkg_dict[key][i]
        # _bkg = (_spectrum[0] + _spectrum[1]) / 2
        # _spectrum = _spectrum - _bkg
        _spectrum = _spectrum / np.trapz(_spectrum, emission_energy)
        spectra.append(_spectrum)
    xes_no_bkg_dict[key_av] = np.mean(np.array(spectra), axis=0)
    xes_no_bkg_dict[key_err] = np.std(np.array(spectra), axis=0) / np.sqrt(len(spectra))


# def normalize_spectra(energy, spectra):
#     spectra_out = [spectra[0].copy()]
#     idx1 = 0
#     idx2 = 10
#     int_low_tail = np.sum(spectra[0][idx1:idx2])
#     for spectrum in spectra[1:]:
#         spectrum_out = spectrum.copy()
#         spectrum_out = spectrum_out - np.sum(spectrum_out[idx1:idx2]) + int_low_tail
#         spectrum_out = spectrum_out / np.trapz(spectrum_out, energy)
#         spectra_out.append(spectrum_out)
#     return spectra_out



# bla = normalize_spectra(emission_energy, [xes_no_bkg_dict['300mV_av'], xes_no_bkg_dict['900mV_av']])

def normalize_spectrum(x, s):
    '''
    Corrects the background and renormalizes the spectrum.
    The background is estimated as line going through the first and the last points in spectra.
    x - energy
    s - intensity
    '''
    x1 = x[0]
    x2 = x[-1]
    s1 = s[0]
    s2 = s[-1]
    k = (s2 - s1) / (x2 - x1)
    b = s1 - k * x1
    bkg = k * x + b
    s_upd = s - bkg
    s_upd = s_upd / np.trapz(s_upd, x)
    return s_upd

plt.figure(44)
plt.clf()

plt.subplot(211)
plt.plot(emission_energy, xes_dict['300mV_av'], label='300 mV')
plt.plot(emission_energy, xes_no_bkg_dict['300mV_av'], label='300 mV no bkg')

plt.subplot(211)
plt.plot(emission_energy, xes_dict['900mV_av'], label='900 mV')
plt.plot(emission_energy, xes_no_bkg_dict['900mV_av'], label='900 mV no bkg')
plt.legend()

plt.subplot(212)
plt.plot(emission_energy, xes_dict['900mV_av'] - xes_dict['300mV_av'], label='900 mV - 300 mV')
plt.plot(emission_energy, xes_no_bkg_dict['900mV_av'] - xes_no_bkg_dict['300mV_av'], label='900 mV - 300 mV no bkg')
plt.legend()


plt.figure(45)
plt.clf()

plt.subplot(211)
plt.plot(emission_energy, normalize_spectrum(emission_energy, xes_dict['300mV_av']), label='300 mV renorm')
plt.plot(emission_energy, normalize_spectrum(emission_energy, xes_no_bkg_dict['300mV_av']), label='300 mV no bkg renorm')
# plt.plot(emission_energy, normalize_spectrum(emission_energy, xes_dict['300mV_av']), label='300 mV recorrected')
# plt.plot(emission_energy, xes_no_bkg_dict['300mV_av'], label='300 mV no bkg')

plt.plot(emission_energy, normalize_spectrum(emission_energy, xes_dict['900mV_av']), label='900 mV renorm')
plt.plot(emission_energy, normalize_spectrum(emission_energy, xes_no_bkg_dict['900mV_av']), label='900 mV no bkg renorm')
plt.legend()

plt.subplot(212)
plt.plot(emission_energy, normalize_spectrum(emission_energy, xes_dict['900mV_av']) -
                          normalize_spectrum(emission_energy, xes_dict['300mV_av']), label='900 mV - 300 mV renorm')
plt.plot(emission_energy, normalize_spectrum(emission_energy, xes_no_bkg_dict['900mV_av']) -
                          normalize_spectrum(emission_energy, xes_no_bkg_dict['300mV_av']), label='900 mV - 300 mV no bkg renorm')
plt.legend()


# plt.figure()
# plt.plot(emission_energy, xes_dict['900mV_err'])
# plt.plot(emission_energy, xes_dict['900mV_err'] * normalize_spectrum(emission_energy, xes_no_bkg_dict['900mV_av']) / xes_no_bkg_dict['900mV_av'])

output_dict = {'emission_energy' : emission_energy,
               '300mV_av' : xes_no_bkg_dict['300mV_av'],
               '300mV_av_renorm' : normalize_spectrum(emission_energy, xes_no_bkg_dict['300mV_av']),
               '300mV_err' : xes_no_bkg_dict['300mV_err'],
               '500mV_av' : xes_no_bkg_dict['500mV_av'],
               '500mV_av_renorm' : normalize_spectrum(emission_energy, xes_no_bkg_dict['500mV_av']),
               '500mV_err' : xes_no_bkg_dict['500mV_err'],
               '700mV_av' : xes_no_bkg_dict['700mV_av'],
               '700mV_av_renorm' : normalize_spectrum(emission_energy, xes_no_bkg_dict['700mV_av']),
               '700mV_err' : xes_no_bkg_dict['700mV_err'],
               '800mV_av' : xes_no_bkg_dict['800mV_av'],
               '800mV_av_renorm' : normalize_spectrum(emission_energy, xes_no_bkg_dict['800mV_av']),
               '800mV_err' : xes_no_bkg_dict['800mV_err'],
               '900mV_av' : xes_no_bkg_dict['900mV_av'],
               '900mV_av_renorm' : normalize_spectrum(emission_energy, xes_no_bkg_dict['900mV_av']),
               '900mV_err' : xes_no_bkg_dict['900mV_err'],
               }
output_df = pd.DataFrame(output_dict)
output_df.to_csv(working_folder + '/reprocessed_averaged_Co_XES_data.dat', sep='\t', index=False)

# output_dict = {'emission_energy' : emission_energy,
#                '300mV_av' : xes_no_bkg_dict['300mV_av'],
#                '300mV_av_renorm' : normalize_spectrum(emission_energy, xes_no_bkg_dict['300mV_av']),
#                '300mV_err' : xes_no_bkg_dict['300mV_err'],
#                '700mV_av' : xes_no_bkg_dict['700mV_av'],
#                '700mV_av_renorm' : normalize_spectrum(emission_energy, xes_no_bkg_dict['700mV_av']),
#                '700mV_err' : xes_no_bkg_dict['700mV_err'],
#                '900mV_av' : xes_no_bkg_dict['900mV_av'],
#                '900mV_av_renorm' : normalize_spectrum(emission_energy, xes_no_bkg_dict['900mV_av']),
#                '900mV_err' : xes_no_bkg_dict['900mV_err'],
#                }
# output_df = pd.DataFrame(output_dict)
# output_df.to_csv(working_folder + '/reprocessed_averaged_Fe_XES_data.dat', sep='\t', index=False)

#

emission_energy = x.project[0].energy
output_dict = {'energy' : emission_energy}
for ds in x.project:
    output_dict[ds.name + '_av'] = ds.mu / np.trapz(ds.mu, emission_energy)
    output_dict[ds.name + '_renorm'] = normalize_spectrum(emission_energy, ds.mu)
output_df = pd.DataFrame(output_dict)
output_df.to_csv(working_folder + '/reprocessed_averaged_Co_reference_XES_data.dat', sep='\t', index=False)

plt.figure(88)
for ds in x.project:
    plt.plot(emission_energy, ds.mu / np.trapz(ds.mu, emission_energy))

#######
def remove_bkg_from_pil100k_roi(image, roi, dw=5, plotting=False):
    y, x, dy, dx = roi
    yw, xw, dyw, dxw = y - dw, x - dw, dy + 2 * dw, dx + 2 * dw

    bkg_mask = np.zeros(image.shape, dtype=bool)
    bkg_mask[yw:yw + dyw, xw:xw + dxw] = True
    bkg_mask[y:y+dy, x:x+dx] = False

    # image_bkg = image.copy()
    # image_bkg[~bkg_mask] = -100

    y_size, x_size = image.shape
    y_mesh, x_mesh = np.meshgrid(np.arange(y_size), np.arange(x_size), indexing='ij')

    y_bkg = y_mesh[bkg_mask].ravel()
    x_bkg = x_mesh[bkg_mask].ravel()
    i_bkg = image[bkg_mask].ravel()
    # dfg
    # mask = mask_by_percentiles(i_bkg)
    mask = (i_bkg >= 0) #& (i_bkg < thresh)
    y_bkg = y_bkg[mask]
    x_bkg = x_bkg[mask]
    i_bkg = i_bkg[mask]

    c = fit_linear_surf(y_bkg, x_bkg, i_bkg, plotting=plotting)

    A_fit = np.hstack((y_mesh.ravel()[:, None], x_mesh.ravel()[:, None], np.ones((y_mesh.ravel().size, 1))))
    i_bkg_fit = (A_fit @ c).reshape(y_size, x_size)

    return image - i_bkg_fit

def pil100k_roi_sum(image, roi):
    y, x, dy, dx = roi
    pixels = image[y: y + dy, x: x + dx]
    return np.sum(pixels[pixels>=0])

def pil100k_roi_sum_w_bkg_removed(image, roi, dw=5, plotting=False):
    image_no_bkg = remove_bkg_from_pil100k_roi(image, roi, dw=dw, plotting=plotting)
    y, x, dy, dx = roi
    pixels = image[y: y + dy, x: x + dx]
    pixels_no_bkg = image_no_bkg[y: y + dy, x: x + dx]
    return np.sum(pixels_no_bkg[pixels>=0])

# remove_bkg_from_pil100k_roi(total_image, (60, 360, 90, 100), dw=20)

# pil100k_roi_sum_w_bkg_removed(total_image, (60, 360, 90, 100), dw=20)

def mask_by_percentiles(x, p_lo=5, p_hi=95):
    x_lo, x_hi = np.percentile(x, [p_lo, p_hi])
    return ((x > x_lo) & (x < x_hi))

def filter_by_percentiles(x, p_lo=5, p_hi=95):
    x_mask = mask_by_percentiles(x, p_lo=p_lo, p_hi=p_hi)
    return x[x_mask]


# _x, _y = np.meshgrid(np.arange(10), np.arange(10), indexing='ij')
# _x = _x.ravel()
# _y = _y.ravel()
# _z = _x + _y + 5 + np.random.randn(_x.size)

def fit_linear_surf(x, y, z, plotting=False):
    A = np.hstack((x[:, None], y[:, None], np.ones((x.size, 1))))
    c, _, _, _ = np.linalg.lstsq(A, z, rcond=-1)
    if plotting:
        try:
            mplot3d
        except NameError:
            from mpl_toolkits import mplot3d
        fig = plt.figure(333, clear=True)
        ax = plt.axes(projection='3d')
        ax.scatter3D(x, y, z, marker='.', color='k')
        ax.scatter3D(x, y, A @ c, marker='.', color='r')
    return c

# fit_linear_surf(_x, _y, _z, plotting=True)

####
uids = ['11719da3-236e-40aa-b94d-247307de4ea9',
        'd0a58ba0-c55f-42a8-a05d-8735c1e5dd72']
# uids = [-3, -2, -1]

uids = [#'a1516a2a-29a6-479d-aa1f-5d1de422b627', # 6/1
        'a1516a2a-29a6-479d-aa1f-5d1de422b627', # 20/5
        '9e06284a-9e41-4a95-befa-87080f547c0c', # 22.5/2.5
        'c25b61c6-1633-4ac6-9b58-d62885f9f917'] #24/1
def get_x_y(uid):
    hdr = db[uid]
    t = hdr.table()
    x = t.giantxy_x_user_setpoint
    y = t.xs_channel1_rois_roi01_value
    return x, y

plt.figure()
for uid in uids:
    x, y = get_x_y(uid)
    plt.plot(x, y)

#%%


def generate_signal(t, F, offset):
    avs = np.sin(2 * np.pi * t * F)
    avs_shift = np.sin(2 * np.pi * t * F + np.pi / 2)
    s = np.random.poisson(avs + offset)
    x = np.sum(s * avs)
    y = np.sum(s * avs_shift)
    R = x**2 + y**2
    return s, R

t = np.linspace(0, 10, 10001)
F = 1
s1, R1 = generate_signal(t, F, 2)
s2, R2 = generate_signal(t, F, 2000)


print(R1, R2)

plt.figure()
# pl?t.subplot(211)
plt.plot(t, s1)
plt.plot(t, s2)

###

s1 = _23
s2 = _22

plt.figure(1, clear=True)
# plt.plot((s2 - s1)[:, 0])
plt.semilogy(s1[:, 0], label='11200 eV')
plt.semilogy(s2[:, 0], label='11215 eV')

plt.xlim(700, 1200)
plt.xlabel('Channels')
plt.ylabel('Counts')

# plt.plot(s1)


###

# from



###

from xas.file_io import load_interpolated_df_from_file

df, _ = load_interpolated_df_from_file(r'/nsls2/xf08id/users/2021/3/308208/Ferric Mb 0.9 mM 27_5-2_5 Soller Mn 3 ACTUALLY vs SDD 0001.raw')

muf = df.iff/df.i0
t = df.timestamp
energy = df.energy
muf_fft = np.abs(np.fft.fft(muf))
freq = np.fft.fftfreq(t.size, d=t[1]-t[0])
freq_ord = np.argsort(freq)

s_00 = np.sin(2 * np.pi * t * 28.716)
c_00 = np.cos(2 * np.pi * t * 28.716)

ruf = np.sqrt((muf_fft*s_00)**2 + (muf_fft*s_00)**2)

plt.figure(2)
plt.clf()

plt.plot(energy, ruf)
# plt.plot(energy, muf)
# plt.loglog(freq[freq_ord], muf_fft[freq_ord])

########


year='2022'
cycle='1'
proposal = '309839'
PI = ''#self.RE.md['PI']
working_directory = f'/nsls2/xf08id/users/{year}/{cycle}/{proposal}'
zip_file = f'{working_directory}/{proposal}.zip'

id = str(uuid.uuid4())[0:5]

zip_id_file = f'{proposal}-{id}.zip'

if os.path.exists(zip_file):
    os.remove(zip_file)

# os.system(f'zip {zip_file} {working_directory}/*.* ')
os.system(f'zip {zip_file} {working_directory}/*.dat')

folder = f'/{year}/{cycle}/'
dropbox_upload_files(dropbox_service, zip_file,folder,zip_id_file)

link_url = dropbox_get_shared_link(dropbox_service, f'{folder}{zip_id_file}' )
print('Upload succesful')


message = create_html_message(
    'staff08id@gmail.com',
    email_address,
    f'ISS beamline results Proposal {proposal}',
    f' <p> Dear {PI},</p> <p>You can download the result of your'
    f' experiment at ISS under proposal {proposal} here,</p> <p> {link_url} '
    f'</p> <p> Sincerely, </p> <p> ISS Staff </p>'
    )

draft = upload_draft(self.parent.gmail_service, message)
sent = send_draft(self.parent.gmail_service, draft)
print('Email sent')


##############
from xas.file_io import validate_file_exists
from xas.process import process_interpolate_bin_from_uid
cloud_dispatcher = xlive_gui.cloud_dispatcher
for i in range(197472, 198382):
# for i in range(197472, 197500):
    hdr = db[i]
    start = hdr.start
    if 'interp_filename' in list(start.keys()):
        filename = start['interp_filename']
        filename_check = validate_file_exists(filename)
        if filename_check == filename:
            print(i)
            process_interpolate_bin_from_uid(i, db, cloud_dispatcher=cloud_dispatcher)

####

file_list = ['/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0041-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0031-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0026-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0020-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0004-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0048-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0046-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0041-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0039-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0036-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0033-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0031-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0022-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0020-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 2 (pos 001) Ir XANES L3  0014-r0004.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 8 (pos 001) Ir XANES L3  0019-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 8 (pos 001) Ir XANES L3  0015-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 8 (pos 001) Ir XANES L3  0008-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 8 (pos 001) Ir XANES L3  0003-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 7 (pos 001) Ir XANES L3  0014-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 6 (pos 001) Ir XANES L3  0015-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 6 (pos 001) Ir XANES L3  0013-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 6 (pos 001) Ir XANES L3  0007-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 5 (pos 001) Ir XANES L3  0015-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 3 (pos 001) Ir XANES L3  0014-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 3 (pos 001) Ir XANES L3  0009-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 3 (pos 001) Ir XANES L3  0007-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 3 (pos 001) Ir XANES L3  0005-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 1 (pos 001) Ir XANES L3  0018-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 1 (pos 001) Ir XANES L3  0005-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0050-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0044-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 5 (pos 001) Ir XANES L3  0007-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/test 0003-r0003.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 1 SDD test 0001-r0002.dat',
'/nsls2/xf08id/users/2022/1/309628/Sample 4 (pos 001) Ir XANES L3  0041-r0003.dat']

for f in file_list:
    xlive_gui.cloud_dispatcher.load_to_dropbox(f)


a=xview_gui.project

b=a[-1]

b.md_processing = {"Processing steps": ['merge']}
b. md_sample = {'Composition': 'NMCA','Comment':'1','Charging cycle':2,'Voltage': 4.8}
full_dict= [b.md, b.md_sample,b.md_processing, {'Energy': b.energy.tolist(), 'mu_flat': b.flat.tolist()}]
filename = b.md_sample['Composition'] + ' ' + b.md_sample['Comment'] + ' Charging cycle '+ str(b.md_sample['Charging cycle'])+ ' ' + str(b.md_sample['Voltage']) + 'V ' +str(b.md['element'])+ '.json'
print(filename)
print(b.md['merged files'])

json_object = json.dumps(full_dict)

# Writing to sample.json
with open(filename, "w") as f:
     f.write(json_object)



#%%%
# from xas import filter_df_by_valid_keys
from xas.file_io import stepscan_remove_offsets, stepscan_normalize_xs, combine_xspress3_channels


# uid = '1145befd-c665-4740-98b4-6dc3d0671aaf'
uid = 'b05d6f55-fe76-4df4-bceb-7542c9cf7293'

df_raw = stepscan_remove_offsets(db[uid])
df_raw = stepscan_normalize_xs(df_raw)
df_raw = combine_xspress3_channels(df_raw)

df_processed = filter_df_by_valid_keys(df_raw)

def process_von_hamos_scan(df_processed, df_raw, roi='auto'):
    vh_scan = VonHamosScan(df_processed, df_raw)
    if roi == 'auto':
        pass
    vh_scan.set_roi(*roi)
    vh_scan.integrate_images()
    return vh_scan

vh_scan = process_von_hamos_scan(df_processed, df_raw, roi=(65, 30, 100, 300))

#################################

start_times = []
stop_times = []

for i in range(203684, 204565+1):
    hdr = db[i]
    if 'experiment' in hdr.start.keys():
       if (hdr.start['experiment'] == 'step_scan') and (hdr.start['monochromator_scan_uid'] == 'b48af1b1-95c8'):

           if ('time' in hdr.start.keys()) and ('time' in hdr.stop.keys()):
               print(i, (i - 203684) / (204565 - 203684))
               start_times.append(hdr.start['time'])
               stop_times.append(hdr.stop['time'])

##

start_times = np.array(start_times)
stop_times = np.array(stop_times)


start_times_str = [ttime.ctime(t) for t in start_times]


#####################################


import cv2
import matplotlib.pyplot as plt


#x_coordinates = [95, 100, 105]
y_coordinates = [3, 8, 13]
sift = cv2.xfeatures2d.SIFT_create()
imgs = []
img_keypoints = []
img_descriptors = []
for _y in y_coordinates:
    RE(bps.mv(sample_stage.y, _y))
    _img = np.reshape(camera_sp1.image.array_data.value, (964, 1292)).astype(np.float32)
    img = cv2.normalize(cv2.cvtColor(_img, cv2.COLOR_GRAY2BGR), None, 0, 255, cv2.NORM_MINMAX).astype('uint8')
    imgs.append(img)
    keypoints, descriptors = sift.detectAndCompute(img, None)
    img_keypoints.append(keypoints)
    img_descriptors.append(descriptors)

img_matches = []
bf = cv2.BFMatcher(cv2.NORM_L1, crossCheck=False)
for i in range(len(y_coordinates)-1):
    match = bf.match(img_descriptors[i], img_descriptors[i+1])
    img_matches.append(match)



for i in range(len(y_coordinates)-1):
    plt.figure(i + 1, clear=True)
    img_match = cv2.drawMatches(imgs[i], img_keypoints[i], imgs[i+1], img_keypoints[i+1], img_matches[i][:50], imgs[i+1], flags=2)
    plt.imshow(img_match)


def show_similar_points_for_two_images(img_1, keypoints_1, img_2, keypoints_2, matches):
    img_1_pt = np.array([keypoints_1[v.queryIdx].pt for v in matches])
    img_2_pt = np.array([keypoints_2[v.trainIdx].pt for v in matches])

    dx, dy = (img_2_pt - img_1_pt).T

    tol = 15
    dist_target = 90

    dist = np.sqrt(dx**2 + dy**2)

    match_idxs,  = np.where((dist >= dist_target - tol) & (dist <= dist_target + tol) & (np.abs(dx)<5))

    plt.figure(7); plt.hist(dist, 200)

    plt.figure(3, clear=True)
    plt.imshow(img_1)


    plt.figure(4, clear=True)
    plt.imshow(img_2)

    print(len(match_idxs))
    for match_idx in match_idxs:
        plt.figure(3)
        plt.scatter(*keypoints_1[matches[match_idx].queryIdx].pt)

        plt.figure(4)
        plt.scatter(*keypoints_2[matches[match_idx].trainIdx].pt)

    xy1 = [keypoints_1[matches[match_idx].queryIdx].pt for match_idx in match_idxs]
    xy2 = [keypoints_2[matches[match_idx].trainIdx].pt for match_idx in match_idxs]

    return np.array(xy1), np.array(xy2)





i = 1
xy1, xy2 = show_similar_points_for_two_images(imgs[i], img_keypoints[i], imgs[i+1], img_keypoints[i+1], img_matches[i])

plt.figure(3, clear=True)
plt.subplot(221)
plt.plot(xy1[:, 0] , xy2[:, 0], 'k.')

plt.subplot(222)
plt.plot(xy1[:, 1], xy2[:, 1], 'k.')

plt.subplot(223)
plt.plot(xy2[:, 0] - xy1[:, 0], stage_xys[:, 1], 'k.')

plt.subplot(224)
plt.plot(xy2[:, 1] - xy1[:, 1], stage_xys[:, 0], 'k.')

# plt.subplot(224)
# plt.plot(xy1[:, 1], xy2[:, 0], 'k.')

npts = xy1.shape[0]

basis_T = np.hstack((xy1, np.ones((npts, 1)) * (y_coordinates[i+1] - y_coordinates[i])))
AxyT, _, _, _ = np.linalg.lstsq(basis_T, xy2, rcond=-1)
Axy = AxyT.T


our_point = [935, 600]
stage_shift = 5

new_point = Axy @ (our_point + [stage_shift])

plt.figure(10, clear=True)
plt.subplot(211)
plt.imshow(imgs[1])
plt.scatter(*our_point, color='r')

plt.subplot(212)
plt.imshow(imgs[2])
plt.scatter(*new_point, color='r')
# Ax

plt.figure(1, clear=True)
img_match = cv2.drawMatches(img_1_8bit, keypoints_1, img_2_8bit, keypoints_2, matches[:50], img_2_8bit, flags=2)
plt.imshow(img_match)




colors_before = []
colors_after = []
bla = cam1.image
for i in range(bla.size().width()):
    for j in range(bla.size().height()):
        _c = bla.pixelColor(i, j).value()
        colors_before.append(_c)
        if _c > 50:
            bla.setPixelColor(i, j, QtGui.QColor(50))
        _c = bla.pixelColor(i, j).value()
        colors_after.append(_c)


colors_before = []
bla = bla1
for i in range(bla.size().width()):
    for j in range(bla.size().height()):
        _c = bla.pixelColor(i, j).value()
        colors_before.append(_c)

plt.figure(); plt.hist(colors_before, 128)

bragg = 75
motor_pos_dict = rowland_circle.compute_motor_position(johann_main_crystal.real_keys, 85, nom2act=False)
x = motor_pos_dict['motor_cr_assy_x'] + np.linspace(-10, 10, 101)
dy = 1
dbragg = np.rad2deg(np.arctan(dy/x))

energy = rowland_circle.bragg2e(bragg+dbragg)
denergy = energy - np.mean(energy)

plt.figure(1, clear=True)
plt.plot(x, denergy)


CAMERA_KEY = 'camera_sp2'

# A_pix_motor_2_pix, A_pix_pix_2_motor = generate_sample_camera_calibration(dxs, dys, OUTPUT[CAMERA_KEY])

our_point = [765, 590]
stage_shift = [-5, 5]

new_point = A_pix_motor_2_pix @ (our_point + stage_shift)

plt.figure(10, clear=True)
plt.subplot(211)
plt.imshow(OUTPUT[CAMERA_KEY][0], cmap='gray')

plt.scatter(*our_point, color='r')

plt.subplot(212)
plt.imshow(OUTPUT[CAMERA_KEY][2], cmap='gray')

plt.scatter(*new_point, color='r')

# A_pix_pix_2_motor
###################

x = xlive_gui.widget_sample_manager.widget_camera1

def _func(image):
    # print_to_gui('here!')
    # image.setColorCount(5)
    # image.setColorTable(list(range(80)))
    # for i in range(200, 300):
    #     for j in range(200,300):
    #         image.setPixelColor(i, j, QtGui.QColor('white'))
    # image.setPixelColor(200, 200, QtGui.QColor('white'))
    # image.convertToFormat(3)
    # image.setColorCount(2)
    # image.setColor(0, 0)
    # image.setColor(1, 1)
    # color_table = [1]*256
    # image.setColorTable(color_table)
    # image.fill(345340)
    # image.setPixel(100, 100, 345340)
    return image

x.external_func = _func


image = x.image




def cm_tandem_pitch_scan(pitch_rel_pos_list):
    yield from bp.rel_list_scan([bpm_cm],
                                cm1.pitch, pitch_rel_pos_list,
                                cm2.pitch, pitch_rel_pos_list)

delta_ = 0.01
range_ = 0.3
_pitch_rel_pos_list = np.arange(-range_/2, range_/2 + delta_, delta_)
RE(cm_tandem_pitch_scan(_pitch_rel_pos_list))


plt.figure(1, clear=True)
t = db[-1].table()
# plt.plot(t.cm1_pitch, t.cm2_pitch)
plt.plot(t.cm2_pitch, t.bpm_cm_stats1_total)



def cm_tandem_y_scan(y_rel_pos_list):
    yield from bp.rel_list_scan([bpm_cm],
                                cm1.y, y_rel_pos_list,
                                cm2.y, y_rel_pos_list)

delta_ = 0.01
range_ = 0.4
_y_rel_pos_list = np.arange(-range_/2, range_/2 + delta_, delta_)
RE(cm_tandem_y_scan(_y_rel_pos_list))


plt.figure(2, clear=True)
t = db[-1].table()
# plt.plot(t.cm1_y, t.cm2_y)
plt.plot(t.cm2_y, t.bpm_cm_stats1_total)



#####
{
'bragg_registration': {
   'pos_nom':
       {'motor_det_x': [440.1284957158649, ],
   'motor_det_th1': [-7.944093709601603, ],
   'motor_det_th2': [-25.92960063557537, ],
   'motor_cr_assy_x': [956.3239866570002, ],
   'motor_cr_assy_y': [7.181946, ],
   'motor_cr_main_roll': [4245.610827411514, ],
   'motor_cr_main_yaw': [-190.0, ],
   'motor_cr_aux2_x': [-6069.950489617168, ],
   'motor_cr_aux2_y': [-5384.367583499954, ],
   'motor_cr_aux2_roll': [4008.4002042120424, ],
   'motor_cr_aux2_yaw': [210.0530576956662, ],
   'motor_cr_aux3_x': [-8197.678489617168, ],
   'motor_cr_aux3_y': [-5784.367583499954, ],
   'motor_cr_aux3_roll': [4859.267204212042, ],
   'motor_cr_aux3_yaw': [-2426.521057695666, ]},
  'pos_act': {'motor_det_x': [445.027446107, ],
   'motor_det_th1': [-8.12859375, ],
   'motor_det_th2': [-25.8721875, ],
   'motor_cr_assy_x': [957.4060535164999, ],
   'motor_cr_assy_y': [7.181946, ],
   'motor_cr_main_roll': [3691.876, ],
   'motor_cr_main_yaw': [-290.00100000000003, ],
   'motor_cr_aux2_x': [-8499.99, ],
   'motor_cr_aux2_y': [-5383.835, ],
   'motor_cr_aux2_roll': [2911.366, ],
   'motor_cr_aux2_yaw': [-898.6560000000001, ],
   'motor_cr_aux3_x': [-15699.942000000001, ],
   'motor_cr_aux3_y': [-5783.783, ],
   'motor_cr_aux3_roll': [4117.173,],
   'motor_cr_aux3_yaw': [-912.8670000000001, ]}},
 }

#######

from xas.file_io import write_df_to_file


from bluesky.preprocessors import monitor_during_wrapper
def test_plan(roll_swing = 400, exp_time=3):

    cur_exp_time = pil100k.cam.acquire_period.get()
    pil100k.set_exposure_time(exp_time)

    cur_roll_pos = johann_main_crystal.motor_cr_main_roll.position
    yield from bps.mv(johann_main_crystal.motor_cr_main_roll, cur_roll_pos - roll_swing / 2)

    cur_velocity = johann_main_crystal.motor_cr_main_roll.velocity.get()
    scan_velocity = roll_swing / exp_time * 1.6
    yield from bps.mv(johann_main_crystal.motor_cr_main_roll.velocity, scan_velocity)



    # yield from bps.stage(pil100k)
    yield from bps.open_run()
    # st_trigger = pil100k.trigger()
    # yield from bps.create('primary')
    # yield from bps.trigger(pil100k)
    pil100k.cam.acquire.put(1)
    yield from bps.mv(johann_main_crystal.motor_cr_main_roll, cur_roll_pos + roll_swing)

    # st_trigger.wait()

    # ret = {}
    # reading = (yield from bps.read(pil100k))
    # ret.update(reading)
    # yield from bps.save()
    # return ret

    yield from bps.close_run()
    # yield from bps.unstage(pil100k)

    yield from bps.mv(johann_main_crystal.motor_cr_main_roll.velocity, cur_velocity)
    yield from bps.mv(johann_main_crystal.motor_cr_main_roll, cur_roll_pos)
    pil100k.set_exposure_time(cur_exp_time)

RE(monitor_during_wrapper(test_plan(), [pil100k.image.array_data]))




# image = pil100k.image.array_data.get().reshape((195, 487))
#
# x = pil100k.roi4.min_xyz.min_x.get()
# y = pil100k.roi4.min_xyz.min_y.get()
# dx = pil100k.roi4.size.x.get()
# dy = pil100k.roi4.size.y.get()
#
# image_roi = image[y : (y + dy), x : (x + dx)]
# spectrum = np.sum(image_roi, axis=0)
# df = pd.DataFrame({'energy': np.arange(x, x + dx).tolist(), 'intesity': spectrum.tolist()})
#
# write_df_to_file('/nsls2/data/iss/legacy/processed/2023/1/312089/test.dat', df, '')


# RE(test_plan())






def test_plan(sleep_time):
    yield from bps.open_run()
    pil100k.cam.acquire.put(1)
    yield from bps.sleep(sleep_time)
    yield from bps.close_run()







img = np.array(db[-1].table(stream_name='pil100k_image_array_data_monitor')['pil100k_image_array_data'][2]).reshape(195, 487)
plt.figure()
plt.imshow(img[25:150, 200:340], vmin=0, vmax=50)

def get_projection_from_uid(uid):
    img = np.array(db[uid].table(stream_name='pil100k_image_array_data_monitor')['pil100k_image_array_data'][2]).reshape(195, 487)
    return np.sum(img[25:150, 200:340], axis=0)

bla1 = get_projection_from_uid(-5)
bla2 = get_projection_from_uid(-1)



plt.figure()
plt.plot(np.sum(img[25:150, 200:340], axis=0))


# johann_x = 0

def plot_for_uid(uid, **kwargs):
    t = db[uid].table()
    _roll = t['johann_main_crystal_motor_cr_main_roll'].values
    _intensity = t.pil100k_stats1_total.values
    plt.plot(_roll, _intensity, **kwargs)

plt.figure()
plot_for_uid('030b3e2d-a722-4bb2-a880-31d92c55c361', label='0 mm')
plot_for_uid('306eaa80-cdd6-4ba4-881a-962da6a5e3be', label='-10 mm')

plt.legend()




from numpy.polynomial import Polynomial as P
# np.random.seed(11)
# x = np.linspace(0, 2*np.pi, 20)
# y = np.sin(x) + np.random.normal(scale=.1, size=x.shape)

idx = np.argmax(y)
p = P.fit(x[idx-1:idx+2], y[idx-1:idx+2], 2)

plt.figure(1, clear=True)
plt.plot(x, y)
plt.plot(x, p(x))


plt.figure()
plt.plot((bla1 - np.mean(bla1[25:30]))/(bla1 - np.mean(bla1[25:30])).max(), label='0 mm')
plt.plot((bla2 - np.mean(bla1[25:30]))/(bla2 - np.mean(bla1[25:30])).max(), label='-10 mm')
plt.legend()
#######


x = [ -20, -10, -5.0, -2.5, 0.0, 2.5, 5.0, 10, 20]
uids = ['bcbb4b4d-304b-4132-8d35-f48dbf193757',
        'bb8c2456-7012-4d73-80e0-51a9883d6442',
        '304eb06d-1436-4441-a9fe-4798a6ed812a',
        '2479e7b0-dedc-44e9-8ed0-38c0a38f9dbf',
        '7edc70c3-3911-4e68-8244-b0c2b9485356',
        'ad7d10e3-af07-4aed-91b7-43c17216cd9d',
        '7804cf79-d1e8-48a3-9001-3cb91b4468a1',
        '20a5287e-e753-48ba-b46f-22c456ec0834',
        '3ce53b94-e6f0-422c-a7d8-f9b98293cac7']
plt.figure(1, clear=True)

fwhms = []
for uid in  uids:
    df = process_monitor_scan(db, uid, det_for_time_base='pil100k')
    _fwhm = _estimate_peak_fwhm_from_roll_scan(df, 'johann_main_crystal_motor_cr_main_roll', 'pil100k_stats1_total')
    fwhms.append(_fwhm)
    plt.plot(df.johann_main_crystal_motor_cr_main_roll, df.pil100k_stats1_total)

plt.figure(2, clear=True)
plt.plot(x, fwhms)




# johann_x = [-5, -2.329, 0.00, 2.5, 5]
# uids = ['7dfc734d-f160-41f4-873b-d580997d494d',
#         '7e7ff753-14b6-4cd0-bc32-e4e60f2cf2f1',
#         'd22bf7eb-68e7-4879-bca5-f6f44c3c0b52',
#         'abcd3a49-2b86-4088-99ff-e895e495bdb0',
#         '22f37dfb-a49f-4f2b-8cab-63fa518aa9bb']
from scipy.signal import savgol_filter
def estimate_center_and_width_of_peak(E, I):
    E_cen = E[np.argmax(np.abs(I))]
    # E_cen = np.sum(E * I) / np.sum(I)
    # x = np.abs(I - 0.5)
    e_low = E < E_cen
    e_high = E > E_cen
    x1 = np.interp(0.5, I[e_low], E[e_low])
    x2 = np.interp(0.5, I[e_high][np.argsort(I[e_high])], E[e_high][np.argsort(I[e_high])])
    # x1 = E[e_low][np.argmin(x[e_low])]
    # x2 = E[e_high][np.argmin(x[e_high])]
    fwhm = np.abs(x1 - x2)
    return E_cen, fwhm, x1, x2

def smooth_any_peak(x, y, n=4):
    # neglog_y = -np.log(y)
    # p = np.polyfit(x, neglog_y, n)
    # neglog_y_fit = np.polyval(p, x)
    # neglog_y_fit = savgol_filter(neglog_y, 5, 3)
    # y_fit = np.exp(-neglog_y_fit)
    y_fit = savgol_filter(y, 5, 3)
    return x, y, y_fit

# main
# 0 1.379
roll_key = 'johann_main_crystal_motor_cr_main_roll'
johann_x = [-7.5, -5.0, -2.5, 0, 2.5, 5.0, 7.5]
uids = ['f35fe432-df36-4527-8076-bc39dd32f50c',
        'ceec6052-d4aa-446e-bfa9-2e8aca6b1184',
        'c4637f41-e799-4575-9e1c-b6e5d269c7ea',
        '3de00f32-d2f4-4346-b901-adcd02a865c1',
        '7fdd3b29-596f-44a9-99d0-e9b7cc7fc4a3',
        '9f3e4a08-f20d-4ab7-adf8-140527802726',
        '863f88a2-e638-43e9-a940-10b100dce4e2']
#
#
roll_key = 'johann_aux2_crystal_motor_cr_aux2_roll'
johann_x = [-13570, -11070, -8570, -6070, -3570, -1070, 1430]
uids = ['6fc38e33-0629-4fdf-8951-42f0ede32240',
        '528e034b-0bd1-4696-b20f-8e3d3e55207b',
        'bd60cfde-71b1-402f-a131-4b2a4d629fcb',
        '5fca9e2d-a32d-43cc-bb6c-b2bc622f9ff1',
        'c4e97f52-17dc-43e5-ab8a-3af86c7a4f71',
        '01f876fe-9708-416e-aa6a-60deb42595ad',
        'ae86d1ce-5c70-4b44-8e37-97610ceca037'
      ]

roll_key = 'johann_aux3_crystal_motor_cr_aux3_roll'
johann_x = [-15700, -13200, -10700, -8200, -5700, -3200, -700]
uids = ['f32097cf-cd4a-44c7-85e7-cf18b79000d0',
        '1c5c2f8c-998b-4608-a0ef-7432ba51bc56',
        'd2cff6fe-2b51-4afe-90af-ae503949b660',
        '089adb71-2968-4442-854e-b8dae0012a8e',
        '3b7d6286-684e-4121-a3e1-c94f6133ef1f',
        'b773a138-a438-4f77-a43d-220970847e97',
        '9d145102-a11b-4a5d-b824-13485051f82d'

       ]

# elastic_fwhm = [1.139, 1.170, 1.181, 1.282, 1.367, 1.425]
# elastic_ecen = [8046.325, 8046.195, 8046.091, 8045.986, 8045.914, 8045.850]

e_cen = []
e_fwhm = []
int_max = []

plt.figure(1, clear=True)
plt.subplot(221)
for uid in uids:
    t = db[uid].table()
    _roll = t[roll_key].values
    _intensity = t.pil100k_stats1_total.values

    _intensity_smooth = savgol_filter(_intensity, 5, 3)
    _intensity_smooth = (_intensity_smooth - np.mean(_intensity_smooth[:3])) / (_intensity_smooth.max() - np.mean(_intensity_smooth[:3]))

    _e_cen, _e_fwhm, _e1, _e2 = estimate_center_and_width_of_peak(_roll, _intensity_smooth)# / _intensity_smooth.max())
    e_cen.append(_e_cen)
    e_fwhm.append(_e_fwhm)
    # int_max.append(_intensity.max())
    _int_max = np.mean(np.sort(_intensity)[-3:])
    int_max.append(_int_max)

    # plt.plot(_roll - _e_cen, _intensity)
    # plt.plot([_e1 - _e_cen, _e1 - _e_cen], [0, 1], 'k-')
    # plt.plot([_e2 - _e_cen, _e2 - _e_cen], [0, 1], 'k-')

    # plt.plot(_roll, _intensity , 'k.')
    plt.plot(_roll, _intensity_smooth, '-')
    plt.plot([_e1, _e1], [0, 1], 'k-')
    plt.plot([_e2, _e2], [0, 1], 'k-')
# plt.plot([-120, 120], [0.5, 0.5], 'k--')

plt.subplot(222)
plt.plot(johann_x, int_max, 'k.-')

ax = plt.subplot(224)
ax1 = ax.twinx()
ax.plot(johann_x, e_fwhm, 'r-')
# ax1.plot(johann_x, elastic_fwhm, 'b-')

plt.subplot(223)
# plt.plot(elastic_ecen, e_cen, 'k.-')
##

# PCL in (~100 um fwhm)
# main (Ge-660, Saint Gobain): fwhm=1.550
# aux2 (Ge-660, Alpyx): fwhm=1.862
# aux3 (Si-733, XRS): fwhm=1.686

# PCL out (~200 um fwhm)
# main (Ge-660, Saint Gobain):  fwhm=1.572
# aux2 (Ge-660, Alpyx): fwhm=1.953
# aux3 (Si-733, XRS): fwhm=1.698





_config = {'R': 1000.0,
 'crystal': 'Si',
 'hkl': [4, 4, 4],
 'parking': {'motor_det_x': -77.000020062,
  'motor_det_th1': 0.0,
  'motor_det_th2': 0.0,
  'motor_cr_assy_x': -2.00002624199999,
  'motor_cr_assy_y': 7.181946,
  'motor_cr_main_roll': 690.0,
  'motor_cr_main_yaw': -530.0,
  'motor_cr_aux2_x': 500.0,
  'motor_cr_aux2_y': -8500.0,
  'motor_cr_aux2_roll': 1419.5590000000002,
  'motor_cr_aux2_yaw': -1500.0,
  'motor_cr_aux3_x': 0.0,
  'motor_cr_aux3_y': -8900.0,
  'motor_cr_aux3_roll': 675.0,
  'motor_cr_aux3_yaw': -669.0},
 'roll_offset': 11.5,
 'det_offsets': {'motor_det_th1': 68.99965625,
  'motor_det_th2': -69.00037499999999},
 'det_focus': 0,
 'bragg_registration': {'pos_nom': {'motor_det_x': [334.70185507125404, 317.89533995746365],
  'motor_det_th1': [13.05490586149521, 15.890696395387565],
  'motor_det_th2': [-34.30660500426744, -35.59521858587816],
  'motor_cr_assy_x': [980.8515088144756, 983.2515265275326],
  'motor_cr_assy_y': [7.181946, 7.181946],
  'motor_cr_main_roll': [1564.1504286138877, 2337.7389047547035],
  'motor_cr_main_yaw': [-530.0, -530.0],
  'motor_cr_aux2_x': [325.8761543546383, 350.6293395377225],
  'motor_cr_aux2_y': [-6632.870595321352, -6775.926019273891],
  'motor_cr_aux2_roll': [2238.7301205935255, 3016.6572011456146],
  'motor_cr_aux2_yaw': [-766.185324134957, -874.8615507076067],
  'motor_cr_aux3_x': [-174.12384564536174, -149.3706604622775],
  'motor_cr_aux3_y': [-7032.870595321352, -7175.926019273891],
  'motor_cr_aux3_roll': [1494.1711205935255, 2272.0982011456144],
  'motor_cr_aux3_yaw': [-1402.814675865043, -1294.1384492923933]},
 'pos_act': {'motor_det_x': [332.7006863615, 315.8941862775],
  'motor_det_th1': [13.0, 15.8359375],
  'motor_det_th2': [-34.2825, -35.5715625],
  'motor_cr_assy_x': [978.164640021, 980.564658526],
  'motor_cr_assy_y': [7.181946, 7.181946],
  'motor_cr_main_roll': [1460.491, 2239.2870000000003],
  'motor_cr_main_yaw': [-530.0, -529.996],
  'motor_cr_aux2_x': [-10000.0, -9975.216],
  'motor_cr_aux2_y': [-7032.0, -7175.03],
  'motor_cr_aux2_roll': [798.173, 1569.9470000000001],
  'motor_cr_aux2_yaw': [-1043.593, -1070.273],
  'motor_cr_aux3_x': [-5000.0, -4975.198],
  'motor_cr_aux3_y': [-7032.0, -7175.084],
  'motor_cr_aux3_roll': [1528.346, 2300.821],
  'motor_cr_aux3_yaw': [-1206.981, -1158.1390000000001]}},
 'energy_calibration': {'x_nom': [], 'x_act': [], 'n_poly': 2},
 'enabled_crystals': {'main': True, 'aux2': True, 'aux3': True},
 'initialized': True}


rowland_circle.set_spectrometer_config(_config)


#####

df = []

for _energy in np.linspace(8005, 8065, 101):
    _pos = johann_emission._forward({'energy' :_energy})
    for k in _pos.keys():
        _pos[k] = float(_pos[k])
    _pos['bragg'] = rowland_circle.e2bragg(_energy)
    _pos['energy'] = float(_energy)
    df.append(_pos)


df = pd.DataFrame(df)


key = 'motor_cr_assy_x'


plt.figure(1, clear=True)

c = 'bragg'
plt.plot(df['energy'], (df[c] - df[c].values[0]) / (df[c].values[-1] - df[c].values[0]))
ax = plt.gca()
for c in df.columns[:-2]:
    _ax = ax.twinx()
    plt.plot(df['energy'], (df[c] - df[c].values[0]) / (df[c].values[-1] - df[c].values[0]))
    # _ax.plot([df['energy'].values[0], df['energy'].values[-1]], [df[c].values[0], df[c].values[-1]], 'k-')

plt.plot([df['energy'].values[0], df['energy'].values[-1]], [0, 1], 'k-')

# plt.plot
# plt.plot()





##



x, y, y_fit = fit_any_peak(_roll, _intensity, n=7)
plt.figure(2, clear=True)
plt.plot(x, y)
plt.plot(x, y_fit)


##########################################

all_scans = []

for year, cycles in zip([2022, 2023], [[1, 2, 3], [1]]):
    for cycle in cycles:
        proposals = os.listdir(f"{ROOT_PATH}/{USER_PATH}/{year}/{cycle}")
        for proposal in proposals:
            fpath = f"{ROOT_PATH}/{USER_PATH}/{year}/{cycle}/{proposal}/scan_manager.json"
            try:
                with open(fpath, 'r') as f:
                    _list_local = json.loads(f.read())
            except Exception as e:
                print(e)
            all_scans.extend(_list_local)

#################

t_apb = hdr.table(stream_name='apb_stream', fill=True)['apb_stream'][1]
apb_time = t_apb[:, 0]
apb_sig = t_apb[:, 5]
apb_sig -= apb_sig.min()
apb_sig /= apb_sig.max()


t_trig = hdr.table(stream_name='apb_trigger_xs', fill=True)['apb_trigger_xs'][1]
trig_time = t_trig[:, 0]
trig_sig = t_trig[:, 1]


plt.figure(1, clear=True)
plt.plot(apb_time, apb_sig)
plt.plot(trig_time, trig_sig)

# plt.plot(apb_time, t_apb[:, 6])

########################


motor = johann_main_crystal.motor_cr_main_roll


RE(bp.rel_list_scan([pil100k], motor, np.linspace(-50, 50, 3)))





######




uids = ['22e37f88-fef2-4030-8996-fc9a42dc75ed',
 'fc9f5a08-ee9e-4024-9f4a-e72a6e15ba3e',
 'bb1c30e0-1ec9-4104-a59f-a320ea3c0525',
 '483cd3e2-ce45-429d-a503-623d972dd031',
 '9e93d969-b069-4302-a3b4-a6a0a21d4af9',
 'cc9db346-6648-4c44-846d-e27ce6e9c227',
 'd0c98d91-1848-4e32-ad45-add2fa0bb253',
 '1ec329b1-9f88-4494-8830-4ad92bdc0bc4',
 'c6f8f7b6-4a03-448e-b1cb-0dd4e5d59458',
 '1f9f26bb-249d-421e-b088-ccd1598189ce',
 '5933bc80-1dce-4ae9-a2f4-b7ab7b2e9b96',
 '1a0df1df-3e5a-4235-9948-3b186744bf91',
 '7c3d76ae-157f-4197-9a00-68d220b3af4d',
 '036851bf-00f8-413f-a31e-39e0f84ba99d',
 '3440cc18-f0a9-4b01-8d1f-eed2df894021',
 '8a6cc88a-71cc-4114-a522-a8c6a9313cb2']

#
uids = list(db.v2.search({'sample_name': 'Fe_EDTA', 'sample_condition': 'RT_NH3_5ml_min', 'scan_name': 'v2c 0_3eV'}))


t = db['22e37f88-fef2-4030-8996-fc9a42dc75ed'].table(fill=True)

plt.figure(); plt.imshow(np.sum(np.array(t.pil100k_image.tolist()).squeeze(), axis=0)[37: 160, 250: 270], vmin=0, vmax=10)
plt.figure(); plt.imshow(np.sum(np.array(t.pil100k_image.tolist()).squeeze(), axis=0)[37: 160, 270: 286], vmin=0, vmax=10)
plt.figure(); plt.imshow(np.sum(np.array(t.pil100k_image.tolist()).squeeze(), axis=0)[37: 160, 286: 304], vmin=0, vmax=10)

def compare_rois(uid, x1, x2, y1, y2, title=''):
    t = db[uid].table(fill=True).copy()
    npts = t.shape[0]
    roi_signal = np.zeros(npts)
    for i in range(npts):
        image = t.pil100k_image[i + 1].squeeze()
        # if i==70: plt.figure(); plt.imshow(image[x1:x2, y1:y2], vmin=0, vmax=5); plt.title(title)
        roi_signal[i] = np.sum(image[x1:x2, y1:y2])
    return roi_signal

roi1 = []
roi2 = []
roi3 = []

for uid in uids:
    print(uid)
    _roi1 = compare_rois(uid, x1=37, x2=160, y1=250, y2=270, title='roi1')
    _roi2 = compare_rois(uid, x1=37, x2=160, y1=270, y2=286, title='roi2')
    _roi3 = compare_rois(uid, x1=37, x2=160, y1=286, y2=304, title='roi3')
    roi1.append(_roi1)
    roi2.append(_roi2)
    roi3.append(_roi3)

roi1_av = np.mean(np.array(roi1), axis=0)
roi2_av = np.mean(np.array(roi2), axis=0)
roi3_av = np.mean(np.array(roi3), axis=0)



plt.figure()
plt.plot(roi1_av, label='aux2')
plt.plot(roi2_av, label='main')
plt.plot(roi3_av, label='aux3')

plt.legend()

def remove_bkg(roi, n1=5, n2=-5):
    x = np.arange(roi.size)
    x1 = x[n1]
    x2 = x[n2]
    mask = (x <= x1) | (x >= x2)
    x_mask = x[mask]
    roi_mask = roi[mask]
    p = np.polyfit(x_mask, roi_mask, 1)
    roi_bkg = np.polyval(p, x)
    roi_norm = (roi - roi_bkg) / np.sum(roi - roi_bkg)
    return roi_norm

plt.figure()
plt.plot(remove_bkg(roi1_av), label='aux2')
plt.plot(remove_bkg(roi2_av), label='main')
plt.plot(remove_bkg(roi3_av), label='aux3')

plt.legend()




my_volt = EpicsSignal('XF:08IDB-CT{DIODE-Box_B1:13}InCh0:Data-I', name='my_volt')
my_volt_conv = Signal(name='my_volt_conv')

def update_my_volt_conv(value, **kwargs):
    if value >=10:
        my_volt_conv.put(0)
    else:
        my_volt_conv.put(value)

my_volt.subscribe(update_my_volt_conv)


class PotentiostatVoltage(EpicsSignal):
    def get(self):
        v = super().get()
        if v > 10:
            return 0
        else:
            return v

potentiostat_voltage = PotentiostatVoltage('XF:08IDB-CT{DIODE-Box_B1:13}InCh0:Data-I', name='my_volt')

####%%

# scan_dict = scan_manager.standard_scan_dict('Cu', 'K')
scan_parameters = { 'element': 'Cu',
                    'edge': 'K',
                    'e0': xraydb.xray_edge('Cu', 'K').energy,
                    'preedge_start': -200,
                    'XANES_start': -30,
                    'XANES_end': 50,
                    'EXAFS_end': 16,
                    'type': 'standard',
                    'preedge_duration': 4,
                    'edge_duration': 6,
                    'postedge_duration': 20,
                    'preedge_flex': 0.5,
                    'postedge_flex': 0.3,
                    'pad': 0.0,
                    'repeat': 1,
                    'single_direction': True,
                    'revert': True,
                    'filename': ''}
scan_parameters_fly = {**scan_parameters}
scan_parameters_fly['XANES_end'] = 950
scan_parameters_fly['preedge_duration'] = 2
scan_parameters_fly['edge_duration'] = 26
scan_parameters_fly['postedge_duration'] = 2
scan_manager.trajectory_creator.define_from_dict(scan_parameters_fly)
# scan_manager.trajectory_creator.interpolate()
# scan_manager.trajectory_creator.compute_time_per_bin()

_time = scan_manager.trajectory_creator.time
_energy = scan_manager.trajectory_creator.energy
# _energy_fly = scan_manager.trajectory_creator.e_bin
# _time_dwell_fly = scan_manager.trajectory_creator.time_per_bin

scan_parameters_step = {**scan_parameters,
                        'preedge_stepsize': 2,
                        'XANES_stepsize': 0.25,
                        'EXAFS_stepsize': 0.05,
                        'preedge_dwelltime': 1,
                        'XANES_dwelltime': 1,
                        'EXAFS_dwelltime': 1,
                        'k_power': 1}
# _energy_step, _dwell_step, _time_step = generate_energy_grid_from_dict(scan_parameters_step)
# _time_step = _time_step[::-1]

_energy_step, _, _ = generate_energy_grid_from_dict(scan_parameters_step)
_energy_step = _energy_step[::-1]

_energy_step = _energy_step / (_energy_step.max() - _energy_step.min()) * (_energy.max() - _energy.min())
_energy_step = _energy_step - _energy_step.min() + _energy.min()

_k_mask = _energy_step > (scan_parameters['e0'] + scan_parameters['XANES_end'])
_k_step = xray.e2k(_energy_step[_k_mask], scan_parameters['e0'])
_k_power = 2

time_dwell = np.ones(_energy_step.size)
time_dwell[_k_mask] = time_dwell[_k_mask] * (_k_step / _k_step.min()) ** _k_power
_time_step = np.cumsum(time_dwell)

time_dwell = time_dwell / (_time_step.max() - _time_step.min())* 30
_time_step = _time_step / (_time_step.max() - _time_step.min())* 30
_time_step -= _time_step.min()

_energy_edges = np.hstack([_energy_step[0], _energy_step[:-1] + np.diff(_energy_step)/2, _energy_step[-1]])
_time_edges = np.interp(_energy_edges, _energy, _time)
_time_dwell_fly = np.diff(_time_edges)

plt.figure(1, clear=True )
plt.subplot(211)
plt.plot(_time, _energy)
plt.plot(_time_step, _energy_step)

plt.subplot(212)
plt.semilogy(_energy_step, _time_dwell_fly)#, 'k.-')
plt.semilogy(_energy_step, time_dwell)#, 'k.-')

_energy_step_fine = np.interp(_time, _time_step, _energy_step)

def dy_dx(x, y):
    return x[:-1] + np.diff(x), np.diff(y) / np.diff(x)

_time_v, _energy_step_fine_v = dy_dx(_time, _energy_step_fine)
_time_a, _energy_step_fine_a = dy_dx(_time_v, _energy_step_fine_v)

plt.figure(2, clear=True)
plt.subplot(311)
plt.plot(_time, _energy_step_fine)

plt.subplot(312)
plt.plot(_time_v, _energy_step_fine_v)

plt.subplot(313)
plt.plot(_time_a, _energy_step_fine_a)

##########

x = xlive_gui.widget_sample_manager.detached_ui

x.treeWidget_samples.clear()
treeWidget_tracking_dict = {}

def update_sample_tree(x):
    # print_debug('updating treeWidget_samples: start')
    #
    for i, sample in enumerate(x.sample_manager.samples):

        if not sample.archived:
            # print_debug(f'{i=}, {sample.name=}')
            # print_debug(f'making sample item: start')

            if sample.uid not in treeWidget_tracking_dict.keys():
                # print('creating the sample')
                name = sample.name
                npts = sample.number_of_points
                npts_fresh = sample.number_of_unexposed_points
                sample_str = f"{name} ({npts_fresh}/{npts})"
                sample_item = x._make_sample_item(sample_str, i)
                treeWidget_tracking_dict[sample.uid] = sample_item
            # x.treeWidget_samples.addItem(sample_item)
            else:
                # print('sample exists')
                sample_item = treeWidget_tracking_dict[sample.uid]
            # fsdga

            if (i == x._currently_selected_index) or ((i == len(x.sample_manager.samples)) and
                                                         (x._currently_selected_index == -1)):
                sample_item.setExpanded(True)
            else:
                sample_item.setExpanded(False)

            for j in range(sample.number_of_points):
                point_data = sample.position_data.iloc[j]
                point_uid = point_data['sample_point_uid']
                if point_uid not in treeWidget_tracking_dict.keys():
                    # print_debug(f'making sample point item: start')
                    point_str, point_exposed = sample.index_point_info_for_qt_item(j)
                    point_item = x._make_sample_point_item(sample_item, point_str, j, point_exposed)
                    treeWidget_tracking_dict[point_uid] = point_item



                # print_debug(f'making sample point item: end')
            # print_debug(f'making sample item: end')
    # print_debug('updating treeWidget_samples: end')
                # x._make_sample_point_item(sample_item, point_str, j, point_exposed)
                # print_debug(f'making sample point item: end')
            # print_debug(f'making sample item: end')
    # print_debug('updating treeWidget_samples: end')


update_sample_tree(x)


sample = Sample('bla', coordinates=[{'x': 0.0, 'y': 0.0, 'z': 0.0, 'th': 0.0}])

{'x': sample.position_data.iloc[0]['x'], 'y': sample.position_data.iloc[0]['y'], 'z': sample.position_data.iloc[0]['z'], 'th': sample.position_data.iloc[0]['th']}

###

from xas.db_io import load_apb_dataset_from_db, translate_apb_dataset, load_apb_trig_dataset_from_db, load_xs3_dataset_from_db, load_pil100k_dataset_from_db, load_apb_dataset_only_from_db, translate_apb_only_dataset
from xas.interpolate import interpolate


def interpolate_data_for_fly_scan_and_plot(db, uid, label=''):
    hdr = db[uid]
    stream_names = hdr.stream_names
    apb_df, energy_df, energy_offset = load_apb_dataset_from_db(db, uid)
    raw_dict = translate_apb_dataset(apb_df, energy_df, energy_offset)
    for stream_name in stream_names:

        if stream_name == 'xs_stream':
            apb_trigger_xs_timestamps = load_apb_trig_dataset_from_db(db, uid, stream_name='apb_trigger_xs')
            xs3_dict = load_xs3_dataset_from_db(db, uid, apb_trigger_xs_timestamps)
            raw_dict = {**raw_dict, **xs3_dict}

    df = interpolate(raw_dict)
    plt.plot(df.energy, df.xs_ch02_roi04, label=label)


plt.figure()
interpolate_data_for_fly_scan_and_plot(db, '89daed24-678e-4a68-985b-3ffe7e2fafd2', label='UP RT')
interpolate_data_for_fly_scan_and_plot(db, '1d779dd5-6c90-4523-b6fc-e4d6cb3ae468', label='DOWN RT')
interpolate_data_for_fly_scan_and_plot(db, 'eddd649a-0a67-43ad-b381-46e6aa9f915d', label='UP 300C')
interpolate_data_for_fly_scan_and_plot(db, '5df31038-f505-46cc-adab-d9ed745d3975', label='DOWN 300C')
plt.legend()





import requests
os.system('cd ~')
proposal = '317775'
headers = {'accept': 'application/json',}
proposal_info = requests.get(f'https://api.nsls2.bnl.gov/v1/proposal/{proposal}', headers=headers).json()

user_names = []
for user in proposal_info['proposal']['users']:
    user_names.append(f"{user['last_name']}, {user['first_name']}")
name_list = '" "'.join(user_names)
os.system(f'./search_users.sh -- "{name_list}" > output.txt')


file_path = 'output.txt'
with open(file_path, 'r') as file:
    file_content = file.read()
strings = file_content.split('\n')
logins = []
for string in strings:
    if (string.find(',') > -1) and (string.find('Running command') == -1):
        inds = [index for index, char in enumerate(string) if char == '|']
        logins.append(string[(inds[1]+1):inds[2]].strip())

for name in logins:
    os.systemf(f'n2sn_add_user --login  {name} GUACVIEW')

with open("logins.txt", "w") as f:
    for login in logins:
        f.write(login + "\n")


for j in range (1,33):
    qitem = QtWidgets.QCheckBox(f'Channel {j}')
    qitem.setCheckState(True)
    qitem.setTristate(False)
    self.verticalLayout_channels.addWidget(qitem)
    setattr(self, f'checkbox_ch{j}',qitem)

for jj in range(1, 33):
    _mca = getattr(a.ge_detector._channels, f'mca{jj}').get()
    mca = np.array(_mca[0])
    energy = np.array(range(len(mca)))
    a.figure_mca.ax.plot(energy, mca, label=f'Channel {jj}')

for j in range(1, 33):


    for key, val in rois.items():
        spinbox = QtWidgets.QSpinBox()
        a.gridLayout_roi.addWidget(spinbox, j,  val[0])
        setattr(a, f'spinbox_ch{j}_roi{key}_low', spinbox)
        spinbox = QtWidgets.QSpinBox()
        a.gridLayout_roi.addWidget(spinbox, j, val[1])
        setattr(a, f'spinbox_ch{j}_roi{key}_high', spinbox)
        label = QtWidgets.QLabel('')
        a.gridLayout_roi.addWidget(label, j, val[1])
        setattr(a, f'label_ch{j}_roi{key}_counts', label)



import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit



# Define the Gaussian function
def gaussian(x, a, x0, sigma):
    return a * np.exp(-((x - x0) ** 2) / (2 * sigma ** 2))

# # Generate synthetic data for testing
# x_data = np.linspace(-10, 10, 100)
# y_data = gaussian(x_data, 10, 0, 2) + 0.5 * np.random.normal(size=x_data.size)  # Adding noise

hdr = db[-1]
t8= hdr.table()

x_data  = t8['hhm_energy']
y_data = t8['xs_channel4_rois_roi03_value']/max(t8['xs_channel4_rois_roi03_value'])
# Fit the Gaussian curve
popt, _ = curve_fit(gaussian, x_data, y_data, p0=[1, 9986, 2])

a, x0, sigma = popt


# Compute FWHM (Full Width at Half Maximum)
FWHM = 2 * np.sqrt(2 * np.log(2)) * sigma
print(f'FWHM: {FWHM}')

# Plot the results
plt.scatter(x_data, y_data, label='Data', color='red', s=10)
plt.plot(x_data, gaussian(x_data, *popt), label='Fitted Gaussian', color='blue')
plt.axhline(y=a/2, color='green', linestyle='--', label='Half Maximum')
plt.legend()
plt.xlabel('X')
plt.ylabel('Y')
plt.title('Gaussian Fit with FWHM')
plt.show()

