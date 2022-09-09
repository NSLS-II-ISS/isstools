import re
import sys
import numpy as np
import pkg_resources
import math

from PyQt5 import uic, QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QPixmap
from PyQt5.Qt import QObject, Qt
from PyQt5.QtCore import QThread, QSettings
from PyQt5.QtWidgets import QMenu

from ..elements.elements import remove_special_characters

from isstools.elements.qmicroscope import Microscope
from isstools.dialogs import UpdateSampleInfo
from isstools.dialogs.BasicDialogs import message_box, question_message_box


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sample_manager.ui')
coordinate_system_file = pkg_resources.resource_filename('isstools', 'icons/Coordinate system.png')


class UISampleManager(*uic.loadUiType(ui_path)):
    sample_list_changed_signal = QtCore.pyqtSignal()

    def __init__(self,
                 sample_stage=None,
                 camera_dict=None,
                 sample_manager=None,
                 parent=None,
                 cam1_url='http://10.66.59.30:8083/FfmStream1.jpg',
                 cam2_url='http://10.66.59.30:8082/FfmStream1.jpg',
                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.sample_stage = sample_stage
        self.camera_dict = camera_dict
        self.settings = parent.settings

        self.camera1 = self.camera_dict['camera_sample1']
        self.camera2 = self.camera_dict['camera_sample2']

        self.sample_manager = sample_manager
        self.sample_manager.append_list_update_signal(self.sample_list_changed_signal)

        # motion controls and stages

        pixmap = QPixmap(coordinate_system_file)
        self.label_coordinate_system.setPixmap(pixmap)

        self.pushButton_visualize_sample.clicked.connect(self.visualize_sample)
        self.pushButton_visualize_beam.clicked.connect(self.visualize_beam)

        self.spinBox_image_min.valueChanged.connect(self.update_image_limits)
        self.spinBox_image_max.valueChanged.connect(self.update_image_limits)

        self.pushButton_calibration_mode.clicked.connect(self.set_to_calibration_mode)

        self.pushButton_move_up.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_down.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_left.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_right.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_downstream.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_upstream.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_counterclockwise.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_clockwise.clicked.connect(self.move_sample_stage_rel)

        self.verticalSlider_x_step.valueChanged.connect(self.update_sample_stage_step)
        self.verticalSlider_y_step.valueChanged.connect(self.update_sample_stage_step)
        self.verticalSlider_z_step.valueChanged.connect(self.update_sample_stage_step)
        self.verticalSlider_th_step.valueChanged.connect(self.update_sample_stage_step)

        self.pushButton_sample_stage_x_tweak_neg.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_x_tweak_pos.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_y_tweak_neg.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_y_tweak_pos.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_z_tweak_neg.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_z_tweak_pos.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_th_tweak_neg.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_sample_stage_th_tweak_pos.clicked.connect(self.move_sample_stage_rel)

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

        # sample management
        self.update_sample_tree()
        self.sample_list_changed_signal.connect(self.update_sample_tree)

        self.push_import_from_autopilot.clicked.connect(self.get_sample_info_from_autopilot)
        self.push_create_sample.clicked.connect(self.create_new_sample)
        self.push_define_sample_points.clicked.connect(self.define_sample_points)

        self.push_delete_sample.clicked.connect(self.delete_sample)
        self.push_delete_all_samples.clicked.connect(self.delete_all_samples)

        self.push_get_sample_position.clicked.connect(self.get_sample_position)
        self.push_get_sample_position_map_start.clicked.connect(self.get_sample_position)
        self.push_get_sample_position_map_end.clicked.connect(self.get_sample_position)
        self.checkBox_auto_position.toggled.connect(self.enable_user_position_input)
        self.radioButton_sample_map_1D.toggled.connect(self.enable_map_spinboxes)
        self.radioButton_map_steps.toggled.connect(self.enable_map_spinboxes)
        self.enable_user_position_input()
        self.enable_map_spinboxes()

        self.treeWidget_samples.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeWidget_samples.customContextMenuRequested.connect(self.sample_context_menu)

        # cameras and visualization
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

        self.interaction_mode = 'default'
        self.calibration_data = []
        self.pushButton_register_calibration_point.clicked.connect(self.register_calibration_point)
        self.pushButton_process_calibration.clicked.connect(self.process_calibration_data)


    # motion control methods

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

    # sample/sample coordinates management methods

    def enable_user_position_input(self):
        manual_positoioning_flag = not self.checkBox_auto_position.isChecked()
        self.spinBox_sample_x.setEnabled(manual_positoioning_flag)
        self.spinBox_sample_y.setEnabled(manual_positoioning_flag)
        self.spinBox_sample_z.setEnabled(manual_positoioning_flag)
        self.spinBox_sample_th.setEnabled(manual_positoioning_flag)
        self.push_get_sample_position.setEnabled(manual_positoioning_flag)

    def enable_map_spinboxes(self):
        is_1d = self.radioButton_sample_map_1D.isChecked()
        is_steps = self.radioButton_map_steps.isChecked()

        self.spinBox_sample_x_map_steps.setEnabled(is_steps)
        self.spinBox_sample_x_map_spacing.setEnabled((not is_steps))

        self.spinBox_sample_y_map_steps.setEnabled((is_steps) and (not is_1d))
        self.spinBox_sample_y_map_spacing.setEnabled(((not is_steps) and (not is_1d)))


    ''' 
    Dealing with sample positioning and definition
    '''

    def get_sample_position(self):
        sender_object = QObject().sender().objectName()
        x_value = self.sample_stage.x.position
        x_widget = getattr(self, sample_position_widget_dict[sender_object]['x_widget'])
        x_widget.setValue(x_value)

        y_value = self.sample_stage.y.position
        y_widget = getattr(self, sample_position_widget_dict[sender_object]['y_widget'])
        y_widget.setValue(y_value)

        z_value = self.sample_stage.z.position
        z_widget = getattr(self, sample_position_widget_dict[sender_object]['z_widget'])
        z_widget.setValue(z_value)

        th_value = self.sample_stage.th.position
        th_widget = getattr(self, sample_position_widget_dict[sender_object]['th_widget'])
        th_widget.setValue(th_value)

    def _create_list_of_positions(self):
        tab_text = self.tabWidget_sample.tabText(self.tabWidget_sample.currentIndex())
        if tab_text == 'Grid':
            return self._create_grid_of_positions()
        elif tab_text == 'Map':
            return self._create_map_of_positions()
        return

    def _get_stage_coordinates(self, tolerance=0.005):
        self.spinBox_sample_x.setValue(self.sample_stage.x.position)
        self.spinBox_sample_y.setValue(self.sample_stage.y.position)
        self.spinBox_sample_z.setValue(self.sample_stage.z.position)
        # print('!!!!!! WARNING TTH MOTOR WAS DISABLED IN GUI')
        self.spinBox_sample_th.setValue(self.sample_stage.th.position)

    def _create_grid_of_positions(self):
        step_size = self.spinBox_grid_spacing.value()
        n_x = self.spinBox_grid_x_points.value()
        n_y = self.spinBox_grid_y_points.value()
        x_array = np.arange(n_x, dtype=float)
        x_array -= np.median(x_array)
        y_array = np.arange(n_y, dtype=float)
        y_array -= np.median(y_array)
        x_mesh, y_mesh = np.meshgrid(x_array * step_size, y_array * step_size)
        x_mesh = x_mesh.ravel()
        y_mesh = y_mesh.ravel()

        radius = self.spinBox_sample_radius.value()
        if radius > 0:
            r_mesh = np.sqrt(x_mesh ** 2 + y_mesh ** 2)
            x_mesh = x_mesh[r_mesh <= radius]
            y_mesh = y_mesh[r_mesh <= radius]

        if self.checkBox_auto_position.isChecked():
            self._get_stage_coordinates()

        xs = self.spinBox_sample_x.value() + x_mesh
        ys = self.spinBox_sample_y.value() + y_mesh
        z = self.spinBox_sample_z.value()
        th = self.spinBox_sample_th.value()
        npt = xs.size
        positions = []
        for i in range(npt):
            _d = {'x': xs[i],
                  'y': ys[i],
                  'z': z,
                  'th': th}
            positions.append(_d)
        return positions

    def _create_map_of_positions(self):
        x_1 = self.spinBox_sample_x_map_start.value()
        y_1 = self.spinBox_sample_y_map_start.value()
        z_1 = self.spinBox_sample_z_map_start.value()
        th_1 = self.spinBox_sample_th_map_start.value()

        x_2 = self.spinBox_sample_x_map_end.value()
        y_2 = self.spinBox_sample_y_map_end.value()
        z_2 = self.spinBox_sample_z_map_end.value()
        th_2 = self.spinBox_sample_th_map_end.value()

        if self.radioButton_map_steps.isChecked():
            n_x = self.spinBox_sample_x_map_steps.value()
            n_y = self.spinBox_sample_y_map_steps.value()
        elif self.radioButton_map_spacing.isChecked():
            x_spacing = self.spinBox_sample_x_map_spacing.value() / np.cos(np.pi / 4)
            y_spacing = self.spinBox_sample_y_map_spacing.value()
            n_x = int(np.floor(np.abs(x_1 - x_2) / x_spacing))
            n_y = int(np.floor(np.abs(y_1 - y_2) / y_spacing))

        if self.radioButton_sample_map_1D.isChecked():
            xs = np.linspace(x_1, x_2, n_x)
            ys = np.linspace(y_1, y_2, n_x)
        elif self.radioButton_sample_map_2D.isChecked():
            _x = np.linspace(x_1, x_2, n_x)
            _y = np.linspace(y_1, y_2, n_y)
            xs, ys = np.meshgrid(np.linspace(x_1, x_2, n_x),
                                 np.linspace(y_1, y_2, n_y))
            xs = xs.ravel()
            ys = ys.ravel()

        npt = xs.size
        positions = []  #
        for i in range(npt):
            _d = {'x': xs[i],
                  'y': ys[i],
                  'z': np.interp(xs[i], [x_1, x_2], [z_1, z_2]),
                  'th': np.interp(xs[i], [x_1, x_2], [th_1, th_2])}
            positions.append(_d)
        return positions

    '''
    Dealing with making qt items of all sorts
    '''

    def _make_item(self, parent, item_str, index, kind='', force_unchecked=False, checkable=True):
        item = QtWidgets.QTreeWidgetItem(parent)
        item.setText(0, item_str)
        item.setExpanded(True)
        if checkable:
            item.setFlags(item.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        if force_unchecked:
            item.setCheckState(0, Qt.Unchecked)
        item.kind = kind
        item.index = index
        return item

    def _make_sample_item(self, sample_str, sample_index):
        return self._make_item(self.treeWidget_samples, sample_str, sample_index, kind='sample', force_unchecked=False, checkable=False)

    def _make_sample_point_item(self, sample_item, point_str, point_index, is_exposed):
        point_item = self._make_item(sample_item, point_str, point_index, kind='sample_point', force_unchecked=False, checkable=False)
        point_item.is_exposed = is_exposed
        if is_exposed:
            point_item.setForeground(0, QtGui.QColor('red'))

    '''
    Dealing with samples
    '''
    def update_sample_tree(self):
        self.treeWidget_samples.clear()
        for i, sample in enumerate(self.sample_manager.samples):
            name = sample.name
            npts = sample.number_of_points
            npts_fresh = sample.number_of_unexposed_points
            sample_str = f"{name} ({npts_fresh}/{npts})"
            sample_item = self._make_sample_item(sample_str, i)
            # self.treeWidget_samples.addItem(sample_item)
            for j in range(npts):
                point_idx = sample.index_position_index(j)
                point_str = sample.index_coordinate_str(j)
                point_exposed = sample.index_exposed(j)
                # point_str = ' '.join([(f"{key}={value : 0.2f}") for key,value in coord_dict.items()])
                point_str = f'{point_idx + 1:3d} - {point_str}'
                self._make_sample_point_item(sample_item, point_str, j, point_exposed)

    def create_new_sample(self):
        sample_name = self.lineEdit_sample_name.text()
        if (sample_name == '') or (sample_name.isspace()):
            message_box('Warning', 'Sample name is empty')
            return
        sample_name = remove_special_characters(sample_name)
        sample_comment = self.lineEdit_sample_comment.text()
        # positions = self._create_list_of_positions()
        self.sample_manager.add_new_sample(sample_name, sample_comment, [])


    def define_sample_points(self):
        index_list = self.treeWidget_samples.selectedIndexes()
        if len(index_list) == 1:
            index = index_list[0]
            item = self.treeWidget_samples.itemFromIndex(index)
            if item.kind == 'sample':
                sample_index = item.index
                positions = self._create_list_of_positions()
                self.sample_manager.add_points_to_sample_at_index(sample_index, positions)




    def get_sample_info_from_autopilot(self):
        try:
            df = self.parent_gui.widget_autopilot.sample_df
            str_to_parse = self.lineEdit_sample_name.text()
            if '_' in str_to_parse:
                try:
                    n_holder, n_sample = [int(i) for i in str_to_parse.split('_')]
                    select_holders = df['Holder ID'].apply(lambda x: int(x)).values == n_holder
                    select_sample_n = df['Sample #'].apply(lambda x: int(x)).values == n_sample
                    line_number = np.where(select_holders & select_sample_n)[0][0]
                except:
                    pass
            else:
                line_number = int(self.lineEdit_sample_name.text()) - 1  # pandas is confusing
            name = df.iloc[line_number]['Name']
            comment = df.iloc[line_number]['Composition'] + ' ' + df.iloc[line_number]['Comment']
            name = name.replace('/', '_')
            self.lineEdit_sample_name.setText(name)
            self.lineEdit_sample_comment.setText(comment)
        except:
            message_box('Error', 'Autopilot table is not defined')

    def delete_sample(self):
        index_dict = {}

        index_list = self.treeWidget_samples.selectedIndexes()
        for index in index_list:
            item = self.treeWidget_samples.itemFromIndex(index)
            if item.kind == 'sample':
                sample_index = item.index
                point_index_list = [item.child(i).index for i in range(item.childCount())]
            elif item.kind == 'sample_point':
                sample_index = item.parent().index
                point_index_list = [item.index]
            if sample_index in index_dict.keys():
                index_dict[sample_index].extend(point_index_list)
            else:
                index_dict[sample_index] = point_index_list
        self.sample_manager.delete_samples_with_index_dict(index_dict)



    def delete_all_samples(self):
        self.sample_manager.reset()

    '''
    Sample Context menu
    '''

    def sample_context_menu(self, QPos):
        menu = QMenu()
        modify = menu.addAction("&Modify")
        move_to_sample = menu.addAction("Mo&ve to sample")
        set_as_exposed = menu.addAction("Set as exposed")
        set_as_unexposed = menu.addAction("Set as unexposed")
        parentPosition = self.treeWidget_samples.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition + QPos)
        action = menu.exec_()
        if action == modify:
            self.modify_item()
        elif action == move_to_sample:
            self.move_to_sample()
        elif action == set_as_exposed:
            self.set_as_exposed_selected_samples()
        elif action == set_as_unexposed:
            self.set_as_exposed_selected_samples(exposed=False)

    def modify_item(self):
        sender_object = QObject().sender()
        selection = sender_object.selectedIndexes()
        if len(selection) == 1:
            index = sender_object.currentIndex()
            if sender_object == self.treeWidget_samples:
                item = sender_object.itemFromIndex(index)
            else:
                return

            if item.kind == 'sample':
                sample_index = item.index
                sample = self.sample_manager.sample_at_index(sample_index)
                dlg = UpdateSampleInfo.UpdateSampleInfo(sample.name, sample.comment)
                if dlg.exec_():
                    new_name, new_comment = dlg.getValues()
                    self.sample_manager.update_sample_at_index(sample_index, new_name, new_comment)
            elif item.kind == 'sample_point':
                sample_index = item.parent().index
                sample_name = self.sample_manager.sample_name_at_index(sample_index)
                sample_point_index = item.index
                coordinate_dict = self.sample_manager.sample_coordinate_dict_at_index(sample_index, sample_point_index)
                dlg = UpdateSampleInfo.UpdateSamplePointInfo(sample_name, **coordinate_dict)
                if dlg.exec_():
                    new_coordinate_dict = dlg.getValues()
                    self.sample_manager.update_sample_coordinates_at_index(sample_index, sample_point_index,
                                                                           new_coordinate_dict)

    def move_to_sample(self):
        sender_object = QObject().sender()
        selection = sender_object.selectedIndexes()
        if len(selection) == 1:
            index = sender_object.currentIndex()
            item = sender_object.itemFromIndex(index)
            if item.kind == 'sample_point':
                sample_index = item.parent().index
                sample_point_index = item.index
                name = self.sample_manager.sample_name_at_index(sample_index)
                coordinate_dict = self.sample_manager.sample_coordinate_dict_at_index(sample_index, sample_point_index)
                ret = question_message_box(self, 'Moving to sample',
                                           f'Moving to sample {name} at \n' +
                                           f'x = {coordinate_dict["x"]:.2f}\n' +
                                           f'y = {coordinate_dict["y"]:.2f}\n' +
                                           f'z = {coordinate_dict["z"]:.2f}\n' +
                                           f'th = {coordinate_dict["th"]:.2f}\n' +
                                           'Are you sure?')
                if ret:
                    for axis, position in coordinate_dict.items():
                        plan = 'move_motor_plan'
                        motor = getattr(self.sample_stage, axis)
                        plan_kwargs = {'motor_attr': motor.name, 'based_on': 'object_name', 'position': position}
                        self.plan_processor.add_plan_and_run_if_idle(plan, plan_kwargs)

            else:
                message_box('Warning', 'Please select sample point')
        elif len(selection) > 1:
            message_box('Warning', 'Cannot move to multiple sample positions. Select one sample!')

    def set_as_exposed_selected_samples(self, exposed=True):
        index_dict = {}

        index_list = self.treeWidget_samples.selectedIndexes()
        for index in index_list:
            item = self.treeWidget_samples.itemFromIndex(index)
            if item.kind == 'sample':
                sample_index = item.index
                point_index_list = [item.child(i).index for i in range(item.childCount())]
            elif item.kind == 'sample_point':
                sample_index = item.parent().index
                point_index_list = [item.index]
            if sample_index in index_dict.keys():
                index_dict[sample_index].extend(point_index_list)
            else:
                index_dict[sample_index] = point_index_list
        self.sample_manager.set_as_exposed_with_index_dict(index_dict, exposed=exposed)


    # sample visualization methods

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
        output_dict = self.sample_stage.positions('x', 'y', prefix='sample_stage')
        output_dict['cam1'] = self.sample_cam1.calibration_polygon.coordinate_list
        output_dict['cam2'] = self.sample_cam2.calibration_polygon.coordinate_list
        self.calibration_data.append(output_dict)

    def process_calibration_data(self):
        pass





stage_button_widget_dict = {
            # pushbuttons
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
            'pushButton_move_downstream':
                {'axis': 'z',
                 'direction': -1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_z_step'},
            'pushButton_move_upstream':
                {'axis': 'z',
                 'direction': 1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_z_step'},
            'pushButton_move_clockwise':
                {'axis': 'th',
                 'direction': -1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_th_step'},
            'pushButton_move_counterclockwise':
                {'axis': 'th',
                 'direction': 1,
                 'step_size_widget': 'doubleSpinBox_sample_stage_y_step'},
            # tweak pushbuttons
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
                                      },
            'verticalSlider_z_step' : {'widget' : 'doubleSpinBox_sample_stage_z_step',
                                                  'math_params' : {'min_step' : 0.1,
                                                                   'max_step' : 50,
                                                                   'logarithmic' : True}
                                      },
            'verticalSlider_th_step' : {'widget' : 'doubleSpinBox_sample_stage_th_step',
                                                  'math_params' : {'min_step' : 0.1,
                                                                   'max_step' : 50,
                                                                   'logarithmic' : True}
                                      },
                      }

sample_position_widget_dict = {
            'push_get_sample_position':
                {'x_widget': 'spinBox_sample_x',
                 'y_widget': 'spinBox_sample_y',
                 'z_widget': 'spinBox_sample_z',
                 'th_widget': 'spinBox_sample_th',
                 },
            'push_get_sample_position_map_start':
                {'x_widget': 'spinBox_sample_x_map_start',
                 'y_widget': 'spinBox_sample_y_map_start',
                 'z_widget': 'spinBox_sample_z_map_start',
                 'th_widget': 'spinBox_sample_th_map_start',
                 },
            'push_get_sample_position_map_end':
                {'x_widget': 'spinBox_sample_x_map_end',
                 'y_widget': 'spinBox_sample_y_map_end',
                 'z_widget': 'spinBox_sample_z_map_end',
                 'th_widget': 'spinBox_sample_th_map_end'},
        }



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


# x = np.linspace(0, 99, 100)
# y_steps = [0.1, 1, 10, 50]
#
#





