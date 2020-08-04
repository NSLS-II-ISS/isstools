import datetime
from timeit import default_timer as timer

import numpy as np
import pkg_resources
from PyQt5 import uic, QtCore
from PyQt5.QtCore import QThread, QSettings
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import time
from pyzbar.pyzbar import decode as pzDecode
import bluesky.plan_stubs as bps
from xas.xray import generate_energy_grid

from isstools.dialogs.BasicDialogs import question_message_box, message_box
from isstools.elements.figure_update import update_figure
from isstools.elements.parameter_handler import parse_plan_parameters, return_parameters_from_widget
from isstools.widgets import widget_energy_selector
from isstools.elements.batch_motion import shift_stage_to_zero, move_to_sample, SamplePositioner

from isstools.process_callbacks.callback import run_router


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_camera.ui')

class UICamera(*uic.loadUiType(ui_path)):
    def __init__(self,
                 camera_dict={},
                 sample_stage = {},
                 RE = None,
                 parent_gui = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.sample_stage = sample_stage
        self.RE = RE
        self.addCanvas()
        self.cid = self.canvas_c1.mpl_connect('button_press_event', self.set_hcursor)
        self.cid = self.canvas_c2.mpl_connect('button_press_event', self.set_vcursor)
        self.h_vc = None
        self.h_hc = None
        self.qr_vc = None
        self.qr_hc = None

        self.push_show_image.clicked.connect(self.show_image)
        self.push_zero_stage.clicked.connect(self.zero_stage)
        self.push_move_to_sample.clicked.connect(self.move_to_sample)
        self.push_park_stage.clicked.connect(self.park_stage)
        self.camera_dict = camera_dict


        self.settings = parent_gui.settings
        # print('DEBUGGING', self.settings.value('sample_stage_zero_x', defaultValue=250, type=int))
        self.spinBox_zero_x.setValue(self.settings.value('sample_stage_zero_x_pix', defaultValue=250, type=int))
        self.spinBox_zero_y.setValue(self.settings.value('sample_stage_zero_y_pix', defaultValue=250, type=int))

        sample_stage_zero_x_rbk = self.settings.value('sample_stage_zero_x_rbk', defaultValue=0, type=float)
        sample_stage_zero_y_rbk = self.settings.value('sample_stage_zero_y_rbk', defaultValue=0, type=float)

        self.spinBox_zero_x_rbk.setValue(sample_stage_zero_x_rbk)
        self.spinBox_zero_y_rbk.setValue(sample_stage_zero_y_rbk)

        self.sample_positioner = SamplePositioner(sample_stage_zero_x_rbk,
                                                  sample_stage_zero_y_rbk,
                                                  10.0, # delta_first_holder_x
                                                  10.0, # delta_first_holder_y
                                                  RE,
                                                  sample_stage)

        self.beam_x_position_on_camera = self.settings.value('beam_x_position_on_camera', defaultValue=250)
        self.beam_y_position_on_camera = self.settings.value('beam_y_position_on_camera', defaultValue=250)

        # print('DEBUGGING', self.spinBox_zero_x.value())
        #
        # self.spinBox_zero_x.valueChanged.connect(self._update_camera_settings)

        self.timer_track_camera = QtCore.QTimer(self)
        self.timer_track_camera.setInterval(1000)
        self.timer_track_camera.timeout.connect(self.track_camera)
        #self.timer_track_camera.start()


    def addCanvas(self):
        self.figure_c1 = Figure()
        self.figure_c1.set_facecolor(color='#FcF9F6')
        self.canvas_c1 = FigureCanvas(self.figure_c1)
        self.figure_c1.ax = self.figure_c1.add_subplot(111)

        self.figure_c1.tight_layout()
        self.toolbar_c1 = NavigationToolbar(self.canvas_c1, self, coordinates=True)
        self.plot_camera1.addWidget(self.toolbar_c1)
        self.plot_camera1.addWidget(self.canvas_c1)
        self.canvas_c1.draw_idle()

        self.figure_c2 = Figure()
        self.figure_c2.set_facecolor(color='#FcF9F6')
        self.canvas_c2 = FigureCanvas(self.figure_c2)
        self.figure_c2.ax = self.figure_c2.add_subplot(111)

        self.figure_c2.tight_layout()
        self.toolbar_c2 = NavigationToolbar(self.canvas_c2, self, coordinates=True)
        self.plot_camera2.addWidget(self.toolbar_c2)
        self.plot_camera2.addWidget(self.canvas_c2)
        self.canvas_c2.draw_idle()

        self.figure_qr = Figure()
        self.figure_qr.set_facecolor(color='#FcF9F6')
        self.canvas_qr = FigureCanvas(self.figure_qr)
        self.figure_qr.ax = self.figure_qr.add_subplot(111)

        self.figure_qr.tight_layout()
        self.toolbar_qr = NavigationToolbar(self.canvas_qr, self, coordinates=True)
        self.plot_camera_qr.addWidget(self.toolbar_qr)
        self.plot_camera_qr.addWidget(self.canvas_qr)
        self.canvas_qr.draw_idle()


    # def show_image(self, camera_):


    def show_image(self):
        if self.push_track.isChecked():
            self.timer_track_camera.start()
        else:
            self.timer_track_camera.singleShot(0, self.track_camera)

    def track_camera(self):
        camera1 = self.camera_dict['camera_sample1']
        camera2 = self.camera_dict['camera_sample2']
        camera_qr = self.camera_dict['camera_sample4']
        image1 = camera1.image.image
        image2 = camera2.image.image
        image_qr = camera_qr.image.image
        self.figure_c1.ax.imshow(image1, cmap='gray')
        self.figure_c2.ax.imshow(image2, cmap='gray')
        self.figure_qr.ax.imshow(image_qr, cmap='gray', origin='lower')

        # beam position from previous session
        self._set_vcursor()
        self._set_hcursor()

        # pretty cross
        self.set_qr_cursor()

        self.canvas_c1.draw_idle()
        self.canvas_c2.draw_idle()
        self.canvas_qr.draw_idle()


    def park_stage(self):
        # stage_x = self.spinBox_zero_x_rbk.value()
        # stage_y = self.spinBox_zero_y_rbk.value()
        # self.RE(bps.mv(self.sample_stage.x, stage_x))
        # self.RE(bps.mv(self.sample_stage.y, stage_y))
        self.sample_positioner.goto_park()
        self.show_image()


    def zero_stage(self):
        camera_qr = self.camera_dict['camera_sample4']
        image_qr = camera_qr.image.image
        qr_codes = pzDecode(image_qr)
        if qr_codes:
            for qr_code in qr_codes:
                qr_text = qr_code.data.decode('utf8')
                if qr_text == '0 position':
                    # self.label_qrcode.setText(qr_text)

                    # print('qr code center:',
                    #       qr_code.rect.left + qr_code.rect.width/2,
                    #       qr_code.rect.top + qr_code.rect.height/2)
                    # print('qr code should be moved by these pixels:',
                    #       qr_code.rect.left + qr_code.rect.width/2 - self.spinBox_zero_x.value(),
                    #       qr_code.rect.top + qr_code.rect.height/2 - self.spinBox_zero_y.value())

                    delta_x, delta_y = shift_stage_to_zero( qr_code.rect.left + qr_code.rect.width/2,
                                                            qr_code.rect.top + qr_code.rect.height/2,
                                                            self.spinBox_zero_x.value(),
                                                            self.spinBox_zero_y.value())
                    print('moving the giant_xy stage by (', delta_x, ',', delta_y, ')')
                    self.RE(bps.mvr(self.sample_stage.x, delta_x))
                    self.RE(bps.mvr(self.sample_stage.y, delta_y))
                    self.show_image()

                    self.sample_x_zero_pos = self.sample_stage.x.read()[self.sample_stage.x.name]['value']
                    self.sample_y_zero_pos = self.sample_stage.y.read()[self.sample_stage.y.name]['value']

                    self.spinBox_zero_x_rbk.setValue(self.sample_x_zero_pos)
                    self.spinBox_zero_y_rbk.setValue(self.sample_y_zero_pos)

                    # need to change the (delta_first_holder_x, delta_first_holder_y) upon update
                    self.sample_positioner = SamplePositioner(self.sample_x_zero_pos,
                                                              self.sample_y_zero_pos,
                                                              10.0,  # delta_first_holder_x
                                                              10.0,  # delta_first_holder_y
                                                              self.RE,
                                                              self.sample_stage)

                    self.settings.setValue('sample_stage_zero_x_pix', self.spinBox_zero_x.value())
                    self.settings.setValue('sample_stage_zero_y_pix', self.spinBox_zero_y.value())
                    self.settings.setValue('sample_stage_zero_x_rbk', self.spinBox_zero_x_rbk.value())
                    self.settings.setValue('sample_stage_zero_y_rbk', self.spinBox_zero_y_rbk.value())


    def move_to_sample(self):
        index_stack = self.spinBox_index_stack.value()
        index_holder = self.spinBox_index_holder.value()
        index_sample = self.spinBox_index_sample.value()
        self.sample_positioner.goto_sample(index_stack, index_holder, index_sample)
        # zero_x = self.spinBox_zero_x_rbk.value()
        # zero_y = self.spinBox_zero_y_rbk.value()
        #
        # qr_code_111_x = 281.859
        # qr_code_111_y = -24.866
        # delta_first_holder_x = qr_code_111_x - zero_x
        # delta_first_holder_y = qr_code_111_y - zero_y
        #
        # giant_x, giant_y = move_to_sample(zero_x, zero_y, delta_first_holder_x, delta_first_holder_y,
        #                                   index_stack, index_holder, index_sample)
        # print('moving the giant_xy stage by (', giant_x - self.sample_stage.x.read()[self.sample_stage.x.name]['value'], ',',
        #                                         giant_y - self.sample_stage.y.read()[self.sample_stage.y.name]['value'], ')')
        # # print(giant_x - zero_x, giant_y - zero_y)
        # self.RE(bps.mv(self.sample_stage.x, giant_x))
        # self.RE(bps.mv(self.sample_stage.y, giant_y))
        # self.show_image()



    def set_vcursor(self, event):
        # wrapper for separation of event and xdata
        if event.button == 3:
            self.beam_x_position_on_camera = event.xdata
            self.settings.setValue('beam_x_position_on_camera', self.beam_x_position_on_camera)
            self._set_vcursor()

    def _set_vcursor(self):
        xdata = self.beam_x_position_on_camera
        if self.h_vc:
            self.h_vc.remove()
        y1, y2 = self.figure_c2.ax.get_ylim()
        self.h_vc = self.figure_c2.ax.vlines(xdata, y1,y2, color = 'green' )
        self.canvas_c2.draw_idle()


    def set_hcursor(self, event):
        # wrapper for separation of event and ydata
        if event.button == 3:
            self.beam_y_position_on_camera = event.ydata
            self.settings.setValue('beam_y_position_on_camera', self.beam_y_position_on_camera)
            self._set_hcursor()


    def _set_hcursor(self):
        ydata = self.beam_y_position_on_camera
        if self.h_hc:
            self.h_hc.remove()
        x1, x2 = self.figure_c1.ax.get_xlim()
        self.h_hc = self.figure_c1.ax.hlines(ydata, x1, x2, color='green')
        self.canvas_c1.draw_idle()



    def set_qr_cursor(self):
        color = [0.0, 0.7, 0.0]
        y_lo, y_hi = self.figure_qr.ax.get_xlim()
        x_lo, x_hi = self.figure_qr.ax.get_ylim()
        if self.qr_vc:
            self.qr_vc.remove()
        if self.qr_hc:
            self.qr_hc.remove()

        self.qr_vc = self.figure_qr.ax.vlines(self.spinBox_zero_x.value(), x_lo, x_hi, colors=color, linewidths=0.5)
        self.qr_hc = self.figure_qr.ax.hlines(self.spinBox_zero_y.value(), y_lo, y_hi, colors=color, linewidths=0.5)
        # self.figure_qr.ax.set_xlim(y_low, y_high)
        # self.figure_qr.ax.set_ylim(x_low, x_high)






