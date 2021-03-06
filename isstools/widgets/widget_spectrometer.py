import pkg_resources
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QThread, QSettings
from PyQt5.Qt import  QObject
from bluesky.callbacks import LivePlot
from bluesky.callbacks.mpl_plotting import LiveScatter
import numpy as np

from isstools.dialogs import (UpdatePiezoDialog, MoveMotorDialog)
from isstools.dialogs.BasicDialogs import question_message_box
from isstools.elements.figure_update import update_figure_with_colorbar, update_figure, setup_figure
from isstools.elements.transformations import  range_step_2_start_stop_nsteps


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer.ui')

class UISpectrometer(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE,
                 # hhm,
                 db,
                 detector_dictionary,
                 motor_dictionary,
                 aux_plan_funcs,
                 # ic_amplifiers,
                 service_plan_funcs,
                 # tune_elements,
                 # shutter_dictionary,
                 # parent_gui,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.RE = RE
        self.db = db
        self.vmax = None
        self.pil_image = None
        self.detector_dictionary = detector_dictionary
        self.pilatus = detector_dictionary['Pilatus 100k']['device']

        self.aux_plan_funcs = aux_plan_funcs
        self.motor_dictionary = motor_dictionary
        self.service_plan_funcs = service_plan_funcs
        # self.parent_gui = parent_gui
        self.last_motor_used = None
        self.push_1D_scan.clicked.connect(self.run_pcl_scan)
        self.push_xy_scan.clicked.connect(self.run_2dscan)
        self.push_py_scan.clicked.connect(self.run_2dscan)
        self.push_scan.clicked.connect(self.run_scan)
        self.push_single_shot.clicked.connect(self.single_shot)

        self.det_list = list(detector_dictionary.keys())
        self.comboBox_detectors.addItems(self.det_list)
        self.comboBox_detectors.currentIndexChanged.connect(self.detector_selected)
        self.detector_selected()

        self.motor_list = [self.motor_dictionary[motor]['description'] for motor in self.motor_dictionary
                         if ('group' in  self.motor_dictionary[motor].keys())
                         and (self.motor_dictionary[motor]['group']=='spectrometer')]

        self.comboBox_motors.addItems(self.motor_list)

        self.figure_scan, self.canvas_scan,self.toolbar_scan = setup_figure(self, self.layout_plot_scan)
        self.figure_integ, self.canvas_integ,self.toolbar_integ = setup_figure(self, self.layout_plot_integ)

        self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
        self.spinBox_image_max.valueChanged.connect(self.rescale_image)
        self.spinBox_image_min.valueChanged.connect(self.rescale_image)



        # self.roi_dict = {'roi1': {'radioButton': self.radioButton_roi1,
        #                           'x':self.pilatus.roi}}

    def run_scan(self):

        self.canvas_scan.mpl_disconnect(self.cid_scan)
        update_figure([self.figure_scan.ax], self.toolbar_scan,self.canvas_scan)
        self.figure_scan.ax.set_aspect('auto')
        for motor in self.motor_dictionary:
            if self.comboBox_motors.currentText() == self.motor_dictionary[motor]['description']:
                self.motor = self.motor_dictionary[motor]['object']
                break

        rel_start, rel_stop, num_steps =  range_step_2_start_stop_nsteps(
                            self.doubleSpinBox_range.value(),
                            self.doubleSpinBox_step.value())

        uid_list = self.RE(self.aux_plan_funcs['general_scan']([self.detector],
                                                               self.motor,
                                                               rel_start,
                                                               rel_stop,
                                                               num_steps, ),
                           LivePlot(self.channel,  self.motor.name, ax=self.figure_scan.ax))

        self.canvas_scan.draw_idle()
        self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
        self.last_motor_used = self.motor


    def run_pcl_scan(self, **kwargs):
        self.canvas_scan.mpl_disconnect(self.cid_scan)
        self.figure_scan.ax.set_aspect('auto')
        detector_name = self.comboBox_detectors.currentText()
        detector = self.detector_dictionary[detector_name]['device']
        channels = self.detector_dictionary[detector_name]['channels']
        channel = channels[self.comboBox_channels.currentIndex()]
        update_figure([self.figure_scan.ax], self.toolbar_scan, self.canvas_scan)

        motor_suffix = self.comboBox__pcl_motors.currentText().split(' ')[-1]
        motor_name = f'six_axes_stage_{motor_suffix}'
        self.motor = self.motor_dictionary[motor_name]['object']

        range = getattr(self, f'doubleSpinBox_range_{motor_suffix}').value()
        step = getattr(self, f'doubleSpinBox_step_{motor_suffix}').value()
        ''
        rel_start = -float(range) / 2
        rel_stop = float(range) / 2
        num_steps = int(round(range / float(step))) + 1

        uid_list = self.RE(self.aux_plan_funcs['general_scan']([detector],
                                                               self.motor,
                                                               rel_start,
                                                               rel_stop,
                                                               num_steps, ),
                           LivePlot(channel, self.motor.name, ax=self.figure_scan.ax))

        self.figure_scan.tight_layout()
        self.canvas_scan.draw_idle()
        self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
        self.last_motor_used = self.motor



    def run_2dscan(self):
        self.figure_scan.ax.set_aspect('auto')
        sender = QObject()
        sender_object = sender.sender().objectName()
        if 'xy' in sender_object:
            m1 = 'x'
            m2 = 'y'
        elif 'py' in sender_object:
            m1 = 'pitch'
            m2 = 'yaw'
        
        self.canvas_scan.mpl_disconnect(self.cid_scan)
        detector_name = self.comboBox_detectors.currentText()
        detector = self.detector_dictionary[detector_name]['device']
        channels = self.detector_dictionary[detector_name]['channels']
        channel = channels[self.comboBox_channels.currentIndex()]

        motor1 = self.motor_dictionary[f'six_axes_stage_{m1}']['object']
        motor2 = self.motor_dictionary[f'six_axes_stage_{m2}']['object']
        m1_pos = motor1.read()[motor1.name]['value']
        m2_pos = motor2.read()[motor2.name]['value']

        motor1_range = getattr(self, f'doubleSpinBox_range_{m1}').value()
        motor2_range = getattr(self, f'doubleSpinBox_range_{m2}').value()

        motor1_step = getattr(self, f'doubleSpinBox_step_{m1}').value()
        motor2_step = getattr(self, f'doubleSpinBox_step_{m2}').value()

        motor1_nsteps = int(round(motor1_range / float(motor1_step))) + 1
        motor2_nsteps = int(round(motor2_range / float(motor2_step))) + 1

        #self.figure_scan.clf()
        update_figure_with_colorbar([self.figure_scan.ax], self.toolbar_scan, self.canvas_scan,self.figure_scan)

        plan = self.aux_plan_funcs['general_spiral_scan']([detector],
                                                          motor1=motor1, motor2=motor2,
                                                          motor1_range=motor1_range, motor2_range=motor2_range,
                                                          motor1_nsteps=motor1_nsteps, motor2_nsteps=motor2_nsteps)

        # xlim =

        live_scatter = LiveScatter(motor1.name, motor2.name, channel, ax=self.figure_scan.ax,
                                   xlim=(m1_pos - motor1_range / 2, m1_pos + motor1_range / 2),
                                   ylim=(m2_pos - motor2_range / 2, m2_pos + motor2_range / 2),
                                   **{'s' : 100, 'marker' : 's','cmap': 'nipy_spectral'})
        # live_scatter = LivePlot(channel, self.motor.name, ax=self.figure_scan.ax)

        uid = self.RE(plan, live_scatter)
        self.figure_scan.ax.set_aspect('auto')
        self.figure_scan.tight_layout()
        self.canvas_scan.draw_idle()
        self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
        self.last_motor_used = [motor1, motor2]

    def single_shot(self):
        plan = self.service_plan_funcs['pil_count']
        self.pilatus.cam.acquire_time.set(self.doubleSpinBox_exposure.value())
        uid = self.RE(plan())
        self.pil_image = np.array(list(self.db[uid][0].data(field='pil100k_image')))[0]
        self.pil_image = self.pil_image[::-1, :]
        max_image = self.pil_image.max()
        min_image = self.pil_image.min()
        self.label_max_count.setText(f'Max counts: {max_image}')
        if self.vmax is None:
            self.vmax = max_image
            self.vmax = min_image
            self.spinBox_image_max.setValue(max_image)
            self.spinBox_image_min.setValue(min_image)
        self.figure_scan.ax.imshow(self.pil_image, cmap ='nipy_spectral', vmin = self.vmin, vmax=self.vmax, origin='bottom')
        self.canvas_scan.draw_idle()

    def rescale_image(self):
        if self.pil_image is not None:
            self.vmax = self.spinBox_image_max.value()
            self.vmin = self.spinBox_image_min.value()
            self.figure_scan.ax.imshow(self.pil_image, cmap ='nipy_spectral', vmin = self.vmin, vmax=self.vmax, origin='bottom')
            self.canvas_scan.draw_idle()


    def getX_scan(self, event):
        print(f'Event {event.button}')
        if event.button == 3:
            if self.last_motor_used:
                if type(self.last_motor_used) == list:
                    motor1, motor2 = self.last_motor_used
                    dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=motor1,
                                                          parent=self.canvas_scan)
                    if dlg.exec_():
                        pass

                    dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.ydata, motor=motor2,
                                                          parent=self.canvas_scan)
                    if dlg.exec_():
                        pass

                else:
                    dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=self.last_motor_used,
                                                          parent=self.canvas_scan)
                    if dlg.exec_():
                        pass

    def detector_selected(self):
        self.comboBox_channels.clear()
        detector = self.comboBox_detectors.currentText()
        self.comboBox_channels.addItems(self.detector_dictionary[detector]['channels'])

        detector_name = self.comboBox_detectors.currentText()
        self.detector = self.detector_dictionary[detector_name]['device']
        channels = self.detector_dictionary[detector_name]['channels']
        self.channel = channels[self.comboBox_channels.currentIndex()]





