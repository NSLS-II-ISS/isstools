import re
import sys
import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore, QtWidgets

from PyQt5.QtCore import QThread, QSettings

from .widgets import (widget_info_general,
                      widget_scan_manager,
                      widget_processing,
                      widget_batch,
                      widget_run,
                      widget_beamline_setup,
                      widget_sdd_manager,
                      widget_xia_manager,
                      widget_info_shutters,
                      widget_info_beamline,
                      widget_sample_registry,
                      widget_spectrometer,
                      widget_plan_queue,
                      widget_sample_manager,
                      widget_user_manager)

from isstools.elements.batch_motion import SamplePositioner
from .elements.emitting_stream import EmittingStream
from .process_callbacks.callback import ScanProcessingCallback
from isscloudtools.cloud_dispatcher import CloudDispatcher
from isscloudtools.initialize import get_dropbox_service, get_gmail_service, get_slack_service
from isscloudtools.gmail import create_html_message, upload_draft, send_draft
import time as ttime
from xas.process import process_interpolate_bin
from isstools.dialogs.BasicDialogs import question_message_box, error_message_box, message_box

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
                 data_collection_plan_funcs=None,
                 service_plan_funcs=None,
                 aux_plan_funcs=None,
                 scan_manager=None,
                 sample_manager=None,
                 scan_sequence_manager=None,
                 batch_manager=None,
                 user_manager=None,
                 plan_processor=None,
                 RE=None,
                 db=None,
                 processing_ioc_uid=None,
                 accelerator=None,
                 front_end=None,
                 hhm=None,
                 hhm_encoder=None,
                 hhm_feedback=None,
                 trajectory_manager=None,
                 johann_emission=None,
                 johann_spectrometer_manager=None,
                 sdd=None,
                 ge_detector=None,
                 inclinometers = None,
                 pil100k=None,
                 apb=None,
                 apb_trigger_xs=None,
                 apb_trigger_pil100k=None,
                 detector_dict=None,
                 shutter_dict=None,
                 motor_dict=None,
                 camera_dict=None,
                 sample_env_dict=None,
                 sample_stage=None,
                 tune_elements=None,
                 ic_amplifiers=None,
                 print_to_gui=None,
                 window_title=None,
                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.RE = RE
        self.db = db
        self.apb = apb
        self.hhm = hhm
        self.hhm_encoder = hhm_encoder
        self.token = None
        self.window_title = window_title
        self.motor_dict = motor_dict
        self.scan_manager = scan_manager
        self.johann_emission = johann_emission
        self.plan_processor = plan_processor
        # self.plan_processor.append_gui_plan_list_update_signal(self.plans_changed_signal)
        self.plan_processor.append_list_update_signal(self.plans_changed_signal)
        self.plan_processor.append_gui_status_update_signal(self.plan_processor_status_changed_signal)
        self.data_collection_plan_funcs = data_collection_plan_funcs
        self.print_to_gui = print_to_gui

        self.manager_dict = {'scan_manager' : scan_manager,
                             'sample_manager' : sample_manager,
                             'scan_sequence_manager' : scan_sequence_manager,
                             'batch_manager' : batch_manager,
                             'plan_processor' : plan_processor,}

        if RE is not None:
            RE.is_aborted = False
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update_re_state)
            self.timer.start(1000)

        hhm.trajectory_progress.subscribe(self.update_progress)
        self.progress_sig.connect(self.update_progressbar)
        self.progressBar.setValue(0)
        self.settings = QSettings(self.window_title, 'XLive')



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
        self.dropbox_service = get_dropbox_service()
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
                                           sample_manager=sample_manager,
                                           plan_processor=plan_processor,
                                           sample_env_dict=sample_env_dict,
                                           hhm=hhm,
                                           johann_spectrometer_motor=johann_emission,
                                           parent=None,
                                           )
        self.layout_run.addWidget(self.widget_run)



        print('widget scan manager loading', ttime.ctime())
        self.widget_scan_manager = widget_scan_manager.UIScanManager(hhm=hhm,
                                                                     scan_manager=scan_manager,
                                                                     johann_spectrometer_manager=johann_spectrometer_manager,
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

        print('widget user loading', ttime.ctime())
        self.widget_user_manager = widget_user_manager.UIUserManager(
                                                                      RE=RE,
                                                                      parent=self,
                                                                      user_manager=user_manager,
                                                                      sample_manager=sample_manager,
                                                                      scan_manager=scan_manager,

                                                                      )
        self.layout_user_manager.addWidget(self.widget_user_manager)


        print('widget camera loading', ttime.ctime())
        self.widget_sample_manager = widget_sample_manager.UISampleManager(sample_stage=sample_stage,
                                                                           motor_dict=motor_dict,
                                                                           camera_dict=camera_dict,
                                                                           sample_manager=sample_manager,
                                                                           plan_processor=plan_processor,
                                                                           parent=self)
        self.layout_sample_manager.addWidget(self.widget_sample_manager)



        print('widget batch loading', ttime.ctime())
        self.widget_batch_mode = widget_batch.UIBatch(service_plan_funcs=service_plan_funcs,
                                                      hhm=hhm,
                                                      trajectory_manager=trajectory_manager,
                                                      RE=RE,
                                                      sample_manager=sample_manager,
                                                      scan_manager=scan_manager,
                                                      scan_sequence_manager=scan_sequence_manager,
                                                      batch_manager=batch_manager,
                                                      plan_processor=plan_processor,
                                                      sample_stage=sample_stage,
                                                      parent_gui=self,
                                                      motors_dict=motor_dict,
                                                      camera_dict=camera_dict,
                                                      sample_positioner=self.sample_positioner
                                                      )
        self.layout_batch.addWidget(self.widget_batch_mode)

        print('widget beamline setup loading', ttime.ctime())
        self.widget_beamline_setup = widget_beamline_setup.UIBeamlineSetup(plan_processor,
                                                                           hhm,
                                                                           hhm_encoder,
                                                                           hhm_feedback,
                                                                           apb,
                                                                           apb_trigger_xs,
                                                                           apb_trigger_pil100k,
                                                                           db,
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
        self.widget_info_shutters = widget_info_shutters.UIInfoShutters(shutters=shutter_dict,
                                                                        plan_processor=plan_processor,
                                                                        parent=self)
        self.layout_info_shutters.addWidget(self.widget_info_shutters)

        #Info general
        print('widget info general loading', ttime.ctime())
        self.widget_info_general = widget_info_general.UIInfoGeneral(RE=RE,
                                                                     db=db,
                                                                     parent=self,
                                                                     manager_dict=self.manager_dict
                                                                     )

        self.layout_info_general.addWidget(self.widget_info_general)

        # Info beamline
        print('widget info beamline loading', ttime.ctime())
        self.widget_info_beamline = widget_info_beamline.UIInfoBeamline(accelerator=accelerator,
                                                                        front_end=front_end,
                                                                        hhm=hhm,
                                                                        hhm_feedback=hhm_feedback,
                                                                        motor_emission=johann_emission,
                                                                        inclinometers = inclinometers,
                                                                        shutters=shutter_dict,
                                                                        ic_amplifiers=ic_amplifiers,
                                                                        apb=apb,
                                                                        RE=RE,
                                                                        plan_processor=plan_processor,
                                                                        db=None,
                                                                        foil_camera=detector_dict['Camera SP5']['device'],
                                                                        attenuator_camera=detector_dict['Camera SP6']['device'],
                                                                        encoder_pb = self.hhm_encoder,
                                                                        aux_plan_funcs=aux_plan_funcs,
                                                                        parent=self)
        self.layout_info_beamline.addWidget(self.widget_info_beamline)



        if sdd is not None:
            print('widget 4 element Si detector manager loading', ttime.ctime())
            self.widget_sdd_manager = widget_sdd_manager.UISDDManager(service_plan_funcs,
                                                                      sdd,
                                                                      RE,
                                                                      )
            self.layout_sdd_manager.addWidget(self.widget_sdd_manager)

        if ge_detector is not None:
            print('widget 32 element Ge detector manager loading', ttime.ctime())
            self.widget_xia_manager = widget_xia_manager.UIXIAManager(service_plan_funcs=service_plan_funcs,
                                                                      ge_detector=ge_detector,
                                                                      RE=RE,
                                                                      )
            self.layout_xia_manager.addWidget(self.widget_xia_manager)

        print('widget sample registry loading', ttime.ctime())
        self.widget_sample_registry = widget_sample_registry.UISampleRegistry(motor_dict,
                                                                            camera_dict,
                                                                            hhm,
                                                                            trajectory_manager,
                                                                            RE,
                                                                            # db,
                                                                            sample_stage,
                                                                            self,
                                                                            service_plan_funcs,
                                                                            {}  # plan funcs
                                                                            )
        self.layout_sample_registry.addWidget(self.widget_sample_registry)


        print('widget spectrometer loading', ttime.ctime())
        self.widget_spectrometer = widget_spectrometer.UISpectrometer(RE,
                                                                      plan_processor,
                                                                      hhm,
                                                                      db,
                                                                      johann_emission,
                                                                      johann_spectrometer_manager,
                                                                      detector_dict,
                                                                      motor_dict,
                                                                      shutter_dict,
                                                                      aux_plan_funcs,
                                                                      service_plan_funcs,
                                                                      parent=self
                                                                      )
        self.layout_spectrometer.addWidget(self.widget_spectrometer)





        self.widget_scan_manager.scansChanged.connect(self.widget_run.update_scan_defs)
        self.widget_scan_manager.scansChanged.connect(self.widget_batch_mode.update_scan_defs)
        self.widget_scan_manager.scansChanged.connect(self.widget_user_manager.update_scan_list)


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
        self.processing_thread = ProcessingThread(self, print_func=print_to_gui, processing_ioc_uid=processing_ioc_uid)

        self.push_re_abort.clicked.connect(self.re_abort)
        self.cloud_dispatcher = CloudDispatcher(dropbox_service=self.dropbox_service,slack_service=self.slack_client_bot)
        print(' Cloud dispatcher initialization is complete`q', ttime.ctime())
        pc = ScanProcessingCallback(db=self.db, draw_func_interp=self.widget_run.draw_interpolated_data,
                                    draw_func_bin=None,
                                    cloud_dispatcher=self.cloud_dispatcher, thread=self.processing_thread, print_func=print_to_gui)


        self.fly_token = self.RE.subscribe(pc, 'stop')
        #print(' scan processing callback done', ttime.ctime())
        # Redirect terminal output to GUI
        self.emitstream_out = EmittingStream(self.textEdit_terminal)
        self.emitstream_err = EmittingStream(self.textEdit_terminal)

        sys.stdout = self.emitstream_out
        sys.stderr = self.emitstream_err
        self.setWindowTitle(window_title)
        #self.processing_thread.start()

        sample_manager.list_update_signal.connect(self.widget_run.update_sample_defs)

        self.plan_processor.append_liveplot_maker(self.make_liveplot_func)
        self.define_gui_services_dict()
        self.plan_processor.append_gui_services_dict(self.gui_services_dict)
        self.plan_processor.append_add_plans_question_box_func(self.add_plans_question_box)

    def make_liveplot_func(self, plan_name, plan_kwargs):
        if plan_name in self.data_collection_plan_funcs.keys():
            liveplot_list = self.widget_run.make_xasplot_func(plan_name, plan_kwargs)
        elif plan_name in ['general_scan', 'tuning_scan', 'quick_tuning_scan',
                           'obtain_hhm_calibration_plan', 'obtain_spectrometer_resolution_plan',
                           'tune_johann_piezo_plan', 'johann_analyze_alignment_data_plan',
                           'find_optimal_crystal_alignment_position_plan']:
            if plan_kwargs['liveplot_kwargs'] is not None:
                if 'tab' in plan_kwargs['liveplot_kwargs'].keys():
                    if plan_kwargs['liveplot_kwargs']['tab'] == 'spectrometer':
                        liveplot_list = self.widget_spectrometer.make_liveplot_func(plan_name, plan_kwargs)
                else:
                    liveplot_list = self.widget_beamline_setup.make_liveplot_func(plan_name, plan_kwargs)
            else:
                liveplot_list = []
        else:
            liveplot_list = []

        return liveplot_list

    def define_gui_services_dict(self):
        self.gui_services_dict = {'beamline_setup_plot_energy_calibration_data' :
                                         {'kwarg_name' : 'plot_func',
                                          'kwarg_value' : self.widget_beamline_setup._update_figure_with_calibration_data},
                                  'beamline_setup_plot_quick_tune_data':
                                      {'kwarg_name': 'plot_func',
                                       'kwarg_value': self.widget_beamline_setup._update_figure_with_tuning_data},
                                  'error_message_box' : {'kwarg_name' : 'error_message_func',
                                                         'kwarg_value' : error_message_box},
                                  'question_message_box': {'kwarg_name': 'question_message_func',
                                                           'kwarg_value': self.question_message_box_func},
                                  'spectrometer_plot_epics_fly_scan_data':
                                      {'kwarg_name': 'plot_func',
                                       'kwarg_value': self.widget_spectrometer._update_figure_with_scan_data},
                                  'spectrometer_plot_alignment_scan_data':
                                      {'kwarg_name': 'plot_data_func',
                                       'kwarg_value': self.widget_spectrometer._update_figure_with_scan_data},
                                  'spectrometer_plot_alignment_analysis_data':
                                      {'kwarg_name': 'plot_analysis_func',
                                       'kwarg_value': self.widget_spectrometer._update_figure_with_analysis_data},
                                  }

    def question_message_box_func(self, *args):
        return question_message_box(self, *args)


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
        hhm_flying = self.hhm.abort_trajectory() # it only aborts if there is a trajectory running
        # print(f'>>>>>>>>>>>>> HHM_FLYING = {hhm_flying}')
        # print(f'>>>>>>>>>>>>> HHM_FLYING_STATUS = {self.hhm.flying_status}')
        if not hhm_flying:
            if self.RE.state != 'idle':
                # self.push_re_abort.setEnabled(0)
                self.RE.abort()
                self.RE.state == 'abort'
                self.RE.is_aborted = True

        ret = question_message_box(self, 'Aborting the scan', 'Would you like to clear/reset queue?')

        self.plan_processor.pause_plan_list()
        if ret:
            self.plan_processor.reset()
        else:
            self.plan_processor.pause_plan_list()
            if not self.plan_processor.RE_is_running:
                self.plan_processor.update_status('idle')
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

    def add_plans_question_box(self, plans, add_at, idx, pause_after):
        messageBox = QtWidgets.QMessageBox()
        messageBox.setWindowTitle('Warning')
        messageBox.setText('Queue is not empty')
        messageBox.addButton(QtWidgets.QPushButton('Skip'), QtWidgets.QMessageBox.NoRole)
        messageBox.addButton(QtWidgets.QPushButton('Add to the beginning of the queue and pause after'), QtWidgets.QMessageBox.YesRole)
        messageBox.addButton(QtWidgets.QPushButton('Add to the beginning of the queue'), QtWidgets.QMessageBox.YesRole)
        messageBox.addButton(QtWidgets.QPushButton('Add to the end of the queue'), QtWidgets.QMessageBox.YesRole)
        ret = messageBox.exec_()
        if ret == 0:
            plans = []
        elif ret == 1:
            pause_after = True
            add_at = 'head'
        elif ret == 2:
            add_at = 'head'
        elif ret == 3:
            add_at = 'tail'
        return plans, add_at, idx, pause_after

class ProcessingThread(QThread):
    def __init__(self, gui, print_func=None, processing_ioc_uid=None):
        QThread.__init__(self)
        self.gui = gui
        self.camera1 = self.gui.widget_sample_manager.widget_camera1
        self.camera2 = self.gui.widget_sample_manager.widget_camera2
        self.doc = None
        if print_func is None:
            self.print = print
        else:
            def _print_func(msg):
                print_func(msg, tag='Processing here', add_timestamp=True)
            self.print = _print_func
        self.soft_mode = True
        self.processing_ioc_uid = processing_ioc_uid

    def run(self):
        attempt = 0
        while self.doc:
            try:
                attempt += 1
                uid = self.doc['run_start']
                if self.processing_ioc_uid is not None:
                    self.processing_ioc_uid.put(uid)
                else:
                    self.print(f' File received 1 {uid}')
                    process_interpolate_bin(self.doc,
                                            self.gui.db,
                                            draw_func_interp=self.gui.widget_run.draw_data,
                                            draw_func_bin=None,
                                            cloud_dispatcher=self.gui.cloud_dispatcher,
                                            print_func=self.print,
                                            save_image = True,
                                            camera1 = self.camera1,
                                            camera2 = self.camera2)


                self.doc = None
            except Exception as e:
                if self.soft_mode:
                    self.print(f'Exception: {e}')
                    self.print(f'>>>>>> #{attempt} Attempt to process data ({ttime.ctime()}) ')
                    ttime.sleep(3)
                else:
                    raise e
            if attempt == 5:
                break




