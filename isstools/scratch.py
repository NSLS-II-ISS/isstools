
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



df = pd.read_json('/nsls2/xf08id/Sandbox/Beamline_components/2021_09_09_beamline_tabulation/beamline_hhmy_hhrmy_tabulation.json')
df2 = pd.read_json('/nsls2/xf08id/Sandbox/Beamline_components/2021_09_09_beamline_tabulation/beamline_hhmy_hhrmy_tabulation_high_energies.json')
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


