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
    plt.clf()
    plt.plot(energy, hhmy, 'k.')
    plt.plot(energy_grid, hhmy_fit_grid, 'r-')
    # plt.plot(energy_grid, hhmy_fit_grid_poly, 'b-')

fit_hhmy(offset=0)

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

for i in range(-5, -200, -1):
   hdr = db[i]
   if 'experiment' in hdr.start.keys():
       if hdr.start['experiment'] == 'collect_n_exposures':
           process_interpolate_bin_from_uid(i, db)



'''
In [1]: [Queue] (2022-04-11 11:08:59.173233) Execution of plan fly_scan_plan starting...
[Flyer] (2022-04-11 11:08:59.235931) Preparing mono starting...
[Flyer] (2022-04-11 11:09:03.264127) Preparing mono complete
[Flyer] (2022-04-11 11:09:03.264235) Fly scan staging starting...
[Flyer] (2022-04-11 11:09:03.376111) 	start staging apb_stream ...
[Flyer] (2022-04-11 11:09:03.378491) 	start staging pb9_enc1 ...
[Flyer] (2022-04-11 11:09:03.379319) Fly scan staging complete
CA.Client.Exception...............................................
    Warning: "Channel write request failed"
    Context: "op=1, channel=XF:08IDA-CT{Enc09:1}ID:File.VAL, type=DBR_CHAR, count=30, ctx="XF:08IDA-CT{Enc09:1}ID:File""
    Source File: ../oldChannelNotify.cpp line 158
    Current Time: Mon Apr 11 2022 11:09:03.379631513
..................................................................
[Flyer] (2022-04-11 11:09:03.575839) Detector kickoff starting...
Mon Apr 11 11:09:03 2022 >>> User Shutter opening...
[Flyer] (2022-04-11 11:09:06.165611) Detector kickoff complete
[Flyer] (2022-04-11 11:09:06.165883) Mono trajectory motion starting...
[Flyer] (2022-04-11 11:09:37.273874) Mono trajectory motion complete
[Flyer] (2022-04-11 11:09:37.274177) Detector complete starting...
(2022-04-11 11:09:37.274408) apb_stream complete starting
(2022-04-11 11:09:37.277092) apb_stream complete done
Mon Apr 11 11:09:37 2022 >>> pb9_enc1 complete starting...
Mon Apr 11 11:09:39 2022 Moving file from /mnt/xf08ida-ioc1/en_566ffce6 to /nsls2/data/iss/legacy/raw/2022/04/11/en_566ffce6
'''


########


def plot_trig_data(uid):
    hdr = db[uid]
    t = hdr.table(stream_name='apb_trigger_pil100k', fill=True)
    d = t['apb_trigger_pil100k'][1]
    ts, trig = d[:, 0], d[:, 1]

    t_apb = hdr.table(stream_name='apb_stream', fill=True)
    d_apb = t_apb['apb_stream'][1]
    d_apb.shape
    ts_apb = d_apb[:, 0]
    trig_apb = d_apb[:, 6]
    trig_apb -= trig_apb.min()
    trig_apb /= trig_apb.max()

    plt.figure(); plt.plot(ts_apb, trig_apb); plt.plot(ts, trig)

plot_trig_data('57f8dc26-bdc1-4e2b-b6ee-5d74876804d9')
plot_trig_data('68cf1eef-6a76-4597-818c-2bd02ae47867')


#########
def plot_scan(uid, *args, dx=0, dy=0, ys=1, **kwargs):
    hdr = db[uid]
    t = hdr.table()
    plt.plot(t.sample_stage_y + dx, (t.apb_ave_ch2 + dy) * ys, *args, **kwargs)


plt.figure(1, clear=True)
plot_scan( 'afa2b264-bfbe-43b6-aaad-1fd9dbbcd5ad', 'b-', dx=56.74, dy=123, ys=1/155.48, label='Z=-1.77')
plot_scan('f0b79b3e-4c48-4c94-99cf-6ff542f38316', 'm-', dx=56.593, dy=116, ys=1/148.5, label='Z= 2.69')
plt.hlines([0.05, 0.95], -0.5, 0.5, colors='k')
plt.vlines([-0.12, 0.11], -1, 2, colors='m', linestyles='--')
plt.vlines([-0.065, 0.065], -1, 2, colors='b', linestyles='--')

plt.legend()
plt.xlim(-0.3, 0.3)
plt.ylim(-0.1, 1.1)





