import re
import sys
import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtCore import QThread, QSettings

from .widgets import (widget_info_general,
                      widget_scan_manager,
                      widget_processing,
                      widget_batch,
                      widget_run,
                      widget_beamline_setup,
                      widget_sdd_manager,
                      widget_info_shutters,
                      widget_info_beamline,
                      widget_camera,
                      widget_autopilot,
                      widget_spectrometer,
                      widget_plan_queue)

from isstools.elements.batch_motion import SamplePositioner
from .elements.emitting_stream import EmittingStream
from .process_callbacks.callback import ScanProcessingCallback
from .elements.cloud_dispatcher import CloudDispatcher
from isscloudtools.initialize import get_dropbox_service, get_gmail_service, get_slack_service
from isscloudtools.gmail import create_html_message, upload_draft, send_draft
import time as ttime
from xas.process import process_interpolate_bin


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xlive.ui')



def auto_redraw_factory(fnc):
    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback


class XliveGui(*uic.loadUiType(ui_path)):
    plans_changed_signal = QtCore.pyqtSignal()
    plan_processor_status_changed_signal = QtCore.pyqtSignal()
    progress_sig = QtCore.pyqtSignal()

    def __init__(self,
                 service_plan_funcs=None,
                 aux_plan_funcs=None,
                 scan_manager=None,
                 plan_processor=None,
                 RE=None,
                 db=None,
                 db_proc=None,
                 accelerator=None,
                 hhm=None,
                 hhm_encoder=None,
                 hhm_feedback=None,
                 trajectory_manager=None,
                 johann_spectrometer_motor=None,
                 sdd=None,
                 pil100k=None,
                 apb=None,
                 apb_trigger_xs=None,
                 apb_trigger_pil100k=None,
                 detector_dict=None,
                 shutter_dict=None,
                 motor_dict=None,
                 camera_dict=None,
                 sample_stage=None,
                 tune_elements=None,
                 ic_amplifiers=None,
                 window_title=None,
                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.RE = RE
        self.db = db
        self.db_proc = db_proc
        self.apb = apb
        self.hhm = hhm
        self.hhm_encoder = hhm_encoder
        self.token = None
        self.window_title = window_title
        self.scan_manager = scan_manager
        self.plan_processor = plan_processor
        self.plan_processor.append_gui_plan_list_update_signal(self.plans_changed_signal)
        self.plan_processor.append_gui_status_update_signal(self.plan_processor_status_changed_signal)

        if RE is not None:
            RE.is_aborted = False
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update_re_state)
            self.timer.start(1000)

        hhm.trajectory_progress.subscribe(self.update_progress)
        self.progress_sig.connect(self.update_progressbar)
        self.progressBar.setValue(0)
        self.settings = QSettings(self.window_title, 'XLive')

        self.processing_thread = processing_thread(self)

        # define sample positioner to pass it to widget camera and further
        stage_park_x = self.settings.value('stage_park_x', defaultValue=0, type=float)
        stage_park_y = self.settings.value('stage_park_y', defaultValue=0, type=float)
        sample_park_x = self.settings.value('sample_park_x', defaultValue=0, type=float)
        sample_park_y = self.settings.value('sample_park_y', defaultValue=0, type=float)
        self.sample_positioner = SamplePositioner(self.RE,
                                                  sample_stage,
                                                  stage_park_x,
                                                  stage_park_y,
                                                  delta_first_holder_x=sample_park_x - stage_park_x,
                                                  delta_first_holder_y=sample_park_y - stage_park_y)


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


        print('widget run loading', ttime.ctime())
        self.widget_run = widget_run.UIRun(scan_manager=scan_manager,
                                           plan_processor=plan_processor,
                                           parent=None,
                                           )
        self.layout_run.addWidget(self.widget_run)


        print('widget scan manager loading', ttime.ctime())
        self.widget_scan_manager = widget_scan_manager.UIScanManager(hhm=hhm,
                                                                     scan_manager=scan_manager,
                                                                     detector_dict=detector_dict,
                                                                     parent=self
                                                                     )
        self.layout_scan_manager.addWidget(self.widget_scan_manager)


        print('widget processing loading', ttime.ctime())
        self.widget_processing = widget_processing.UIProcessing(hhm,
                                                                db,
                                                                parent_gui=self,
                                                                )
        self.layout_processing.addWidget(self.widget_processing)


        print('widget camera loading', ttime.ctime())
        self.widget_camera = widget_camera.UICamera(camera_dict,
                                                    sample_stage,
                                                    self.sample_positioner,
                                                    RE,
                                                    parent_gui=self,
                                                    sample_registry=None
                                                    )
        self.layout_camera.addWidget(self.widget_camera)

        print('widget batch loading', ttime.ctime())
        self.widget_batch_mode = widget_batch.UIBatch(service_plan_funcs=service_plan_funcs,
                                                      hhm=hhm,
                                                      trajectory_manager=trajectory_manager,
                                                      RE=RE,
                                                      sample_stage=sample_stage,
                                                      parent_gui=self,
                                                      motors_dict=motor_dict,
                                                      camera_dict=camera_dict,
                                                      sample_positioner=self.sample_positioner
                                                      )
        self.layout_batch.addWidget(self.widget_batch_mode)

        print('widget beamline setup loading', ttime.ctime())
        self.widget_beamline_setup = widget_beamline_setup.UIBeamlineSetup(RE,
                                                                           hhm,
                                                                           hhm_encoder,
                                                                           hhm_feedback,
                                                                           apb,
                                                                           apb_trigger_xs,
                                                                           apb_trigger_pil100k,
                                                                           db,
                                                                           db_proc,
                                                                           detector_dict,
                                                                           ic_amplifiers,
                                                                           {}, # plan funcs
                                                                           service_plan_funcs,
                                                                           aux_plan_funcs,
                                                                           motor_dict,
                                                                           tune_elements,
                                                                           shutter_dict,
                                                                           self,
                                                                           )
        self.layout_beamline_setup.addWidget(self.widget_beamline_setup)

        #Info shutters
        self.layout_info_shutters.addWidget(widget_info_shutters.UIInfoShutters(shutter_dict))

        #Info general
        print('widget info general loading', ttime.ctime())
        self.widget_info_general = widget_info_general.UIInfoGeneral(RE=RE,
                                                                     db=db,
                                                                     parent=self
                                                                     )

        self.layout_info_general.addWidget(self.widget_info_general)

        # Info beamline
        print('widget info beamline loading', ttime.ctime())
        self.widget_info_beamline = widget_info_beamline.UIInfoBeamline(accelerator=accelerator,
                                                                        hhm=hhm,
                                                                        hhm_feedback=hhm_feedback,
                                                                        motor_emission=johann_spectrometer_motor,
                                                                        shutters=shutter_dict,
                                                                        ic_amplifiers=ic_amplifiers,
                                                                        RE=RE,
                                                                        db=None,
                                                                        foil_camera=detector_dict['Camera SP5']['device'],
                                                                        attenuator_camera=detector_dict['Camera SP6']['device'],
                                                                        encoder_pb = self.hhm_encoder,
                                                                        aux_plan_funcs=aux_plan_funcs,
                                                                        parent=self)
        self.layout_info_beamline.addWidget(self.widget_info_beamline)



        if sdd is not None:
            print('widget sdd manager loading', ttime.ctime())
            self.widget_sdd_manager = widget_sdd_manager.UISDDManager(service_plan_funcs,
                                                                      sdd,
                                                                      RE)
            self.layout_sdd_manager.addWidget(self.widget_sdd_manager)

        print('widget autopilot loading', ttime.ctime())
        self.widget_autopilot = widget_autopilot.UIAutopilot(motor_dict,
                                                             camera_dict,
                                                             hhm,
                                                             trajectory_manager,
                                                             RE,
                                                             # db,
                                                             sample_stage,
                                                             self,
                                                             service_plan_funcs,
                                                             {} # plan funcs
                                                             )
        self.layout_autopilot.addWidget(self.widget_autopilot)


        print('widget spectrometer loading', ttime.ctime())
        self.widget_spectrometer = widget_spectrometer.UISpectrometer(RE,
                                                                      db,
                                                                      detector_dict,
                                                                      motor_dict,
                                                                      shutter_dict,
                                                                      aux_plan_funcs,
                                                                      service_plan_funcs,
                                                                      parent=self
                                                                      )
        self.layout_spectrometer.addWidget(self.widget_spectrometer)

        self.widget_scan_manager.scansChanged.connect(self.widget_run.update_scan_defs)

        print('widget loading done', ttime.ctime())

        print('widget plan queue loading', ttime.ctime())
        self.widget_plan_queue = widget_plan_queue.UIPlanQueue(hhm=hhm,
                                                               plan_processor=plan_processor,
                                                               detector_dict=detector_dict,
                                                               parent=self)
        self.layout_plan_queue.addWidget(self.widget_plan_queue)

        # self.widget_run.plansAdded.connect(self.widget_plan_queue.update_plan_list)

        # self.widget_scan_manager.trajectoriesChanged.connect(
        #     self.widget_batch_mode.widget_batch_manual.update_batch_traj)

        print('widget loading done', ttime.ctime())


        self.push_re_abort.clicked.connect(self.re_abort)
        self.cloud_dispatcher = CloudDispatcher(dropbox_service=self.dropbox_service,slack_service=self.slack_client_bot)
        print(' >>>>>>>>>>> cloud dispatcher done', ttime.ctime())
        pc = ScanProcessingCallback(db=self.db, draw_func_interp=self.widget_run.draw_interpolated_data,
                                    draw_func_bin=None,
                                    cloud_dispatcher=self.cloud_dispatcher, thread=self.processing_thread)


        self.fly_token = self.RE.subscribe(pc, 'stop')
        print(' scan processing callback done', ttime.ctime())
        # Redirect terminal output to GUI
        self.emitstream_out = EmittingStream(self.textEdit_terminal)
        self.emitstream_err = EmittingStream(self.textEdit_terminal)

        sys.stdout = self.emitstream_out
        sys.stderr = self.emitstream_err
        self.setWindowTitle(window_title)
        #self.processing_thread.start()

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
            # self.push_re_abort.setEnabled(0)
            self.RE.abort()
            self.RE.state == 'abort'
            self.RE.is_aborted = True

        self.hhm.abort_trajectory()
            # self.push_re_abort.setEnabled(1)

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



class processing_thread(QThread):
    def __init__(self, gui):
        QThread.__init__(self)
        self.gui = gui
        self.doc = None

    def run(self):
        attempt = 0
        while self.doc:
            try:
                attempt += 1
                uid = self.doc['run_start']
                print(f'({ttime.ctime()}) File received {uid}')
                process_interpolate_bin(self.doc, self.gui.db, self.gui.widget_run.draw_interpolated_data, None, self.gui.cloud_dispatcher)
                self.doc = None
            except Exception as e:
                print(e)
                print(f'>>>>>> #{attempt} Attempt to process data ({ttime.ctime()}) ')
                ttime.sleep(1)
            if attempt == 5:
                break




