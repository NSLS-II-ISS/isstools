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
import matplotlib.patches as patches
import time
from pyzbar.pyzbar import decode as pzDecode
import bluesky.plan_stubs as bps
from xas.xray import generate_energy_grid

from isstools.dialogs.BasicDialogs import question_message_box, message_box
from isstools.elements.figure_update import update_figure
from isstools.elements.parameter_handler import parse_plan_parameters, return_parameters_from_widget
from isstools.widgets import widget_energy_selector
from isstools.elements.batch_motion import SamplePositioner
import time as ttime
from isstools.widgets import widget_sample_positioner
# from isstools.process_callbacks.callback import run_router


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_camera.ui')

class UICamera(*uic.loadUiType(ui_path)):
    def __init__(self,
                 camera_dict={},
                 sample_stage = {},
                 sample_positioner=None,
                 RE = None,
                 parent_gui = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        # beamline controls
        self.camera_dict = camera_dict
        self.sample_stage = sample_stage
        self.RE = RE
        self.parent = parent_gui

        # figure management
        self.addCanvas()
        self.cid = self.canvas_c1.mpl_connect('button_press_event', self.set_hcursor)
        self.cid = self.canvas_c2.mpl_connect('button_press_event', self.set_vcursor)
        self.cid = self.canvas_qr.mpl_connect('button_press_event', self.set_qr_roi)
        self.h_vc = None
        self.h_hc = None

        self.qr_roi_patch = None
        self.qr_hlines = None
        self.qr_vlines = None

        # taking images management
        self.push_show_image.clicked.connect(self.show_image)
        self.timer_track_camera = QtCore.QTimer(self)
        self.timer_track_camera.setInterval(1000)
        self.timer_track_camera.timeout.connect(self.track_camera)

        # stage positioning management
        self.push_stage_up.clicked.connect(self.stage_up)
        self.push_stage_down.clicked.connect(self.stage_down)
        self.push_stage_left.clicked.connect(self.stage_left)
        self.push_stage_right.clicked.connect(self.stage_right)
        self.push_update_stage_parking.clicked.connect(self.update_stage_parking)
        self.push_park_stage.clicked.connect(self.park_stage)
        self.push_update_sample_parking.clicked.connect(self.update_sample_parking)


        self.sample_positioner = sample_positioner
        self.settings = parent_gui.settings
        self.widget_sample_positioner = widget_sample_positioner.UISamplePositioner(parent=self,
                                                                     settings=self.settings,
                                                                     RE=RE,
                                                                     sample_positioner=sample_positioner)
        self.layout_sample_positioner.addWidget(self.widget_sample_positioner)

        # persistence management

        # stage_park_x = self.settings.value('stage_park_x', defaultValue=0, type=float)
        # stage_park_y = self.settings.value('stage_park_y', defaultValue=0, type=float)

        stage_park_x = sample_positioner.stage_park_x
        stage_park_y = sample_positioner.stage_park_y
        self.spinBox_stage_x.setValue(stage_park_x)
        self.spinBox_stage_y.setValue(stage_park_y)

        # sample_park_x = self.settings.value('sample_park_x', defaultValue=0, type=float)
        # sample_park_y = self.settings.value('sample_park_y', defaultValue=0, type=float)
        sample_park_x = sample_positioner.stage_park_x + sample_positioner.delta_first_holder_x
        sample_park_y = sample_positioner.stage_park_y + sample_positioner.delta_first_holder_y
        self.spinBox_sample_x.setValue(sample_park_x)
        self.spinBox_sample_y.setValue(sample_park_y)

        self.beam_x_position_on_camera = self.settings.value('beam_x_position_on_camera', defaultValue=250)
        self.beam_y_position_on_camera = self.settings.value('beam_y_position_on_camera', defaultValue=250)


        x1 = self.settings.value('qr_roi_x1', defaultValue=0, type=int)
        x2 = self.settings.value('qr_roi_x2', defaultValue=0, type=int)
        y1 = self.settings.value('qr_roi_y1', defaultValue=0, type=int)
        y2 = self.settings.value('qr_roi_y2', defaultValue=0, type=int)
        self.qr_roi = [(x1, y1), [x2, y2]]

        # sample positioner handle


        # get pictures on the GUI upon opening
        self.show_image()
        #self.timer_track_camera.start()


    # def _save_sample_index_settings(self):
    #     self.settings.setValue('index_stack', self.spinBox_index_stack.value())
    #     self.settings.setValue('index_holder', self.spinBox_index_holder.value())
    #     self.settings.setValue('index_sample', self.spinBox_index_sample.value())



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
        init_time = ttime.time()
        camera1 = self.camera_dict['camera_sample1']
        camera2 = self.camera_dict['camera_sample2']
        camera_qr = self.camera_dict['camera_sample4']
        image1 = camera1.image.image
        image2 = camera2.image.image
        image_qr = camera_qr.image.image
        vmin1, vmax1 = np.percentile(image1, 5), np.percentile(image1, 90)
        vmin2, vmax2 = np.percentile(image2, 5), np.percentile(image2, 90)
        vminqr, vmaxqr = np.percentile(image_qr, 5), np.percentile(image_qr, 90)
        print(f'Got images from PV {ttime.time()-init_time}')
        self.figure_c1.ax.imshow(image1, cmap='gray', vmin=vmin1, vmax=vmax1)
        self.figure_c2.ax.imshow(image2, cmap='gray', vmin=vmin2, vmax=vmax2)
        self.figure_qr.ax.imshow(image_qr, cmap='gray', origin='lower', vmin=vminqr, vmax=vmaxqr)
        print(f'Imshow {ttime.time() - init_time}')
        # beam position from previous session
        self._set_vcursor()
        self._set_hcursor()
        self.plot_qr_roi()
        # pretty cross
        # self.set_qr_cursor()

        self.canvas_c1.draw_idle()
        self.canvas_c2.draw_idle()
        self.canvas_qr.draw_idle()
        print(f'Done with images {ttime.time() - init_time}')


    def stage_up(self):
        v_step = self.spinBox_ver_step.value()
        self.RE(bps.mvr(self.sample_stage.y, v_step))
        self.show_image()

    def stage_down(self):
        v_step = self.spinBox_ver_step.value()
        self.RE(bps.mvr(self.sample_stage.y, -v_step))
        self.show_image()

    def stage_right(self):
        h_step = self.spinBox_hor_step.value()
        self.RE(bps.mvr(self.sample_stage.x, -h_step))
        self.show_image()

    def stage_left(self):
        h_step = self.spinBox_hor_step.value()
        self.RE(bps.mvr(self.sample_stage.x, h_step))
        self.show_image()


    def park_stage(self):
        # stage_x = self.spinBox_zero_x_rbk.value()
        # stage_y = self.spinBox_zero_y_rbk.value()
        # self.RE(bps.mv(self.sample_stage.x, stage_x))
        # self.RE(bps.mv(self.sample_stage.y, stage_y))
        self.sample_positioner.goto_park()
        self.show_image()


    def update_stage_parking(self):

        ret = question_message_box(self, 'Stage Parking Update',
                                   ('Are you sure you want to update stage parking position?\n' +
                                    'You may need to recalibrate the stage/sample positioning'))
        if ret:
            stage_park_x = self.sample_stage.x.read()[self.sample_stage.x.name]['value']
            stage_park_y = self.sample_stage.y.read()[self.sample_stage.y.name]['value']

            self.spinBox_stage_x.setValue(stage_park_x)
            self.spinBox_stage_y.setValue(stage_park_y)

            self.settings.setValue('stage_park_x', stage_park_x)
            self.settings.setValue('stage_park_y', stage_park_y)

            sample_park_x = self.spinBox_sample_x.value()
            sample_park_y = self.spinBox_sample_y.value()

            self.sample_positioner = SamplePositioner(self.RE,
                                                      self.sample_stage,
                                                      stage_park_x,
                                                      stage_park_y,
                                                      delta_first_holder_x=sample_park_x - stage_park_x,
                                                      delta_first_holder_y=sample_park_y - stage_park_y)

    def update_sample_parking(self):

        ret = question_message_box(self, 'Sample Parking Update',
                                   ('Are you sure you want to update sample parking position?\n' +
                                    'You may need to recalibrate the stage/sample positioning'))
        if ret:
            sample_park_x = self.sample_stage.x.read()[self.sample_stage.x.name]['value']
            sample_park_y = self.sample_stage.y.read()[self.sample_stage.y.name]['value']

            self.spinBox_sample_x.setValue(sample_park_x)
            self.spinBox_sample_y.setValue(sample_park_y)

            self.settings.setValue('sample_park_x', sample_park_x)
            self.settings.setValue('sample_park_y', sample_park_y)

            stage_park_x = self.spinBox_stage_x.value()
            stage_park_y = self.spinBox_stage_y.value()

            self.sample_positioner = SamplePositioner(self.RE,
                                                      self.sample_stage,
                                                      stage_park_x,
                                                      stage_park_y,
                                                      delta_first_holder_x=sample_park_x - stage_park_x,
                                                      delta_first_holder_y=sample_park_y - stage_park_y)

    # def zero_stage(self):
    #     camera_qr = self.camera_dict['camera_sample4']
    #     image_qr = camera_qr.image.image
    #     qr_codes = pzDecode(image_qr)
    #     if qr_codes:
    #         for qr_code in qr_codes:
    #             qr_text = qr_code.data.decode('utf8')
    #             if qr_text == '0 position':
    #                 # self.label_qrcode.setText(qr_text)
    #
    #                 # print('qr code center:',
    #                 #       qr_code.rect.left + qr_code.rect.width/2,
    #                 #       qr_code.rect.top + qr_code.rect.height/2)
    #                 # print('qr code should be moved by these pixels:',
    #                 #       qr_code.rect.left + qr_code.rect.width/2 - self.spinBox_zero_x.value(),
    #                 #       qr_code.rect.top + qr_code.rect.height/2 - self.spinBox_zero_y.value())
    #
    #                 delta_x, delta_y = shift_stage_to_zero( qr_code.rect.left + qr_code.rect.width/2,
    #                                                         qr_code.rect.top + qr_code.rect.height/2,
    #                                                         self.spinBox_zero_x.value(),
    #                                                         self.spinBox_zero_y.value())
    #                 print('moving the giant_xy stage by (', delta_x, ',', delta_y, ')')
    #                 self.RE(bps.mvr(self.sample_stage.x, delta_x))
    #                 self.RE(bps.mvr(self.sample_stage.y, delta_y))
    #                 self.show_image()
    #
    #                 self.sample_x_zero_pos = self.sample_stage.x.read()[self.sample_stage.x.name]['value']
    #                 self.sample_y_zero_pos = self.sample_stage.y.read()[self.sample_stage.y.name]['value']
    #
    #                 self.spinBox_zero_x_rbk.setValue(self.sample_x_zero_pos)
    #                 self.spinBox_zero_y_rbk.setValue(self.sample_y_zero_pos)
    #
    #                 # need to change the (delta_first_holder_x, delta_first_holder_y) upon update
    #                 self.sample_positioner = SamplePositioner(self.sample_x_zero_pos,
    #                                                           self.sample_y_zero_pos,
    #                                                           10.0,  # delta_first_holder_x
    #                                                           10.0,  # delta_first_holder_y
    #                                                           self.RE,
    #                                                           self.sample_stage)
    #
    #                 self.settings.setValue('sample_stage_zero_x_pix', self.spinBox_zero_x.value())
    #                 self.settings.setValue('sample_stage_zero_y_pix', self.spinBox_zero_y.value())
    #                 self.settings.setValue('sample_stage_zero_x_rbk', self.spinBox_zero_x_rbk.value())
    #                 self.settings.setValue('sample_stage_zero_y_rbk', self.spinBox_zero_y_rbk.value())




    def move_to_sample(self):
        self._save_sample_index_settings()
        index_stack = self.spinBox_index_stack.value()
        index_holder = self.spinBox_index_holder.value()
        index_sample = self.spinBox_index_sample.value()
        self.sample_positioner.goto_sample(index_stack, index_holder, index_sample)
        self.RE(bps.sleep(0.1))
        self.show_image()


    def set_qr_roi(self, event):
        if event.button == 3:
            x, y = int(event.xdata), int(event.ydata)
            if self.qr_roi is None:
                self.qr_roi = [(x, y)]
            else:
                if len(self.qr_roi) == 1:
                    self.qr_roi.append((x, y))
                    self.settings.setValue('qr_roi_x1', self.qr_roi[0][0])
                    self.settings.setValue('qr_roi_x2', self.qr_roi[1][0])
                    self.settings.setValue('qr_roi_y1', self.qr_roi[0][1])
                    self.settings.setValue('qr_roi_y2', self.qr_roi[1][1])

                elif len(self.qr_roi) == 2:
                    self.qr_roi = [(x, y)]
        self.show_image()



    def plot_qr_roi(self):
        if self.qr_vlines:
            self.qr_vlines.remove()
        if self.qr_hlines:
            self.qr_hlines.remove()
        try:
            if self.qr_roi_patch:
                self.qr_roi_patch.remove()
        except ValueError:
            pass

        if self.qr_roi:
            xlim = self.figure_qr.ax.get_xlim()
            ylim = self.figure_qr.ax.get_ylim()
            xs = [i[0] for i in self.qr_roi]
            ys = [i[1] for i in self.qr_roi]
            self.qr_vlines = self.figure_qr.ax.vlines(xs, ylim[0], ylim[1], linestyles='--', colors='r', linewidths=0.5)
            self.qr_hlines = self.figure_qr.ax.hlines(ys, xlim[0], xlim[1], linestyles='--', colors='r', linewidths=0.5)
            if len(self.qr_roi) == 2:
                x1, x2 = self.qr_roi[0][0], self.qr_roi[1][0]
                y1, y2 = self.qr_roi[0][1], self.qr_roi[1][1]
                rect = patches.Rectangle((min(x1, x2), min(y1, y2)), abs(x1-x2), abs(y1-y2), linewidth=1, edgecolor='r', facecolor='none')

                self.qr_roi_patch = self.figure_qr.ax.add_patch(rect)




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



    # def set_qr_cursor(self):
    #     color = [0.0, 0.7, 0.0]
    #     y_lo, y_hi = self.figure_qr.ax.get_xlim()
    #     x_lo, x_hi = self.figure_qr.ax.get_ylim()
    #     if self.qr_vc:
    #         self.qr_vc.remove()
    #     if self.qr_hc:
    #         self.qr_hc.remove()
    #
    #     self.qr_vc = self.figure_qr.ax.vlines(self.spinBox_zero_x.value(), x_lo, x_hi, colors=color, linewidths=0.5)
    #     self.qr_hc = self.figure_qr.ax.hlines(self.spinBox_zero_y.value(), y_lo, y_hi, colors=color, linewidths=0.5)
        # self.figure_qr.ax.set_xlim(y_low, y_high)
        # self.figure_qr.ax.set_ylim(x_low, x_high)






