import re
import sys

import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore
from matplotlib.figure import Figure

from isstools.widgets import (widget_general_info, widget_trajectory_manager, widget_processing, widget_batch_mode,widget_batch_mode_new,
widget_run, widget_beamline_setup, widget_sdd_manager, widget_beamline_status)

from isstools.elements import EmittingStream
#Libs for ZeroMQ communication
import socket
from PyQt5.QtCore import QThread
import zmq
import pickle
import pandas as pd


import kafka

ui_path = pkg_resources.resource_filename('isstools', 'ui/XLive.ui')

def auto_redraw_factory(fnc):
    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback


class XliveGui(*uic.loadUiType(ui_path)):

    progress_sig = QtCore.pyqtSignal()

    def __init__(self,
                 plan_funcs={},
                 service_plan_funcs={},
                 aux_plan_funcs={},
                 RE=None,
                 db=None,
                 accelerator=None,
                 hhm=None,
                 shutters_dict={},
                 det_dict={},
                 motors_dict={},
                 sample_stage=None,
                 tune_elements=None,
                 ic_amplifiers={},
                 processing_sender=None,
                 bootstrap_servers=['cmb01:9092', 'cmb02:9092'],
                 kafka_topic="qas-analysis", 
                 window_title="XLive @QAS/11-ID NSLS-II",
                 job_submitter=None,
                 prepare_bl=None,
                 *args, **kwargs):
        '''

            Parameters
            ----------

            plan_funcs : list, optional
                functions that run plans (call RE(plan()) etc)
            prep_traj_plan : generator or None, optional
                a plan that prepares the trajectories
            RE : bluesky.RunEngine, optional
                a RunEngine instance
            db : databroker.Broker, optional
                the database to save acquired data to
            accelerator : 
            hhm : ophyd.Device, optional
                the monochromator. "hhm" stood for "high heatload monochromator" 
                and has been kept from the legacy ISS code
            shutters_dict : dict, optional
                dictionary of available shutters
            det_dict : dict, optional
                dictionary of detectors
            motors_dict : dict, optional
                dictionary of motors
            general_scan_func : generator or None, optional
            receiving address: string, optinal
                the address for where to subscribe the Kafka Consumer to
        '''
        self.window_title = window_title

        self.sender = processing_sender

        super().__init__(*args, **kwargs)
        self.setupUi(self)


        self.RE = RE


        if RE is not None:
            RE.is_aborted = False
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update_re_state)
            self.timer.start(1000)



        hhm.trajectory_progress.subscribe(self.update_progress)
        self.progress_sig.connect(self.update_progressbar)
        self.progressBar.setValue(0)

        # Activating ZeroMQ Receiving Socket
        self.context = zmq.Context()
        self.hostname_filter = socket.gethostname()
        # Now using Kafka
        self.consumer = kafka.KafkaConsumer(kafka_topic, bootstrap_servers=bootstrap_servers)
        self.receiving_thread = ReceivingThread(self)
        self.run_mode = 'run'

        # Looking for analog pizzaboxes:
        regex = re.compile('pba\d{1}.*')
        matches = [det for det in det_dict if re.match(regex, det)]
        adc_list = [det_dict[x]['obj'] for x in det_dict if x in matches]

        # Looking for encoder pizzaboxes:
        regex = re.compile('pb\d{1}_enc.*')
        matches = [det for det in det_dict if re.match(regex, det)]
        enc_list = [det_dict[x]['obj'] for x in det_dict if x in matches]

        # Looking for xias:
        regex = re.compile('xia\d{1}')
        matches = [det for det in det_dict if re.match(regex, det)]
        xia_list = [det_dict[x]['obj'] for x in det_dict if x in matches]
        if len(xia_list):
            xia = xia_list[0]
            self.widget_sdd_manager = widget_sdd_manager.UISDDManager(xia_list)
            self.layout_sdd_manager.addWidget(self.widget_sdd_manager)


        self.widget_general_info = widget_general_info.UIGeneralInfo(accelerator, RE, db)
        self.layout_general_info.addWidget(self.widget_general_info)


        self.widget_trajectory_manager = widget_trajectory_manager.UITrajectoryManager(hhm,
                                                                                       aux_plan_funcs= aux_plan_funcs
                                                                                       )
        self.layout_trajectory_manager.addWidget(self.widget_trajectory_manager)

        self.widget_processing = widget_processing.UIProcessing(hhm,
                                                                db,
                                                                det_dict,
                                                                parent_gui=self,
                                                                job_submitter=job_submitter
                                                                )
        self.layout_processing.addWidget(self.widget_processing)

        self.receiving_thread.received_bin_data.connect(self.widget_processing.plot_data)
        self.receiving_thread.received_req_interp_data.connect(self.widget_processing.plot_interp_data)

        self.widget_run = widget_run.UIRun(plan_funcs,
                                            aux_plan_funcs,
                                            RE,
                                            db,
                                            hhm,
                                            shutters_dict,
                                            adc_list,
                                            enc_list,
                                            xia,
                                            self)
        self.layout_run.addWidget(self.widget_run)
        #self.receiving_thread.received_interp_data.connect(self.widget_run.plot_scan)

        # if self.hhm is not None:
        #     self.widget_batch_mode = widget_batch_mode.UIBatchMode(self.plan_funcs, self.motors_dict, hhm,
        #                                                            self.RE, self.db, self.widget_processing.gen_parser,
        #                                                            self.adc_list, self.enc_list, self.xia,
        #                                                            self.run_prep_traj,
        #                                                            self.widget_run.figure,
        #                                                            self.widget_run.create_log_scan,
        #                                                            sample_stage=sample_stage,
        #                                                            parent_gui = self,
        #                                                            job_submitter=job_submitter)
        #     self.layout_batch.addWidget(self.widget_batch_mode)
        #
        #
        #     self.widget_batch_mode_new = widget_batch_mode_new.UIBatchModeNew(self.plan_funcs, self.service_plan_funcs,
        #                                                            self.motors_dict, hhm,
        #                                                            self.RE, self.db, self.widget_processing.gen_parser,
        #                                                            self.adc_list, self.enc_list, self.xia,
        #                                                            self.run_prep_traj,
        #                                                            self.widget_run.figure,
        #                                                            self.widget_run.create_log_scan,
        #
        #                                                            sample_stage=self.sample_stage,
        #                                                            parent_gui = self)
        #
        #     self.layout_batch_new.addWidget(self.widget_batch_mode_new)
        #
        #
        #
        #     self.widget_trajectory_manager.trajectoriesChanged.connect(self.widget_batch_mode.update_batch_traj)

        self.widget_beamline_setup = widget_beamline_setup.UIBeamlineSetup(RE,
                                                                           hhm,
                                                                           db,
                                                                           adc_list,
                                                                           enc_list,
                                                                           det_dict,
                                                                           xia,
                                                                           ic_amplifiers,
                                                                           plan_funcs,
                                                                           service_plan_funcs,
                                                                           aux_plan_funcs,
                                                                           motors_dict,
                                                                           self.widget_run.create_log_scan,
                                                                           tune_elements,
                                                                           shutters_dict,
                                                                           self)
        self.layout_beamline_setup.addWidget(self.widget_beamline_setup)
        self.layout_beamline_status.addWidget(widget_beamline_status.UIBeamlineStatus(shutters_dict))

        self.push_re_abort.clicked.connect(self.re_abort)

        # After connecting signals to slots, start receiving thread
        self.receiving_thread.start()

        # Redirect terminal output to GUI
        self.emitstream_out = EmittingStream.EmittingStream(self.textEdit_terminal)
        self.emitstream_err = EmittingStream.EmittingStream(self.textEdit_terminal)

        sys.stdout = self.emitstream_out
        sys.stderr = self.emitstream_err
        self.setWindowTitle(window_title)

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

#
class ReceivingThread(QThread):
    received_interp_data = QtCore.pyqtSignal(object)
    received_bin_data = QtCore.pyqtSignal(object)
    received_req_interp_data = QtCore.pyqtSignal(object)
    def __init__(self, gui):
        QThread.__init__(self)
        self.setParent(gui)

    def run(self):
        consumer = self.parent().consumer
        for message in consumer:
            # bruno concatenates and extra message at beginning of this packet
            # we need to take it off
            message = message.value[len(self.parent().hostname_filter):]
            data = pickle.loads(message)

            if 'data' in data['processing_ret']:
                #data['processing_ret']['data'] = pd.read_msgpack(data['processing_ret']['data'])
                data['processing_ret']['data'] = data['processing_ret']['data'].decode()

            if data['type'] == 'spectroscopy':
                if data['processing_ret']['type'] == 'interpolate':
                    self.received_interp_data.emit(data)
                if data['processing_ret']['type'] == 'bin':
                    self.received_bin_data.emit(data)
                if data['processing_ret']['type'] == 'request_interpolated_data':
                    self.received_req_interp_data.emit(data)
