import pkg_resources
import inspect
import re
import os
from subprocess import call
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtCore import QThread, QSettings
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import time as ttime
import numpy as np

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_run.ui')

from isstools.xiaparser import xiaparser

class UIRun(*uic.loadUiType(ui_path)):
    def __init__(self,
                 plan_funcs,
                 db,
                 shutters,
                 adc_list,
                 enc_list,
                 xia,
                 html_log_func,
                 parent_gui,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()

        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        self.db = db
        if self.db is None:
            self.run_start.setEnabled(False)

        self.shutters = shutters
        self.adc_list = adc_list
        self.enc_list = enc_list
        self.xia = xia
        self.html_log_func = html_log_func
        self.parent_gui = parent_gui

        self.run_type.addItems(self.plan_funcs_names)
        self.run_start.clicked.connect(self.run_scan)

        self.pushButton_scantype_help.clicked.connect(self.show_scan_help)

        self.run_type.currentIndexChanged.connect(self.populateParams)

        self.params1 = []
        self.params2 = []
        self.params3 = []
        if len(self.plan_funcs) != 0:
            self.populateParams(0)

    def addCanvas(self):
        self.figure = Figure()
        self.figure.set_facecolor(color='#FcF9F6')
        self.canvas = FigureCanvas(self.figure)
        self.figure.ax = self.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self, coordinates=True)
        self.toolbar.setMaximumHeight(25)
        self.plots.addWidget(self.toolbar)
        self.plots.addWidget(self.canvas)
        self.canvas.draw_idle()

    def run_scan(self):
        if self.run_type.currentText() == 'get_offsets':
            for shutter in [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type == 'PH' and
                                            self.shutters[shutter].state.read()['{}_state'.format(shutter)][
                                                'value'] != 1]:
                shutter.close()
                while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 1:
                    QtWidgets.QApplication.processEvents()
                    ttime.sleep(0.1)

        else:
            for shutter in [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type != 'SP']:
                if shutter.state.value:
                    ret = self.questionMessage('Shutter closed',
                                               'Would you like to run the scan with the shutter closed?')
                    if not ret:
                        print('Aborted!')
                        return False
                    break

        # Send sampling time to the pizzaboxes:
        value = int(round(float(self.analog_samp_time) / self.adc_list[0].sample_rate.value * 100000))

        for adc in self.adc_list:
            adc.averaging_points.put(str(value))

        for enc in self.enc_list:
            enc.filter_dt.put(float(self.enc_samp_time) * 100000)

        if self.xia.input_trigger is not None:
            self.xia.input_trigger.unit_sel.put(1)  # ms, not us
            self.xia.input_trigger.period_sp.put(int(self.xia_samp_time))

        self.comment = self.params2[0].text()
        if (self.comment):
            print('\nStarting scan...')

            # Get parameters from the widgets and organize them in a dictionary (run_params)
            run_params = {}
            for i in range(len(self.params1)):
                if (self.param_types[i] == int):
                    run_params[self.params3[i].text().split('=')[0]] = self.params2[i].value()
                elif (self.param_types[i] == float):
                    run_params[self.params3[i].text().split('=')[0]] = self.params2[i].value()
                elif (self.param_types[i] == bool):
                    run_params[self.params3[i].text().split('=')[0]] = bool(self.params2[i].checkState())
                elif (self.param_types[i] == str):
                    run_params[self.params3[i].text().split('=')[0]] = self.params2[i].text()

            # Erase last graph
            self.figure.ax.clear()
            self.toolbar._views.clear()
            self.toolbar._positions.clear()
            self.toolbar._update_view()
            self.canvas.draw_idle()

            self.filepaths = []
            self.current_uid_list = []
            process_after_scan = self.checkBox_parse_after_scan.checkState()

            # Run the scan using the dict created before
            for uid in self.plan_funcs[self.run_type.currentIndex()](**run_params, ax=self.figure.ax):

                if self.plan_funcs[self.run_type.currentIndex()].__name__ == 'get_offsets' or uid == None:
                    return

                self.current_uid_list.append(uid)
                if process_after_scan:
                    self.parse_scans(uid)
                    self.create_log_scan(self.current_uid, self.figure)

            if not process_after_scan:
                for uid in self.current_uid_list:
                    self.parse_scans(uid)
                    self.create_log_scan(self.current_uid, self.figure)

            if self.checkBox_auto_process.checkState() > 0 and self.parent_gui.widget_processing.active_threads == 0:
                self.parent_gui.tabWidget.setCurrentIndex(
                    [self.parent_gui.tabWidget.tabText(index) for index in range(self.parent_gui.tabWidget.count())].index('Processing'))
                self.parent_gui.widget_processing.selected_filename_bin = self.filepaths
                self.parent_gui.widget_processing.label_24.setText(
                    ' '.join(filepath[filepath.rfind('/') + 1: len(filepath)] for filepath in self.filepaths))
                self.parent_gui.widget_processing.process_bin_equal()

        else:
            print('\nPlease, type the name of the scan in the field "name"\nTry again')

    def show_scan_help(self):
        title = self.run_type.currentText()
        message = self.plan_funcs[self.run_type.currentIndex()].__doc__
        QtWidgets.QMessageBox.question(self,
                                       'Help! - {}'.format(title),
                                       message,
                                       QtWidgets.QMessageBox.Ok)

    def parse_scans(self, uid):
        # Erase last graph
        self.figure.ax.clear()
        self.toolbar._views.clear()
        self.toolbar._positions.clear()
        self.toolbar._update_view()

        year = self.db[uid]['start']['year']
        cycle = self.db[uid]['start']['cycle']
        proposal = self.db[uid]['start']['PROPOSAL']
        # Create dirs if they are not there
        log_path = '/GPFS/xf08id/User Data/'
        if log_path[-1] != '/':
            log_path += '/'
        log_path = '{}{}.{}.{}/'.format(log_path, year, cycle, proposal)
        if (not os.path.exists(log_path)):
            os.makedirs(log_path)
            call(['setfacl', '-m', 'g:iss-staff:rwx', log_path])
            call(['chmod', '770', log_path])

        log_path = log_path + 'log/'
        if (not os.path.exists(log_path)):
            os.makedirs(log_path)
            call(['setfacl', '-m', 'g:iss-staff:rwx', log_path])
            call(['chmod', '770', log_path])

        snapshots_path = log_path + 'snapshots/'
        if (not os.path.exists(snapshots_path)):
            os.makedirs(snapshots_path)
            call(['setfacl', '-m', 'g:iss-staff:rwx', snapshots_path])
            call(['chmod', '770', snapshots_path])

        try:
            self.current_uid = uid
            if self.current_uid == '':
                self.current_uid = self.db[-1]['start']['uid']

            if 'xia_filename' in self.db[self.current_uid]['start']:
                # Parse xia
                xia_filename = self.db[self.current_uid]['start']['xia_filename']
                xia_filepath = 'smb://xf08id-nas1/xia_data/{}'.format(xia_filename)
                xia_destfilepath = '/GPFS/xf08id/xia_files/{}'.format(xia_filename)
                smbclient = xiaparser.smbclient(xia_filepath, xia_destfilepath)
                try:
                    smbclient.copy()
                except Exception as exc:
                    if exc.args[1] == 'No such file or directory':
                        print('*** File not found in the XIA! Check if the hard drive is full! ***')
                    else:
                        print(exc)
                    print('Abort current scan processing!\nDone!')
                    return

            self.current_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/' \
                                    '{}.txt'.format(self.db[self.current_uid]['start']['year'],
                                                    self.db[self.current_uid]['start']['cycle'],
                                                    self.db[self.current_uid]['start']['PROPOSAL'],
                                                    self.db[self.current_uid]['start']['name'])
            if os.path.isfile(self.current_filepath):
                iterator = 2
                while True:
                    self.current_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/' \
                                            '{}-{}.txt'.format(self.db[self.current_uid]['start']['year'],
                                                               self.db[self.current_uid]['start']['cycle'],
                                                               self.db[self.current_uid]['start']['PROPOSAL'],
                                                               self.db[self.current_uid]['start']['name'],
                                                               iterator)
                    if not os.path.isfile(self.current_filepath):
                        break
                    iterator += 1

            self.filepaths.append(self.current_filepath)
            self.parent_gui.widget_processing.gen_parser.load(self.current_uid)

            key_base = 'i0'
            if 'xia_filename' in self.db[self.current_uid]['start']:
                key_base = 'xia_trigger'
            self.parent_gui.widget_processing.gen_parser.interpolate(key_base=key_base)

            division = self.parent_gui.widget_processing.gen_parser.interp_arrays['i0'][:, 1] / self.parent_gui.widget_processing.gen_parser.interp_arrays['it'][:, 1]
            division[division < 0] = 1
            self.figure.ax.plot(self.parent_gui.widget_processing.gen_parser.interp_arrays['energy'][:, 1], np.log(division))
            self.figure.ax.set_xlabel('Energy (eV)')
            self.figure.ax.set_ylabel('log(i0 / it)')

            # self.gen_parser should be able to generate the interpolated file

            if 'xia_filename' in self.db[self.current_uid]['start']:
                # Parse xia
                xia_parser = self.xia_parser
                xia_parser.parse(xia_filename, '/GPFS/xf08id/xia_files/')
                xia_parsed_filepath = self.current_filepath[0: self.current_filepath.rfind('/') + 1]
                xia_parser.export_files(dest_filepath=xia_parsed_filepath, all_in_one=True)

                try:
                    if xia_parser.channelsCount():
                        length = min(xia_parser.pixelsCount(0), len(self.parent_gui.widget_processing.gen_parser.interp_arrays['energy']))
                        if xia_parser.pixelsCount(0) != len(self.parent_gui.widget_processing.gen_parser.interp_arrays['energy']):
                            raise Exception(
                                "XIA Pixels number ({}) != Pizzabox Trigger file ({})".format(xia_parser.pixelsCount(0),
                                                                                              len(
                                                                                                  self.parent_gui.widget_processing.gen_parser.interp_arrays[
                                                                                                      'energy'])))
                    else:
                        raise Exception("Could not find channels data in the XIA file")
                except Exception as exc:
                    print('***', exc, '***')

                mcas = []
                if 'xia_rois' in self.db[self.current_uid]['start']:
                    xia_rois = self.db[self.current_uid]['start']['xia_rois']
                    if 'xia_max_energy' in self.db[self.current_uid]['start']:
                        xia_max_energy = self.db[self.current_uid]['start']['xia_max_energy']
                    else:
                        xia_max_energy = 20

                    self.figure.ax.clear()
                    self.toolbar._views.clear()
                    self.toolbar._positions.clear()
                    self.toolbar._update_view()
                    for mca_number in range(1, xia_parser.channelsCount() + 1):
                        if '{}_mca{}_roi0_high'.format(self.xia.name, mca_number) in xia_rois:
                            aux = '{}_mca{}_roi'.format(self.xia.name, mca_number)  # \d{1}.*'
                            regex = re.compile(aux + '\d{1}.*')
                            matches = [string for string in xia_rois if re.match(regex, string)]
                            rois_array = []
                            roi_numbers = [roi_number for roi_number in
                                           [roi.split('mca{}_roi'.format(mca_number))[1].split('_high')[0] for roi in
                                            xia_rois if len(roi.split('mca{}_roi'.format(mca_number))) > 1] if
                                           len(roi_number) <= 3]
                            for roi_number in roi_numbers:
                                rois_array.append(
                                    [xia_rois['{}_mca{}_roi{}_high'.format(self.xia.name, mca_number, roi_number)],
                                     xia_rois['{}_mca{}_roi{}_low'.format(self.xia.name, mca_number, roi_number)]])

                            mcas.append(xia_parser.parse_roi(range(0, length), mca_number, rois_array, xia_max_energy))
                        else:
                            mcas.append(xia_parser.parse_roi(range(0, length), mca_number, [
                                [xia_rois['xia1_mca1_roi0_low'], xia_rois['xia1_mca1_roi0_high']]], xia_max_energy))

                else:
                    for mca_number in range(1, xia_parser.channelsCount() + 1):
                        mcas.append(xia_parser.parse_roi(range(0, length), mca_number, [[6.7, 6.9]]))

                for index_roi, roi in enumerate([[i for i in zip(*mcas)][ind] for ind, k in enumerate(roi_numbers)]):
                    xia_sum = [sum(i) for i in zip(*roi)]
                    if len(self.parent_gui.widget_processing.gen_parser.interp_arrays['energy']) > length:
                        xia_sum.extend([xia_sum[-1]] * (len(self.parent_gui.widget_processing.gen_parser.interp_arrays['energy']) - length))

                    roi_label = getattr(self, 'edit_roi_name_{}'.format(roi_numbers[index_roi])).text()
                    if not len(roi_label):
                        roi_label = 'XIA_ROI{}'.format(roi_numbers[index_roi])

                    self.parent_gui.widget_processing.gen_parser.interp_arrays[roi_label] = np.array(
                        [self.parent_gui.widget_processing.gen_parser.interp_arrays['energy'][:, 0], xia_sum]).transpose()
                    self.figure.ax.plot(self.parent_gui.widget_processing.gen_parser.interp_arrays['energy'][:, 1], -(
                        self.parent_gui.widget_processing.gen_parser.interp_arrays[roi_label][:, 1] / self.parent_gui.widget_processing.gen_parser.interp_arrays['i0'][:, 1]))

                self.figure.ax.set_xlabel('Energy (eV)')
                self.figure.ax.set_ylabel('XIA ROIs')

            self.parent_gui.widget_processing.gen_parser.export_trace(self.current_filepath[:-4], '')

        except Exception as exc:
            print('Could not finish parsing this scan:\n{}'.format(exc))

    def create_log_scan(self, uid, figure):
        self.canvas.draw_idle()
        if self.html_log_func is not None:
            self.html_log_func(uid, figure)

    def populateParams(self, index):
        for i in range(len(self.params1)):
            self.gridLayout_13.removeWidget(self.params1[i])
            self.gridLayout_13.removeWidget(self.params2[i])
            self.gridLayout_13.removeWidget(self.params3[i])
            self.params1[i].deleteLater()
            self.params2[i].deleteLater()
            self.params3[i].deleteLater()
        self.params1 = []
        self.params2 = []
        self.params3 = []
        self.param_types = []
        plan_func = self.plan_funcs[index]
        signature = inspect.signature(plan_func)
        for i in range(0, len(signature.parameters)):
            default = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))
            if default == str(signature.parameters[list(signature.parameters)[i]]):
                default = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))
            self.addParamControl(list(signature.parameters)[i], default,
                                 signature.parameters[list(signature.parameters)[i]].annotation,
                                 grid=self.gridLayout_13, params=[self.params1, self.params2, self.params3])
            self.param_types.append(signature.parameters[list(signature.parameters)[i]].annotation)

    def addParamControl(self, name, default, annotation, grid, params):
        rows = int((grid.count()) / 3)
        param1 = QtWidgets.QLabel(str(rows + 1))

        param2 = None
        def_val = ''
        if default.find('=') != -1:
            def_val = re.sub(r'.*=', '', default)
        if annotation == int:
            param2 = QtWidgets.QSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = int(def_val)
            param2.setValue(def_val)
        elif annotation == float:
            param2 = QtWidgets.QDoubleSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = float(def_val)
            param2.setValue(def_val)
        elif annotation == bool:
            param2 = QtWidgets.QCheckBox()
            if def_val == 'True':
                def_val = True
            else:
                def_val = False
            param2.setCheckState(def_val)
            param2.setTristate(False)
        elif annotation == str:
            param2 = QtWidgets.QLineEdit()
            def_val = str(def_val)
            param2.setText(def_val)

        if param2 is not None:
            param3 = QtWidgets.QLabel(default)
            grid.addWidget(param1, rows, 0, QtCore.Qt.AlignTop)
            grid.addWidget(param2, rows, 1, QtCore.Qt.AlignTop)
            grid.addWidget(param3, rows, 2, QtCore.Qt.AlignTop)
            params[0].append(param1)
            params[1].append(param2)
            params[2].append(param3)

    def questionMessage(self, title, question):
        reply = QtWidgets.QMessageBox.question(self, title,
                                               question,
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            return True
        elif reply == QtWidgets.QMessageBox.No:
            return False
        else:
            return False

    def setAnalogSampTime(self, text):
        self.analog_samp_time = text

    def setEncSampTime(self, text):
        self.enc_samp_time = text

    def setXiaSampTime(self, text):
        self.xia_samp_time = text