import re
import sys

import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore
from matplotlib.figure import Figure

from isstools.widgets import (widget_general_info, widget_trajectory_manager, widget_processing, widget_batch_mode,
                              widget_run, widget_beamline_setup, widget_sdd_manager, widget_beamline_status)

from isstools.elements import EmittingStream
#Libs for ZeroMQ communication
import socket
from PyQt5.QtCore import QThread
import zmq
import pickle
import pandas as pd

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

    def __init__(self, plan_funcs=[],
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

        if 'sample_stages' in kwargs:
            self.sample_stages = kwargs['sample_stages']
            del kwargs['sample_stages']
        else:
            self.sample_stages = []

        if 'processing_sender' in kwargs:
            self.sender = kwargs['processing_sender']
            del kwargs['processing_sender']
        else:
            self.sender = None

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.det_dict = det_dict
        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]

        self.prep_traj_plan = prep_traj_plan

        self.motors_dict = motors_dict

        self.shutters_dict = shutters_dict

        self.RE = RE

        if self.RE is not None:
            self.RE.is_aborted = False
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update_re_state)
            self.timer.start(1000)
        else:
            self.tabWidget.removeTab(
                [self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Run'))
            self.tabWidget.removeTab(
                [self.tabWidget.tabText(index) for index in range(self.tabWidget.count())].index('Run Batch'))
            self.push_re_abort.setEnabled(False)
            self.run_check_gains.setEnabled(False)

        self.hhm = hhm
        if self.hhm is None:
            self.tabWidget.removeTab([self.tabWidget.tabText(index)
                                      for index in range(self.tabWidget.count())].index('Trajectory setup'))
            self.tabWidget.removeTab([self.tabWidget.tabText(index)
                                      for index in range(self.tabWidget.count())].index('Run'))
            self.tabWidget.removeTab([self.tabWidget.tabText(index)
                                      for index in range(self.tabWidget.count())].index('Run Batch'))
        else:
            self.hhm.trajectory_progress.subscribe(self.update_progress)
            self.progress_sig.connect(self.update_progressbar)
            self.progressBar.setValue(0)

        # Activating ZeroMQ Receiving Socket
        self.context = zmq.Context()
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.connect("tcp://xf08id-srv2:5562")
        self.hostname_filter = socket.gethostname()
        self.subscriber.setsockopt_string(zmq.SUBSCRIBE, self.hostname_filter)
        self.receiving_thread = ReceivingThread(self)
        self.run_mode = 'run'

        # Looking for analog pizzaboxes:
        regex = re.compile('pba\d{1}.*')
        matches = [det for det in self.det_dict if re.match(regex, det)]
        self.adc_list = [self.det_dict[x]['obj'] for x in self.det_dict if x in matches]

        # Looking for encoder pizzaboxes:
        regex = re.compile('pb\d{1}_enc.*')
        matches = [det for det in self.det_dict if re.match(regex, det)]
        self.enc_list = [self.det_dict[x]['obj'] for x in self.det_dict if x in matches]

        # Looking for xias:
        regex = re.compile('xia\d{1}')
        matches = [det for det in self.det_dict if re.match(regex, det)]
        self.xia_list = [self.det_dict[x]['obj'] for x in self.det_dict if x in matches]
        if len(self.xia_list):
            self.xia = self.xia_list[0]
            self.widget_sdd_manager = widget_sdd_manager.UISDDManager(self.xia_list)
            self.layout_sdd_manager.addWidget(self.widget_sdd_manager)
        else:
            self.tabWidget.removeTab([self.tabWidget.tabText(index) for index in
                                      range(self.tabWidget.count())].index('Silicon Drift Detector setup'))
            self.xia = None

        self.widget_general_info = widget_general_info.UIGeneralInfo(accelerator, RE, db)
        self.layout_general_info.addWidget(self.widget_general_info)

        if self.hhm is not None:
            self.widget_trajectory_manager = widget_trajectory_manager.UITrajectoryManager(hhm, self.run_prep_traj)
            self.layout_trajectory_manager.addWidget(self.widget_trajectory_manager)

        self.widget_processing = widget_processing.UIProcessing(hhm, db, det_dict, self.sender)
        self.layout_processing.addWidget(self.widget_processing)
        self.receiving_thread.received_bin_data.connect(self.widget_processing.plot_data)
        self.receiving_thread.received_req_interp_data.connect(self.widget_processing.plot_interp_data)

        if self.RE is not None:
            self.widget_run = widget_run.UIRun(self.plan_funcs, db, shutters_dict, self.adc_list, self.enc_list,
                                               self.xia, self.html_log_func, self)
            self.layout_run.addWidget(self.widget_run)
            self.receiving_thread.received_interp_data.connect(self.widget_run.plot_scan)

            if self.hhm is not None:
                self.widget_batch_mode = widget_batch_mode.UIBatchMode(self.plan_funcs, self.motors_dict, hhm,
                                                                       RE, db, self.widget_processing.gen_parser,
                                                                       self.adc_list, self.enc_list, self.xia,
                                                                       self.run_prep_traj,
                                                                       self.widget_run.figure,
                                                                       self.widget_run.create_log_scan,
                                                                       sample_stages=self.sample_stages,
                                                                       parent_gui = self)
                self.layout_batch.addWidget(self.widget_batch_mode)
                self.receiving_thread.received_bin_data.connect(self.widget_batch_mode.plot_batches)

                self.widget_trajectory_manager.trajectoriesChanged.connect(self.widget_batch_mode.update_batch_traj)

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

        self.filepaths = []

        self.push_re_abort.clicked.connect(self.re_abort)

        # After connecting signals to slots, start receiving thread
        self.receiving_thread.start()

        # Redirect terminal output to GUI
        sys.stdout = EmittingStream.EmittingStream(self.textEdit_terminal)
        sys.stderr = EmittingStream.EmittingStream(self.textEdit_terminal)

    def update_progress(self, pvname=None, value=None, char_value=None, **kwargs):
        self.progress_sig.emit()
        self.progressValue = value

    def update_progressbar(self):
        value = np.round(self.progressValue)
        if not math.isnan(value):
            self.progressBar.setValue(int(value))

    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def run_prep_traj(self):
        self.RE(self.prep_traj_plan())

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


class ReceivingThread(QThread):
    received_interp_data = QtCore.pyqtSignal(object)
    received_bin_data = QtCore.pyqtSignal(object)
    received_req_interp_data = QtCore.pyqtSignal(object)
    def __init__(self, gui):
        QThread.__init__(self)
        self.setParent(gui)

    def run(self):
        while True:
            message = self.parent().subscriber.recv()
            message = message[len(self.parent().hostname_filter):]
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                data = pickle.loads(message)

            if 'data' in data['processing_ret']:
                data['processing_ret']['data'] = pd.read_msgpack(data['processing_ret']['data'])

            if data['type'] == 'spectroscopy':
                if data['processing_ret']['type'] == 'interpolate':
                    self.received_interp_data.emit(data)
                if data['processing_ret']['type'] == 'bin':
                    self.received_bin_data.emit(data)
                if data['processing_ret']['type'] == 'request_interpolated_data':
                    self.received_req_interp_data.emit(data)
