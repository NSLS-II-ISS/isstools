import re
import sys
import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtCore import QThread, QSettings

from isstools.widgets import (widget_general_info, widget_trajectory_manager, widget_processing,
                              widget_batch_mode, widget_run, widget_beamline_setup,
                              widget_sdd_manager, widget_beamline_status, widget_camera, widget_autopilot)

from isstools.elements.emitting_stream import EmittingStream
from isstools.process_callbacks.callback import FlyScanProcessingCallback

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
                 camera_dict={},
                 sample_stage=None,
                 tune_elements=None,
                 ic_amplifiers={},
                 window_title=" ",
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

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.RE = RE
        self.db = db
        self.token = None
        self.window_title = window_title
        
        if RE is not None:
            RE.is_aborted = False
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update_re_state)
            self.timer.start(1000)

        hhm.trajectory_progress.subscribe(self.update_progress)
        self.progress_sig.connect(self.update_progressbar)
        self.progressBar.setValue(0)
        self.settings = QSettings(self.window_title, 'XLive')

        self.run_mode = 'run'
        self.window_title = window_title

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



        self.widget_trajectory_manager = widget_trajectory_manager.UITrajectoryManager(hhm,
                                                                                       aux_plan_funcs= aux_plan_funcs
                                                                                       )
        self.layout_trajectory_manager.addWidget(self.widget_trajectory_manager)

        self.widget_processing = widget_processing.UIProcessing(hhm,
                                                                db,
                                                                parent_gui=self,
                                                                )
        self.layout_processing.addWidget(self.widget_processing)

        self.widget_run = widget_run.UIRun(plan_funcs,
                                            aux_plan_funcs,
                                            RE,
                                            db,
                                            hhm,
                                            shutters_dict,
                                            adc_list,
                                            enc_list,
                                            xia,
                                            self,
                                           )
        self.layout_run.addWidget(self.widget_run)

        self.widget_camera = widget_camera.UICamera(camera_dict,
                                                    sample_stage,
                                                    RE,
                                                    self
                                                    )
        self.layout_camera.addWidget(self.widget_camera)



        self.widget_batch_mode = widget_batch_mode.UIBatchMode(plan_funcs,
                                                                      service_plan_funcs,
                                                                      hhm,
                                                                      RE,
                                                                      sample_stage,
                                                                      self,
                                                                      )
        self.layout_batch.addWidget(self.widget_batch_mode)
        self.widget_trajectory_manager.trajectoriesChanged.connect(self.widget_batch_mode.widget_batch_manual.update_batch_traj)

        self.widget_beamline_setup = widget_beamline_setup.UIBeamlineSetup(RE,
                                                                           hhm,
                                                                           db,
                                                                           adc_list,
                                                                           enc_list,
                                                                           det_dict,
                                                                           xia,
                                                                           ic_amplifiers,
                                                                           service_plan_funcs,
                                                                           aux_plan_funcs,
                                                                           motors_dict,
                                                                           tune_elements,
                                                                           shutters_dict,
                                                                           self)
        self.layout_beamline_setup.addWidget(self.widget_beamline_setup)
        self.layout_beamline_status.addWidget(widget_beamline_status.UIBeamlineStatus(shutters_dict))
        self.push_re_abort.clicked.connect(self.re_abort)

        self.widget_general_info = widget_general_info.UIGeneralInfo(accelerator,
                                                                     hhm,
                                                                     shutters_dict,
                                                                     ic_amplifiers,
                                                                     RE,
                                                                     db,
                                                                     self)
        self.layout_general_info.addWidget(self.widget_general_info)

        self.widget_autopilot = widget_autopilot.UIAutopilot(motors_dict, camera_dict, hhm, RE, sample_stage, self)
        self.layout_autopilot.addWidget(self.widget_autopilot)


        
        pc = FlyScanProcessingCallback(db=self.db, draw_func_interp=self.widget_run.draw_interpolated_data, draw_func_bin=self.widget_processing.new_bin_df_arrived)
        self.fly_token = self.RE.subscribe(pc, 'stop')

        # Redirect terminal output to GUI
        self.emitstream_out = EmittingStream(self.textEdit_terminal)
        self.emitstream_err = EmittingStream(self.textEdit_terminal)

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
        palette = self.label_RE_state.palette()
        if (self.RE.state == 'idle'):
            palette.setColor(self.label_RE_state.foregroundRole(), QtGui.QColor(193, 140, 15))
        elif (self.RE.state == 'running'):
            palette.setColor(self.label_RE_state.foregroundRole(), QtGui.QColor(0, 165, 0))
        elif (self.RE.state == 'paused'):
            palette.setColor(self.label_RE_state.foregroundRole(), QtGui.QColor(255, 0, 0))
        elif (self.RE.state == 'abort'):
            palette.setColor(self.label_RE_state.foregroundRole(), QtGui.QColor(255, 0, 0))
        self.label_RE_state.setPalette(palette)
        self.label_RE_state.setText(self.RE.state)


