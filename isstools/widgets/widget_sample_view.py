import re
import sys
import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore, QtWidgets
from PyQt5.Qt import QObject
from PyQt5.QtCore import QThread, QSettings
from isstools.elements.qmicroscope import Microscope




ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sample_view.ui')

stage_widget_dict = {
            'pushButton_move_up':
                {'axis': 'y',
                 'direction': -1,
                 'step_size_widget' : 'label_sample_stage_ystep'},
            'pushButton_move_down':
                {'axis': 'y',
                 'direction': 1,
                 'step_size_widget' : 'label_sample_stage_ystep'},
            'pushButton_move_right':
                {'axis': 'x',
                 'direction': 1,
                 'step_size_widget' : 'label_sample_stage_xstep'},
            'pushButton_move_left':
                {'axis': 'x',
                 'direction': -1,
                 'step_size_widget' : 'label_sample_stage_xstep'}}

slider_widget_dict = {
            'verticalSlider_xstep' : {'widget' : 'label_sample_stage_xstep',
                                      'math_params' : {'min_step' : 0.1,
                                                       'max_step' : 50,
                                                       'logarithmic' : True}
                                      },
            'verticalSlider_ystep' : {'widget' : 'label_sample_stage_ystep',
                                      'math_params' : {'min_step' : 0.1,
                                                       'max_step' : 50,
                                                       'logarithmic' : True}
                                      }
                      }

class UISampleView(*uic.loadUiType(ui_path)):


    def __init__(self,
                 sample_stage=None,
                 camera_dict=None,
                 cam1_url='http://10.66.59.30:8083/FfmStream1.jpg',
                 cam2_url='http://10.66.59.30:8082/FfmStream1.jpg',

                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.sample_stage = sample_stage
        self.camera_dict = camera_dict

        self.camera1 = self.camera_dict['camera_sample1']
        self.camera2 = self.camera_dict['camera_sample2']

        self.interaction_mode = 'default'

        self.pushButton_visualize_sample.clicked.connect(self.visualize_sample)
        self.pushButton_visualize_beam.clicked.connect(self.visualize_beam)

        self.spinBox_image_min.valueChanged.connect(self.update_image_limits)
        self.spinBox_image_max.valueChanged.connect(self.update_image_limits)

        self.pushButton_calibration_mode.clicked.connect(self.set_to_calibration_mode)

        self.pushButton_move_up.clicked.connect(self.move_sample_stage)
        self.pushButton_move_down.clicked.connect(self.move_sample_stage)
        self.pushButton_move_left.clicked.connect(self.move_sample_stage)
        self.pushButton_move_right.clicked.connect(self.move_sample_stage)
        self.verticalSlider_xstep.valueChanged.connect(self.update_sample_stage_step)
        self.verticalSlider_ystep.valueChanged.connect(self.update_sample_stage_step)


        self.pushButton_register_calibration_point.clicked.connect(self.register_calibration_point)

        self.cam1_url = cam1_url
        self.sample_cam1 = Microscope(parent = self, mark_direction=1,)
        self.sample_cam1.url = self.cam1_url
        self.sample_cam1.fps = 10

        self.layout_sample_cam1.addWidget(self.sample_cam1)
        self.sample_cam1.acquire(True)

        self.cam2_url = cam2_url
        self.sample_cam2 = Microscope(parent=self, mark_direction=0, )
        self.sample_cam2.url = self.cam2_url
        self.sample_cam2.fps = 10

        self.layout_sample_cam2.addWidget(self.sample_cam2)
        self.sample_cam2.acquire(True)


    def visualize_beam(self):
        exposure = self.doubleSpinBox_exposure_beam.value()
        self.camera1.exp_time.set(exposure)
        self.camera2.exp_time.set(exposure)

    def visualize_sample(self):
        exposure = self.doubleSpinBox_exposure_sample.value()
        self.camera1.exp_time.set(exposure)
        self.camera2.exp_time.set(exposure)


    def update_image_limits(self):
        vmin = self.spinBox_image_min.value()
        vmax = self.spinBox_image_max.value()
        print(vmin, vmax)


    def set_to_calibration_mode(self, state):
        if state:
            self.interaction_mode = 'calibration'
            self.pushButton_register_calibration_point.setEnabled(True)
        else:
            self.interaction_mode = 'default'
            self.pushButton_register_calibration_point.setEnabled(False)

    def register_calibration_point(self):
        pass

    def move_sample_stage(self):
        sender_object = QObject().sender().objectName()
        axis = stage_widget_dict[sender_object]['axis']
        direction = stage_widget_dict[sender_object]['direction']
        step_label_widget = getattr(self, stage_widget_dict[sender_object]['step_size_widget'])
        step = float(step_label_widget.text())
        status = self.sample_stage.mvr({axis : direction * step})
        # status.wait()

    def update_sample_stage_step(self, idx):
        slider_object = QObject().sender()
        slider_dict = slider_widget_dict[slider_object.objectName()]
        step_label_widget = getattr(self, slider_dict['widget'])
        value = self._compute_step_value(slider_object, idx, **slider_dict['math_params'])
        step_label_widget.setText(str(value))

    def _compute_step_value(self, slider_object, idx, min_step=0.1, max_step=50, logarithmic=True):

        n = int(slider_object.maximum() - slider_object.minimum()) + 1
        if logarithmic:
            step_array =  10 ** np.linspace(np.log10(min_step), np.log10(max_step), n)
        else:
            step_array = np.linspace(min_step, max_step, n)
        return np.round(step_array[idx], 2)



