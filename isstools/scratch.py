
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
        RE(bps.mv(hhm.energy, 15000))
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


