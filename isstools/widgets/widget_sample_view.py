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

stage_button_widget_dict = {
            'pushButton_move_right':
                {'axis': 'x',
                 'direction': 1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_x_step'},
            'pushButton_move_left':
                {'axis': 'x',
                 'direction': -1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_x_step'},
            'pushButton_move_up':
                {'axis': 'y',
                 'direction': -1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_y_step'},
            'pushButton_move_down':
                {'axis': 'y',
                 'direction': 1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_y_step'},
            'pushButton_sample_stage_x_tweak_neg':
                {'axis': 'x',
                 'direction': -1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_x_step'},
            'pushButton_sample_stage_x_tweak_pos':
                {'axis': 'x',
                 'direction': 1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_x_step'},
            'pushButton_sample_stage_y_tweak_neg':
                {'axis': 'y',
                 'direction': -1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_y_step'},
            'pushButton_sample_stage_y_tweak_pos':
                {'axis': 'y',
                 'direction': 1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_y_step'},
            'pushButton_sample_stage_z_tweak_neg':
                {'axis': 'z',
                 'direction': -1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_z_step'},
            'pushButton_sample_stage_z_tweak_pos':
                {'axis': 'z',
                 'direction': 1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_z_step'},
            'pushButton_sample_stage_th_tweak_neg':
                {'axis': 'th',
                 'direction': -1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_th_step'},
            'pushButton_sample_stage_th_tweak_pos':
                {'axis': 'th',
                 'direction': 1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_th_step'},
            'lineEdit_sample_stage_x_position_sp':
                {'axis': 'x'},
            'lineEdit_sample_stage_y_position_sp':
                {'axis': 'y'},
            'lineEdit_sample_stage_z_position_sp':
                {'axis': 'z'},
            'lineEdit_sample_stage_th_position_sp':
                {'axis': 'th'},
            }

stage_lineEdit_widget_dict = {'sample_stage_x' :                {'widget' : 'lineEdit_sample_stage_x_position_rb', 'pv' : 'x.user_readback'},
                              'sample_stage_x_user_setpoint' :  {'widget' : 'lineEdit_sample_stage_x_position_sp', 'pv' : 'x.user_setpoint'},
                              'sample_stage_y':                 {'widget' : 'lineEdit_sample_stage_y_position_rb', 'pv' : 'y.user_readback'},
                              'sample_stage_y_user_setpoint':   {'widget' : 'lineEdit_sample_stage_y_position_sp', 'pv' : 'y.user_setpoint'},
                              'sample_stage_z':                 {'widget' : 'lineEdit_sample_stage_z_position_rb', 'pv' : 'z.user_readback'},
                              'sample_stage_z_user_setpoint':   {'widget' : 'lineEdit_sample_stage_z_position_sp', 'pv' : 'z.user_setpoint'},
                              'sample_stage_th':                {'widget' : 'lineEdit_sample_stage_th_position_rb', 'pv' : 'th.user_readback'},
                              'sample_stage_th_user_setpoint':  {'widget' : 'lineEdit_sample_stage_th_position_sp', 'pv' : 'th.user_setpoint'}}

slider_widget_dict = {
            'verticalSlider_x_step' : {'widget' : 'doubleSpinBox_sample_stage_x_step',
                                      'math_params' : {'min_step' : 0.1,
                                                       'max_step' : 50,
                                                       'logarithmic' : True}
                                      },
            'verticalSlider_y_step' : {'widget' : 'doubleSpinBox_sample_stage_y_step',
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

        self.pushButton_move_up.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_down.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_left.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_right.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_x_tweak_neg.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_x_tweak_pos.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_y_tweak_neg.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_y_tweak_pos.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_z_tweak_neg.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_z_tweak_pos.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_th_tweak_neg.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_th_tweak_pos.clicked.connect(self.move_sample_stage_rel)

        self.verticalSlider_x_step.valueChanged.connect(self.update_sample_stage_step)
        self.verticalSlider_y_step.valueChanged.connect(self.update_sample_stage_step)

        # self.update_lineEdit_sample_stage_x_position_rb(self.sample_stage.x.position, -1e4)

        for k, v in stage_lineEdit_widget_dict.items():
            pv = v['pv']
            self.update_sample_stage_lineEdits(getattr(self.sample_stage, pv).value, -1e4, obj_name=k)

        self.sample_stage.x.user_readback.subscribe(self.update_sample_stage_lineEdits)
        self.sample_stage.x.user_setpoint.subscribe(self.update_sample_stage_lineEdits)
        self.sample_stage.y.user_readback.subscribe(self.update_sample_stage_lineEdits)
        self.sample_stage.y.user_setpoint.subscribe(self.update_sample_stage_lineEdits)
        self.sample_stage.z.user_readback.subscribe(self.update_sample_stage_lineEdits)
        self.sample_stage.z.user_setpoint.subscribe(self.update_sample_stage_lineEdits)
        self.sample_stage.th.user_readback.subscribe(self.update_sample_stage_lineEdits)
        self.sample_stage.th.user_setpoint.subscribe(self.update_sample_stage_lineEdits)

        self.lineEdit_sample_stage_x_position_sp.returnPressed.connect(self.move_sample_stage_abs)
        self.lineEdit_sample_stage_y_position_sp.returnPressed.connect(self.move_sample_stage_abs)
        self.lineEdit_sample_stage_z_position_sp.returnPressed.connect(self.move_sample_stage_abs)
        self.lineEdit_sample_stage_th_position_sp.returnPressed.connect(self.move_sample_stage_abs)

        self.pushButton_register_calibration_point.clicked.connect(self.register_calibration_point)
        self.pushButton_process_calibration.clicked.connect(self.process_calibration_data)

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

        self.sample_cam1.polygonDrawingSignal.connect(self.sample_cam2.calibration_polygon.append)
        self.sample_cam2.polygonDrawingSignal.connect(self.sample_cam1.calibration_polygon.append)

        self.calibration_data = []


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

    def move_sample_stage_rel(self):
        sender_object = QObject().sender().objectName()
        axis = stage_button_widget_dict[sender_object]['axis']
        # print(f'signal emitted')
        direction = stage_button_widget_dict[sender_object]['direction']
        step_label_widget = getattr(self, stage_button_widget_dict[sender_object]['step_size_widget'])
        step = float(step_label_widget.value())
        self.sample_stage.mvr({axis: direction * step}, wait=False)

    def move_sample_stage_abs(self):
        sender_object_name = QObject().sender().objectName()
        pos_widget = getattr(self, sender_object_name)
        try:
            new_pos = float(pos_widget.text())
            axis = stage_button_widget_dict[sender_object_name]['axis']
            self.sample_stage.mv({axis: new_pos})
        except:
            print('position must be float!')

    def update_sample_stage_step(self, idx):
        slider_object = QObject().sender()
        slider_dict = slider_widget_dict[slider_object.objectName()]
        step_label_widget = getattr(self, slider_dict['widget'])
        value = self._compute_step_value(slider_object, idx, **slider_dict['math_params'])
        # step_label_widget.setText(str(value))
        step_label_widget.setValue(float(value))

    def _compute_step_value(self, slider_object, idx, min_step=0.1, max_step=50, logarithmic=True):
        n = int(slider_object.maximum() - slider_object.minimum()) + 1
        if logarithmic:
            step_array =  10 ** np.linspace(np.log10(min_step), np.log10(max_step), n)
        else:
            step_array = np.linspace(min_step, max_step, n)
        return np.round(step_array[idx], 2)

    def update_sample_stage_lineEdits(self, value, old_value, atol=5e-3, obj_name=None, **kwargs):
        if obj_name is None:
            obj_name = kwargs['obj'].name

        if not np.isclose(value, old_value, atol=atol):
            # print(f'{value=}, {old_value=}, {obj_name=}')
            widget = getattr(self, stage_lineEdit_widget_dict[obj_name]['widget'])
            widget.setText(f'{value:0.3f}')


    def set_to_calibration_mode(self, state):
        if state:
            self.interaction_mode = 'calibration'
            self.pushButton_register_calibration_point.setEnabled(True)
        else:
            self.interaction_mode = 'default'
            self.pushButton_register_calibration_point.setEnabled(False)

    def register_calibration_point(self):
        output_dict = self.sample_stage.positions('x', 'y', prefix='sample_stage')
        output_dict['cam1'] = self.sample_cam1.calibration_polygon.coordinate_list
        output_dict['cam2'] = self.sample_cam2.calibration_polygon.coordinate_list
        self.calibration_data.append(output_dict)

    def process_calibration_data(self):
        pass

    # def update_sample_stage_lineEdits_sp(self, value, old_value, atol=5e-3, suffix='sp', **kwargs):
        # self.update_sample_stage_lineEdits(self, value, old_value, atol=atol, suffix=suffix, **kwargs)

    # def update_sample_stage_lineEdits(self, value, old_value, atol=5e-3, suffix='rb', **kwargs):
        # obj_name = kwargs['obj'].name
        # print(f'{value=}, {old_value=}, {kwargs=}')
        # if not np.isclose(value, old_value, atol=atol):
        #
        #
        #     widget = getattr(self, stage_lineEdit_widget_dict[obj_name]['widget_' + suffix])
        #     widget.setText(f'{value:0.3f}')





class CamCalibration:

    def __init__(self, cdata):
        self.cdata = cdata

        self.process_cdata(cdata)

    def process_cdata(self, cdata):
        points = []
        coords = []
        n_entries = len(cdata)

        for i_dict in cdata:
            points.append(i_dict['cam1'])
            coords.append([i_dict['sample_stage_x'], i_dict['sample_stage_y']])

        points = np.array(points)
        coords = np.array(coords)

        points_mid = points[:-1, :, :] + np.diff(points, axis=0)

        # points_delta = np.diff(points, axis=0)
        points_delta = np.mean(np.diff(points, axis=0), axis=1)
        coords_delta = np.diff(coords, axis=0)

        # points_delta_mean = np.mean(points_delta, axis=(0, 1))
        # coords_delta_mean = np.mean(coords_delta, axis=0)

        self.A_xy2px, _, _, _ = np.linalg.lstsq(coords_delta, points_delta[:, 0], rcond=-1)
        self.A_xy2py, _, _, _ = np.linalg.lstsq(coords_delta, points_delta[:, 1], rcond=-1)


# cc = CamCalibration(x.calibration_data)

# dx = self.A_xy2px @ [1, 0]
# self.A_xy2px = np.array([-7.91148978e+00,  8.63858905e-04])
# self.A_xy2py = np.array([ -1.7081848 , -12.94478738])
