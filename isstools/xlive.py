import re
import sys
import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtCore import QThread, QSettings

from .widgets import (widget_info_general,
                      widget_trajectory_manager,
                      widget_processing,
                      widget_batch,
                      widget_run,
                      widget_beamline_setup,
                      widget_sdd_manager,
                      widget_info_shutters,
                      widget_info_beamline,
                      widget_camera,
                      widget_autopilot,
                      widget_spectrometer)


from .elements.emitting_stream import EmittingStream
from .process_callbacks.callback import ScanProcessingCallback
from .elements.cloud_dispatcher import CloudDispatcher
from isscloudtools.initialize import get_dropbox_service, get_gmail_service, get_slack_service
from isscloudtools.gmail import create_html_message, upload_draft, send_draft
import time as ttime
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xlive.ui')



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
                 sdd = None,
                 shutters_dict={},
                 det_dict={},
                 motors_dict={},
                 camera_dict={},
                 sample_stage=None,
                 tune_elements=None,
                 ic_amplifiers={},
                 window_title=" ",
                 apb = None,
                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.RE = RE
        self.db = db
        self.apb = apb
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
        print('cloud starting', ttime.ctime())
        try:
            print('starting slackbot', ttime.ctime())
            self.slack_client_bot, self.slack_client_oath = get_slack_service()
            print('done slackbot', ttime.ctime())
            self.gmail_service = get_gmail_service()
            #self.gmail_service = None
            print('starting dropbox', ttime.ctime())
            self.dropbox_service = get_dropbox_service()
            print('done dropbox', ttime.ctime())
        except:
            print("Cloud services cannot be connected")
            self.slack_client_bot = None
            self.slack_client_oath = None
            self.gmail_service = None
            self.dropbox_service = None
        print('cloud complete', ttime.ctime())
        print('widget trajectory loading', ttime.ctime())
        self.widget_trajectory_manager = widget_trajectory_manager.UITrajectoryManager(
            hhm,
            aux_plan_funcs=aux_plan_funcs

        )
        self.layout_trajectory_manager.addWidget(self.widget_trajectory_manager)

        print('widget processing loading', ttime.ctime())
        self.widget_processing = widget_processing.UIProcessing(
            hhm,
            db,
            parent_gui=self,
        )
        self.layout_processing.addWidget(self.widget_processing)
        print('widget run loading', ttime.ctime())
        self.widget_run = widget_run.UIRun(
            plan_funcs,
            aux_plan_funcs,
            RE,
            db,
            hhm,
            det_dict,
            shutters_dict,
            apb,
            self,
        )
        self.layout_run.addWidget(self.widget_run)
        print('widget camera loading', ttime.ctime())
        self.widget_camera = widget_camera.UICamera(
            camera_dict,
            sample_stage,
            RE,
            self
        )
        self.layout_camera.addWidget(self.widget_camera)
        print('widget batch loading', ttime.ctime())
        self.widget_batch_mode = widget_batch.UIBatch(
            plan_funcs,
            service_plan_funcs,
            hhm,
            RE,
            sample_stage,
            self,
            motors_dict,
            camera_dict,
        )
        self.layout_batch.addWidget(self.widget_batch_mode)



        #Beamline setup
        print('widget beamline setup loading', ttime.ctime())
        self.widget_beamline_setup = widget_beamline_setup.UIBeamlineSetup(
            RE,
            hhm,
            db,
            det_dict,
            ic_amplifiers,
            service_plan_funcs,
            aux_plan_funcs,
            motors_dict,
            tune_elements,
            shutters_dict,
            self,
        )
        self.layout_beamline_setup.addWidget(self.widget_beamline_setup)

        #Info shutters
        self.layout_info_shutters.addWidget(widget_info_shutters.UIInfoShutters(shutters_dict))

        #Info general
        print('widget info general loading', ttime.ctime())
        self.widget_info_general = widget_info_general.UIInfoGeneral(RE=RE,
                                                                     db=db,
                                                                      parent=self)

        self.layout_info_general.addWidget(self.widget_info_general)

        #Info beamline
        print('widget info beamline loading', ttime.ctime())
        self.widget_info_beamline = widget_info_beamline.UIInfoBeamline(
            accelerator=accelerator,
            hhm=hhm,
            shutters=shutters_dict,
            ic_amplifiers=ic_amplifiers,
            apb=apb,
            RE=RE,
            db=None,
            parent=self
        )
        self.layout_info_beamline.addWidget(self.widget_info_beamline)



        if sdd is not None:
            print('widget sdd manager loading', ttime.ctime())
            self.widget_sdd_manager = widget_sdd_manager.UISDDManager(service_plan_funcs, sdd, RE)
            self.layout_sdd_manager.addWidget(self.widget_sdd_manager)
        print('widget autopilot loading', ttime.ctime())
        self.widget_autopilot = widget_autopilot.UIAutopilot(
            motors_dict,
            camera_dict,
            hhm,
            RE,
            # db,
            sample_stage,
            self,
            service_plan_funcs,
            plan_funcs
        )
        self.layout_autopilot.addWidget(self.widget_autopilot)
        print('widget spectrometer loading', ttime.ctime())
        self.widget_spectrometer = widget_spectrometer.UISpectrometer(
            RE,
            db,
            det_dict,
            motors_dict,
            aux_plan_funcs,
            service_plan_funcs,
        )
        self.layout_spectrometer.addWidget(self.widget_spectrometer)

        self.widget_trajectory_manager.trajectoriesChanged.connect(
            self.widget_batch_mode.widget_batch_manual.update_batch_traj)

        print('widget loading done', ttime.ctime())

        self.push_re_abort.clicked.connect(self.re_abort)

        cloud_dispatcher = CloudDispatcher(dropbox_service=self.dropbox_service,slack_service=self.slack_client_bot)

        print(' cloud dispatcher done', ttime.ctime())
        pc = ScanProcessingCallback(db=self.db, draw_func_interp=self.widget_run.draw_interpolated_data,
                                    draw_func_bin=None,
                                    cloud_dispatcher = cloud_dispatcher)
        self.fly_token = self.RE.subscribe(pc, 'stop')
        print(' scan processgin callback done', ttime.ctime())
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


