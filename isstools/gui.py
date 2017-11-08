import math
import re
import sys
import time as ttime


import numpy as np
import pkg_resources

# import PyQt5
from PyQt5 import uic, QtGui, QtCore, QtWidgets
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor

from isstools.xiaparser import xiaparser

from isstools.widgets import (widget_general_info, widget_trajectory_manager, widget_processing, widget_batch_mode,
                              widget_run, widget_beamline_setup)
ui_path = pkg_resources.resource_filename('isstools', 'ui/XLive.ui')

def auto_redraw_factory(fnc):
    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback


class ScanGui(*uic.loadUiType(ui_path)):
    shutters_sig = QtCore.pyqtSignal()
    progress_sig = QtCore.pyqtSignal()

    def __init__(self, plan_funcs = [],
                 prep_traj_plan=None,
                 RE=None,
                 db=None,
                 accelerator=None,
                 hhm=None,
                 shutters={},
                 det_dict={},
                 motors_dict={},
                 general_scan_func = None, parent=None, *args, **kwargs):

        if 'write_html_log' in kwargs:
            self.html_log_func = kwargs['write_html_log']
            del kwargs['write_html_log']
        else:
            self.html_log_func = None

        if 'ic_amplifiers' in kwargs:
            self.ic_amplifiers = kwargs['ic_amplifiers']
            del kwargs['ic_amplifiers']
        else:
            self.ic_amplifiers = None

        if 'auto_tune_elements' in kwargs:
            self.auto_tune_dict = kwargs['auto_tune_elements']
            del kwargs['auto_tune_elements']
        else:
            self.auto_tune_dict = None

        if 'prepare_bl' in kwargs:
            self.prepare_bl_list = kwargs['prepare_bl']
            self.prepare_bl_plan = kwargs['prepare_bl'][0]
            del kwargs['prepare_bl']
        else:
            self.prepare_bl_list = []
            self.prepare_bl_plan = None

        if 'set_gains_offsets' in kwargs:
            self.set_gains_offsets_scan = kwargs['set_gains_offsets']
            del kwargs['set_gains_offsets']
        else:
            self.set_gains_offsets_scan = None

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.det_dict = det_dict
        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]



        self.motors_dict = motors_dict
        self.mot_list = self.motors_dict.keys()
        self.mot_sorted_list = list(self.mot_list)
        self.mot_sorted_list.sort()

        # Looking for analog pizzaboxes:
        regex = re.compile('pba\d{1}.*')
        matches = [string for string in [det.name for det in self.det_dict] if re.match(regex, string)]
        self.adc_list = [x for x in self.det_dict if x.name in matches]

        # Looking for encoder pizzaboxes:
        regex = re.compile('pb\d{1}_enc.*')
        matches = [string for string in [det.name for det in self.det_dict] if re.match(regex, string)]
        self.enc_list = [x for x in self.det_dict if x.name in matches]

        # Looking for xias:
        regex = re.compile('xia\d{1}')
        matches = [string for string in [det.name for det in self.det_dict] if re.match(regex, string)]
        self.xia_list = [x for x in self.det_dict if x.name in matches]
        if len(self.xia_list):
            self.xia = self.xia_list[0]
        else:
            self.xia = None

        self.addCanvas()
        self.RE = RE

        if self.RE is not None:
            self.RE.is_aborted = False
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update_re_state)
            self.timer.start(1000)
        else:
            self.tabWidget.removeTab(
                [self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index(
                    'Run'))
            self.tabWidget.removeTab(
                [self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index(
                    'Run Batch'))
            self.push_re_abort.setEnabled(False)
            self.run_check_gains.setEnabled(False)

        self.hhm = hhm
        if self.hhm is None:
            self.tabWidget.removeTab([self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Trajectories setup'))
            self.tabWidget.removeTab([self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Run'))
            self.tabWidget.removeTab([self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Run Batch'))
        else:
            self.hhm.trajectory_progress.subscribe(self.update_progress)
            self.progress_sig.connect(self.update_progressbar)
            self.progressBar.setValue(0)


        self.widget_general_info = widget_general_info.UIGeneralInfo(accelerator, RE, db)
        self.layout_general_info.addWidget(self.widget_general_info)
        self.widget_trajectory_manager = widget_trajectory_manager.UITrajectoryManager(hhm)
        self.layout_trajectroy_manager.addWidget(self.widget_trajectory_manager)
        self.widget_processing = widget_processing.UIProcessing(hhm, db, det_dict)
        self.layout_processing.addWidget(self.widget_processing)
        if self.RE is not None:
            self.widget_run = widget_run.UIRun(self.plan_funcs, db, shutters, self.adc_list, self.enc_list,
                                               self.xia, self.html_log_func, self)
            self.layout_run.addWidget(self.widget_run)
            self.widget_batch_mode = widget_batch_mode.UIBatchMode(self.plan_funcs, self.motors_dict, hhm,
                                                                   RE, db, self.widget_processing.gen_parser,
                                                                   self.adc_list, self.enc_list, self.xia,
                                                                   self.run_prep_traj, self.widget_run.parse_scans,
                                                                   self.widget_run.figure,
                                                                   self.widget_run.create_log_scan)
            self.layout_batch.addWidget(self.widget_batch_mode)
        self.widget_beamline_setup = widget_beamline_setup.UIBeamlineSetup(RE, self.hhm, db, self.adc_list,
                                                                           self.enc_list, self.det_dict, self.xia,
                                                                           self.ic_amplifiers,
                                                                           self.prepare_bl_plan, self.plan_funcs,
                                                                           self.prepare_bl_list,
                                                                           self.set_gains_offsets_scan,
                                                                           self.motors_dict, general_scan_func,
                                                                           self.widget_run.create_log_scan,
                                                                           self.auto_tune_dict, shutters, self)
        self.layout_beamline_setup.addWidget(self.widget_beamline_setup)

        self.prep_traj_plan = prep_traj_plan
        if self.prep_traj_plan is None:
            self.push_prepare_trajectory.setEnabled(False)
        self.filepaths = []


        # Initialize XIA tab
        self.xia_parser = xiaparser.xiaparser()
        self.push_gain_matching.clicked.connect(self.run_gain_matching)
        self.xia_graphs_names = []
        self.xia_graphs_labels = []
        self.xia_handles = []

        if self.xia is None:
            self.tabWidget.removeTab(
                [self.tabWidget.tabText(index) for index in
                 range(self.tabWidget.count())].index('Silicon Drift Detector setup'))
        else:
            self.xia_channels = [int(mca.split('mca')[1]) for mca in self.xia.read_attrs]
            self.xia_tog_channels = []
            if len(self.xia_channels):
                self.push_gain_matching.setEnabled(True)
                self.push_run_xia_measurement.setEnabled(True)
                self.xia.mca_max_energy.subscribe(self.update_xia_params)
                self.xia.real_time.subscribe(self.update_xia_params)
                self.xia.real_time_rb.subscribe(self.update_xia_params)
                self.edit_xia_acq_time.returnPressed.connect(self.update_xia_acqtime_pv)
                self.edit_xia_energy_range.returnPressed.connect(self.update_xia_energyrange_pv)

                max_en = self.xia.mca_max_energy.value
                energies = np.linspace(0, max_en, 2048)
                # np.floor(energies[getattr(self.xia, "mca{}".format(1)).roi1.low.value] * 1000)/1000

                self.roi_colors = []
                for mult in range(4):
                    self.roi_colors.append((.4 + (.2 * mult), 0, 0))
                    self.roi_colors.append((0, .4 + (.2 * mult), 0))
                    self.roi_colors.append((0, 0, .4 + (.2 * mult)))

                for roi in range(12):
                    low = getattr(self.xia, "mca1.roi{}".format(roi)).low.value
                    high = getattr(self.xia, "mca1.roi{}".format(roi)).high.value
                    if low > 0:
                        getattr(self, 'edit_roi_from_{}'.format(roi)).setText('{:.0f}'.format(
                            np.floor(energies[getattr(self.xia, "mca1.roi{}".format(roi)).low.value] * 1000)))
                    else:
                        getattr(self, 'edit_roi_from_{}'.format(roi)).setText('{:.0f}'.format(low))
                    if high > 0:
                        getattr(self, 'edit_roi_to_{}'.format(roi)).setText('{:.0f}'.format(
                            np.floor(energies[getattr(self.xia, "mca1.roi{}".format(roi)).high.value] * 1000)))
                    else:
                        getattr(self, 'edit_roi_to_{}'.format(roi)).setText('{:.0f}'.format(high))

                    label = getattr(self.xia, "mca1.roi{}".format(roi)).label.value
                    getattr(self, 'edit_roi_name_{}'.format(roi)).setText(label)

                    getattr(self, 'edit_roi_from_{}'.format(roi)).returnPressed.connect(self.update_xia_rois)
                    getattr(self, 'edit_roi_to_{}'.format(roi)).returnPressed.connect(self.update_xia_rois)
                    getattr(self, 'edit_roi_name_{}'.format(roi)).returnPressed.connect(self.update_xia_rois)

                self.push_run_xia_measurement.clicked.connect(self.start_xia_spectra)
                self.push_run_xia_measurement.clicked.connect(self.update_xia_rois)
                for channel in self.xia_channels:
                    getattr(self, "checkBox_gm_ch{}".format(channel)).setEnabled(True)
                    getattr(self.xia, "mca{}".format(channel)).array.subscribe(self.update_xia_graph)
                    getattr(self, "checkBox_gm_ch{}".format(channel)).toggled.connect(self.toggle_xia_checkbox)
                self.push_chackall_xia.clicked.connect(self.toggle_xia_all)

        self.push_re_abort.clicked.connect(self.re_abort)
        
        # Initialize Ophyd elements
        self.shutters_sig.connect(self.change_shutter_color)
        self.shutters = shutters

        self.fe_shutters = [self.shutters[shutter] for shutter in self.shutters if
                            self.shutters[shutter].shutter_type == 'FE']
        for shutter in [self.shutters[shutter] for shutter in self.shutters if
                        self.shutters[shutter].shutter_type == 'FE']:
            del self.shutters[shutter.name]

        self.shutters_buttons = []
        for key, item in zip(self.shutters.keys(), self.shutters.items()):
            self.shutter_layout = QtWidgets.QVBoxLayout()

            label = QtWidgets.QLabel(key)
            label.setAlignment(QtCore.Qt.AlignCenter)
            self.shutter_layout.addWidget(label)
            label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)

            button = QtWidgets.QPushButton('')
            button.setFixedSize(self.height() * 0.06, self.height() * 0.06)
            self.shutter_layout.addWidget(button)
            # button.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

            self.horizontalLayout_shutters.addLayout(self.shutter_layout)

            self.shutters_buttons.append(button)
            button.setFixedWidth(button.height() * 1.2)
            QtCore.QCoreApplication.processEvents()

            if hasattr(item[1].state, 'subscribe'):
                item[1].button = button
                item[1].state.subscribe(self.update_shutter)

                def toggle_shutter_call(shutter):
                    def toggle_shutter():
                        if int(shutter.state.value):
                            shutter.open()
                        else:
                            shutter.close()

                    return toggle_shutter

                button.clicked.connect(toggle_shutter_call(item[1]))

                if item[1].state.value == 0:
                    button.setStyleSheet("background-color: lime")
                else:
                    button.setStyleSheet("background-color: red")

            elif hasattr(item[1], 'subscribe'):
                item[1].output.parent.button = button
                item[1].subscribe(self.update_shutter)

                def toggle_shutter_call(shutter):
                    def toggle_shutter():
                        if shutter.state == 'closed':
                            shutter.open()
                        else:
                            shutter.close()

                    return toggle_shutter

                if item[1].state == 'closed':
                    button.setStyleSheet("background-color: red")
                elif item[1].state == 'open':
                    button.setStyleSheet("background-color: lime")

                button.clicked.connect(toggle_shutter_call(item[1]))

        if self.horizontalLayout_shutters.count() <= 1:
            self.groupBox_shutters.setVisible(False)

        # Initialize 'Batch Mode' tab




        # Redirect terminal output to GUI
        sys.stdout = EmittingStream()
        sys.stderr = EmittingStream()
        sys.stdout.textWritten.connect(self.normalOutputWritten)
        sys.stderr.textWritten.connect(self.normalOutputWritten)

    def update_shutter(self, pvname=None, value=None, char_value=None, **kwargs):
        if 'obj' in kwargs.keys():
            if hasattr(kwargs['obj'].parent, 'button'):
                self.current_button = kwargs['obj'].parent.button

                if int(value) == 0:
                    self.current_button_color = 'lime'
                elif int(value) == 1:
                    self.current_button_color = 'red'

                self.shutters_sig.emit()

    def change_shutter_color(self):
        self.current_button.setStyleSheet("background-color: " + self.current_button_color)


    def update_progress(self, pvname=None, value=None, char_value=None, **kwargs):
        self.progress_sig.emit()
        self.progressValue = value

    def update_progressbar(self):
        self.progressBar.setValue(int(np.round(self.progressValue)))

    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def normalOutputWritten(self, text):
        """Append text to the QtextEdit_terminal."""
        cursor = self.textEdit_terminal.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)

        if text.find('0;3') >= 0:
            text = text.replace('<', '(')
            text = text.replace('>', ')')
            text = text.replace('[0m', '</font>')
            text = text.replace('[0;31m', '<font color=\"Red\">')
            text = text.replace('[0;32m', '<font color=\"Green\">')
            text = text.replace('[0;33m', '<font color=\"Yellow\">')
            text = text.replace('[0;34m', '<font color=\"Blue\">')
            text = text.replace('[0;36m', '<font color=\"Purple\">')
            text = text.replace('\n', '<br />')
            text += '<br />'
            cursor.insertHtml(text)
        elif text.lower().find('abort') >= 0 or text.lower().find('error') >= 0 or text.lower().find('invalid') >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.red)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        elif text.lower().find('starting') >= 0 or text.lower().find('launching') >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.blue)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        elif text.lower().find('complete') >= 0 or text.lower().find('done') >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.darkGreen)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        else:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.black)
            fmt.setFontWeight(QtGui.QFont.Normal)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        self.textEdit_terminal.setTextCursor(cursor)
        self.textEdit_terminal.ensureCursorVisible()

    def addCanvas(self):
        self.figure_gain_matching = Figure()
        self.figure_gain_matching.set_facecolor(color='#FcF9F6')
        self.canvas_gain_matching = FigureCanvas(self.figure_gain_matching)
        self.figure_gain_matching.add_subplot(111)
        self.toolbar_gain_matching = NavigationToolbar(self.canvas_gain_matching, self.tab_2, coordinates=True)
        self.plot_gain_matching.addWidget(self.toolbar_gain_matching)
        self.plot_gain_matching.addWidget(self.canvas_gain_matching)
        self.canvas_gain_matching.draw_idle()

        self.figure_xia_all_graphs = Figure()
        self.figure_xia_all_graphs.set_facecolor(color='#FcF9F6')
        self.canvas_xia_all_graphs = FigureCanvas(self.figure_xia_all_graphs)
        self.figure_xia_all_graphs.ax = self.figure_xia_all_graphs.add_subplot(111)
        self.toolbar_xia_all_graphs = NavigationToolbar(self.canvas_xia_all_graphs, self.tab_2, coordinates=True)
        self.plot_xia_all_graphs.addWidget(self.toolbar_xia_all_graphs)
        self.plot_xia_all_graphs.addWidget(self.canvas_xia_all_graphs)
        self.canvas_xia_all_graphs.draw_idle()
        self.cursor_xia_all_graphs = Cursor(self.figure_xia_all_graphs.ax, useblit=True, color='green', linewidth=0.75)
        self.figure_xia_all_graphs.ax.clear()

    @property
    def plot_x(self):
        return self.plot_selection_dropdown.value()

    def figure_content(self):
        fig1 = Figure()
        fig1.set_facecolor(color='0.89')
        fig1.stale_callback = auto_redraw_factory(fig1.stale_callback)
        ax1f1 = fig1.add_subplot(111)
        ax1f1.plot(np.random.rand(5))
        self.ax = ax1f1
        return fig1

    def run_tune(self):
        for shutter in [self.shutters[shutter] for shutter in self.shutters if
                        self.shutters[shutter].shutter_type != 'SP']:
            if shutter.state.value:
                ret = self.questionMessage('Shutter closed', 'Would you like to run the scan with the shutter closed?')
                if not ret:
                    print('Aborted!')
                    return False
                break

        self.figure_tune.ax.clear()
        self.toolbar_tune._views.clear()
        self.toolbar_tune._positions.clear()
        self.toolbar_tune._update_view()
        self.canvas_tune.draw_idle()

    def run_prep_traj(self):
        self.RE(self.prep_traj_plan())

    def update_repetitions_spinbox(self):
        if self.checkBox_traj_single_dir.isChecked():
            self.spinBox_tiling_repetitions.setValue(1)
            self.spinBox_tiling_repetitions.setEnabled(0)
        else:
            self.spinBox_tiling_repetitions.setEnabled(1)

    def re_abort(self):
        if self.RE.state != 'idle':
            self.RE.abort()
            self.RE.is_aborted = True

    def update_re_state(self):
        palette = self.label_11.palette()
        if (self.RE.state == 'idle'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(193, 140, 15))
        elif (self.RE.state == 'running'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(0, 165, 0))
        elif (self.RE.state == 'paused'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(255, 0, 0))
        elif (self.RE.state == 'abort'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(255, 0, 0))
        self.label_11.setPalette(palette)
        self.label_11.setText(self.RE.state)
        # if self.RE.state != self.RE.last_state:
        #    self.RE.last_state = self.RE.state

    def update_hhm_params(self, value, **kwargs):
        if kwargs['obj'].name == 'hhm_energy':
            text = '{:.2f}'.format(round(value, 2))
            if text != self.last_text:
                self.edit_pb_energy.setText('{:.2f}'.format(round(value, 2)))
                self.last_text = text

    def run_get_offsets(self):
        for shutter in [self.shutters[shutter] for shutter in self.shutters
                        if self.shutters[shutter].shutter_type == 'PH' and
                        self.shutters[shutter].state.read()['{}_state'.format(shutter)]['value'] != 1]:
            shutter.close()
            while shutter.state.read()['{}_state'.format(shutter.name)]['value'] != 1:
                QtWidgets.QApplication.processEvents()
                ttime.sleep(0.1)
        get_offsets = [func for func in self.plan_funcs if func.__name__ == 'get_offsets'][0]

        adc_names = [box.text() for box in self.adc_checkboxes if box.isChecked()]
        adcs = [adc for adc in self.adc_list if adc.dev_name.value in adc_names]

        list(get_offsets(20, *adcs))
        #list(get_offsets())

    def toggle_xia_checkbox(self, value):
        if value:
            self.xia_tog_channels.append(self.sender().text())
        elif self.sender().text() in self.xia_tog_channels:
            self.xia_tog_channels.remove(self.sender().text())
        self.erase_xia_graph()
        for chan in self.xia_tog_channels:
            self.update_xia_graph(getattr(self.xia, 'mca{}.array.value'.format(chan)),
                                  obj=getattr(self.xia, 'mca{}.array'.format(chan)))

    def toggle_xia_all(self):
        if len(self.xia_tog_channels) != len(self.xia.read_attrs):
            for index, mca in enumerate(self.xia.read_attrs):
                if getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).isEnabled():
                    getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).setChecked(True)
        else:
            for index, mca in enumerate(self.xia.read_attrs):
                if getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).isEnabled():
                    getattr(self, 'checkBox_gm_ch{}'.format(index + 1)).setChecked(False)

    def update_xia_params(self, value, **kwargs):
        if kwargs['obj'].name == 'xia1_real_time':
            self.edit_xia_acq_time.setText('{:.2f}'.format(round(value, 2)))
        elif kwargs['obj'].name == 'xia1_real_time_rb':
            self.label_acq_time_rbv.setText('{:.2f}'.format(round(value, 2)))
        elif kwargs['obj'].name == 'xia1_mca_max_energy':
            self.edit_xia_energy_range.setText('{:.0f}'.format(value * 1000))

    def erase_xia_graph(self):
        self.figure_xia_all_graphs.ax.clear()

        for roi in range(12):
            if hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                exec('del self.figure_xia_all_graphs.ax.roi{}l,\
                    self.figure_xia_all_graphs.ax.roi{}h'.format(roi, roi))

        self.toolbar_xia_all_graphs._views.clear()
        self.toolbar_xia_all_graphs._positions.clear()
        self.toolbar_xia_all_graphs._update_view()
        self.xia_graphs_names.clear()
        self.xia_graphs_labels.clear()
        self.xia_handles.clear()
        self.canvas_xia_all_graphs.draw_idle()

    def start_xia_spectra(self):
        if self.xia.collect_mode.value != 0:
            self.xia.collect_mode.put(0)
            ttime.sleep(2)
        self.xia.erase_start.put(1)

    def update_xia_rois(self):
        energies = np.linspace(0, float(self.edit_xia_energy_range.text()) / 1000, 2048)

        for roi in range(12):
            if float(getattr(self, 'edit_roi_from_{}'.format(roi)).text()) < 0 or float(
                    getattr(self, 'edit_roi_to_{}'.format(roi)).text()) < 0:
                exec('start{} = -1'.format(roi))
                exec('end{} = -1'.format(roi))
            else:
                indexes_array = np.where(
                    (energies >= float(getattr(self, 'edit_roi_from_{}'.format(roi)).text()) / 1000) & (
                    energies <= float(getattr(self, 'edit_roi_to_{}'.format(roi)).text()) / 1000) == True)[0]
                if len(indexes_array):
                    exec('start{} = indexes_array.min()'.format(roi))
                    exec('end{} = indexes_array.max()'.format(roi))
                else:
                    exec('start{} = -1'.format(roi))
                    exec('end{} = -1'.format(roi))
            exec('roi{}x = [float(self.edit_roi_from_{}.text()), float(self.edit_roi_to_{}.text())]'.format(roi, roi,
                                                                                                            roi))
            exec('label{} = self.edit_roi_name_{}.text()'.format(roi, roi))

        for channel in self.xia_channels:
            for roi in range(12):
                getattr(self.xia, "mca{}.roi{}".format(channel, roi)).low.put(eval('start{}'.format(roi)))
                getattr(self.xia, "mca{}.roi{}".format(channel, roi)).high.put(eval('end{}'.format(roi)))
                getattr(self.xia, "mca{}.roi{}".format(channel, roi)).label.put(eval('label{}'.format(roi)))

        for roi in range(12):
            if not hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                exec(
                    'self.figure_xia_all_graphs.ax.roi{}l = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[0], color=self.roi_colors[roi])'.format(
                        roi, roi))
                exec(
                    'self.figure_xia_all_graphs.ax.roi{}h = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[1], color=self.roi_colors[roi])'.format(
                        roi, roi))

            else:
                exec('self.figure_xia_all_graphs.ax.roi{}l.set_xdata([roi{}x[0], roi{}x[0]])'.format(roi, roi, roi))
                exec('self.figure_xia_all_graphs.ax.roi{}h.set_xdata([roi{}x[1], roi{}x[1]])'.format(roi, roi, roi))

        self.figure_xia_all_graphs.ax.grid(True)
        self.canvas_xia_all_graphs.draw_idle()

    def update_xia_acqtime_pv(self):
        self.xia.real_time.put(float(self.edit_xia_acq_time.text()))

    def update_xia_energyrange_pv(self):
        self.xia.mca_max_energy.put(float(self.edit_xia_energy_range.text()) / 1000)

    def update_xia_graph(self, value, **kwargs):
        curr_name = kwargs['obj'].name
        curr_index = -1
        if len(self.figure_xia_all_graphs.ax.lines):
            if float(self.edit_xia_energy_range.text()) != self.figure_xia_all_graphs.ax.lines[0].get_xdata()[-1]:
                self.figure_xia_all_graphs.ax.clear()
                for roi in range(12):
                    if hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                        exec('del self.figure_xia_all_graphs.ax.roi{}l,\
                            self.figure_xia_all_graphs.ax.roi{}h'.format(roi, roi))

                self.toolbar_xia_all_graphs._views.clear()
                self.toolbar_xia_all_graphs._positions.clear()
                self.toolbar_xia_all_graphs._update_view()
                self.xia_graphs_names.clear()
                self.xia_graphs_labels.clear()
                self.canvas_xia_all_graphs.draw_idle()

        if curr_name in self.xia_graphs_names:
            for index, name in enumerate(self.xia_graphs_names):
                if curr_name == name:
                    curr_index = index
                    line = self.figure_xia_all_graphs.ax.lines[curr_index]
                    line.set_ydata(value)
                    break

        else:
            ch_number = curr_name.split('_')[1].split('mca')[1]
            if ch_number in self.xia_tog_channels:
                self.xia_graphs_names.append(curr_name)
                label = 'Chan {}'.format(ch_number)
                self.xia_graphs_labels.append(label)
                handles, = self.figure_xia_all_graphs.ax.plot(
                    np.linspace(0, float(self.edit_xia_energy_range.text()), 2048), value, label=label)
                self.xia_handles.append(handles)
                self.figure_xia_all_graphs.ax.legend(self.xia_handles, self.xia_graphs_labels)

            if len(self.figure_xia_all_graphs.ax.lines) == len(self.xia_tog_channels) != 0:
                for roi in range(12):
                    exec('roi{}x = [float(self.edit_roi_from_{}.text()), float(self.edit_roi_to_{}.text())]'.format(roi,
                                                                                                                    roi,
                                                                                                                    roi))

                for roi in range(12):
                    if not hasattr(self.figure_xia_all_graphs.ax, 'roi{}l'.format(roi)):
                        exec(
                            'self.figure_xia_all_graphs.ax.roi{}l = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[0], color=self.roi_colors[roi])'.format(
                                roi, roi))
                        exec(
                            'self.figure_xia_all_graphs.ax.roi{}h = self.figure_xia_all_graphs.ax.axvline(x=roi{}x[1], color=self.roi_colors[roi])'.format(
                                roi, roi))

                self.figure_xia_all_graphs.ax.grid(True)

        self.figure_xia_all_graphs.ax.relim()
        self.figure_xia_all_graphs.ax.autoscale(True, True, True)
        y_interval = self.figure_xia_all_graphs.ax.get_yaxis().get_data_interval()
        if len(y_interval):
            if y_interval[0] != 0 or y_interval[1] != 0:
                self.figure_xia_all_graphs.ax.set_ylim([y_interval[0] - (y_interval[1] - y_interval[0]) * 0.05,
                                                        y_interval[1] + (y_interval[1] - y_interval[0]) * 0.05])
        self.canvas_xia_all_graphs.draw_idle()

    def run_gain_matching(self):
        ax = self.figure_gain_matching.add_subplot(111)
        gain_adjust = [0.001] * len(self.xia_channels)  # , 0.001, 0.001, 0.001]
        diff = [0] * len(self.xia_channels)  # , 0, 0, 0]
        diff_old = [0] * len(self.xia_channels)  # , 0, 0, 0]

        # Run number of iterations defined in the text edit edit_gain_matching_iterations:
        for i in range(int(self.edit_gain_matching_iterations.text())):
            self.xia.collect_mode.put('MCA spectra')
            ttime.sleep(0.25)
            self.xia.mode.put('Real time')
            ttime.sleep(0.25)
            self.xia.real_time.put('1')
            self.xia.capt_start_stop.put(1)
            ttime.sleep(0.05)
            self.xia.erase_start.put(1)
            ttime.sleep(2)
            ax.clear()
            self.toolbar_gain_matching._views.clear()
            self.toolbar_gain_matching._positions.clear()
            self.toolbar_gain_matching._update_view()

            # For each channel:
            for chann in self.xia_channels:
                # If checkbox of current channel is checked:
                if getattr(self, "checkBox_gm_ch{}".format(chann)).checkState() > 0:

                    # Get current channel pre-amp gain:
                    curr_ch_gain = getattr(self.xia, "pre_amp_gain{}".format(chann))

                    coeff = self.xia_parser.gain_matching(self.xia, self.edit_center_gain_matching.text(),
                                                          self.edit_range_gain_matching.text(), chann, ax)
                    # coeff[0] = Intensity
                    # coeff[1] = Fitted mean
                    # coeff[2] = Sigma

                    diff[chann - 1] = float(self.edit_gain_matching_target.text()) - float(coeff[1] * 1000)

                    if i != 0:
                        sign = (diff[chann - 1] * diff_old[chann - 1]) / math.fabs(
                            diff[chann - 1] * diff_old[chann - 1])
                        if int(sign) == -1:
                            gain_adjust[chann - 1] /= 2
                    print('Chan ' + str(chann) + ': ' + str(diff[chann - 1]) + '\n')

                    # Update current channel pre-amp gain:
                    curr_ch_gain.put(curr_ch_gain.value - diff[chann - 1] * gain_adjust[chann - 1])
                    diff_old[chann - 1] = diff[chann - 1]

                    self.canvas_gain_matching.draw_idle()

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

# Class to write terminal output to screen
class EmittingStream(QtCore.QObject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer = sys.__stdout__.buffer
        self.close = sys.__stdout__.close
        self.closed = sys.__stdout__.closed
        self.detach = sys.__stdout__.detach
        self.encoding = sys.__stdout__.encoding
        self.errors = sys.__stdout__.errors
        self.fileno = sys.__stdout__.fileno
        self.flush = sys.__stdout__.flush
        self.isatty = sys.__stdout__.isatty
        self.line_buffering = sys.__stdout__.line_buffering
        self.mode = sys.__stdout__.mode
        self.name = sys.__stdout__.name
        self.newlines = sys.__stdout__.newlines
        self.read = sys.__stdout__.read
        self.readable = sys.__stdout__.readable
        self.readlines = sys.__stdout__.readlines
        self.seek = sys.__stdout__.seek
        self.seekable = sys.__stdout__.seekable
        # self.softspace = sys.__stdout__.softspace
        self.tell = sys.__stdout__.tell
        self.truncate = sys.__stdout__.truncate
        self.writable = sys.__stdout__.writable
        self.writelines = sys.__stdout__.writelines

    textWritten = QtCore.pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))
        # Comment next line if the output should be printed only in the GUI
        sys.__stdout__.write(text)