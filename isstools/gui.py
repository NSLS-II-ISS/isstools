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
                              widget_run, widget_beamline_setup, widget_sdd_manager, widget_beamline_status)

ui_path = pkg_resources.resource_filename('isstools', 'ui/XLive.ui')

def auto_redraw_factory(fnc):
    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback


class ScanGui(*uic.loadUiType(ui_path)):
    progress_sig = QtCore.pyqtSignal()

    def __init__(self, plan_funcs = [],
                 prep_traj_plan=None,
                 RE=None,
                 db=None,
                 accelerator=None,
                 hhm=None,
                 shutters_dict={},
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

        self.shutters_dict = shutters_dict

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
            self.layout_sdd_manager.addWidget(
                widget_sdd_manager.UISDDManager(self.xia_list))
        else:
            self.tabWidget.removeTab([self.tabWidget.tabText(index) for index in
                                      range(self.tabWidget.count())].index('Silicon Drift Detector setup'))
            self.xia = None

        self.widget_general_info = widget_general_info.UIGeneralInfo(accelerator, RE, db)
        self.layout_general_info.addWidget(self.widget_general_info)
        self.widget_trajectory_manager = widget_trajectory_manager.UITrajectoryManager(hhm)
        self.layout_trajectory_manager.addWidget(self.widget_trajectory_manager)
        self.widget_processing = widget_processing.UIProcessing(hhm, db, det_dict)
        self.layout_processing.addWidget(self.widget_processing)
        if self.RE is not None:
            self.widget_run = widget_run.UIRun(self.plan_funcs, db, shutters_dict, self.adc_list, self.enc_list,
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
                                                                           self.auto_tune_dict, shutters_dict, self)
        self.layout_beamline_setup.addWidget(self.widget_beamline_setup)
        self.layout_beamline_status.addWidget(widget_beamline_status.UIBeamlineStatus(self.shutters_dict))

        self.prep_traj_plan = prep_traj_plan
        if self.prep_traj_plan is None:
            self.push_prepare_trajectory.setEnabled(False)
        self.filepaths = []

        self.push_re_abort.clicked.connect(self.re_abort)

        # Redirect terminal output to GUI
        sys.stdout = EmittingStream()
        sys.stderr = EmittingStream()
        sys.stdout.textWritten.connect(self.normalOutputWritten)
        sys.stderr.textWritten.connect(self.normalOutputWritten)

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