import inspect
import re

import pkg_resources
import numpy as np
from PyQt5 import uic, QtGui, QtCore, QtWidgets

from isstools.dialogs.BasicDialogs import message_box
from isstools.elements import elements
from isstools.trajectory.trajectory import trajectory_manager
from isstools.elements.parameter_handler import parse_plan_parameters, return_parameters_from_widget
from PyQt5.Qt import QObject


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_batch_manual.ui')

path_icon_experiment = pkg_resources.resource_filename('isstools', 'icons/experiment.png')
icon_experiment = QtGui.QIcon()
icon_experiment.addPixmap(QtGui.QPixmap(path_icon_experiment), QtGui.QIcon.Normal, QtGui.QIcon.Off)

path_icon_sample = pkg_resources.resource_filename('isstools', 'icons/sample.png')
icon_sample = QtGui.QIcon()
icon_sample.addPixmap(QtGui.QPixmap(path_icon_sample), QtGui.QIcon.Normal, QtGui.QIcon.Off)

path_icon_scan = pkg_resources.resource_filename('isstools', 'icons/scan.png')
icon_scan = QtGui.QIcon()
icon_scan.addPixmap(QtGui.QPixmap(path_icon_scan), QtGui.QIcon.Normal, QtGui.QIcon.Off)

path_icon_service = pkg_resources.resource_filename('isstools', 'icons/service.png')
icon_service = QtGui.QIcon()
icon_service.addPixmap(QtGui.QPixmap(path_icon_service), QtGui.QIcon.Normal, QtGui.QIcon.Off)



class UIBatchManual(*uic.loadUiType(ui_path)):
    def __init__(self,
                 plan_funcs,
                 service_plan_funcs,
                 hhm,
                 sample_stage = None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.plan_funcs = plan_funcs
        self.service_plan_funcs = service_plan_funcs
        self.plan_funcs_names = plan_funcs.keys()
        self.service_plan_funcs_names = service_plan_funcs.keys()
        self.sample_stage = sample_stage
        self.batch_mode_uids = []
        self.traj_manager = trajectory_manager(hhm)
        self.treeView_batch = elements.TreeView(self, 'all')
        self.treeView_batch.acceptDrops()
        self.gridLayout_batch_definition.addWidget(self.treeView_batch, 0, 0)

        # sample functions
        self.push_create_batch_experiment.clicked.connect(self.create_batch_experiment)
        self.model_batch = QtGui.QStandardItemModel(self)
        self.treeView_batch.header().hide()

        
        '''
        WIP add horizontal scrollbar
        self.treeView_batch.header().horizontalScrollBar()
        '''
        
        self.treeView_batch.setModel(self.model_batch)
        self.model_samples = QtGui.QStandardItemModel(self)
        self.push_create_sample.clicked.connect(self.create_new_sample)
        self.push_delete_sample.clicked.connect(self.delete_sample)
        self.push_get_sample_position.clicked.connect(self.get_sample_position)
        self.push_get_sample_position_map_start.clicked.connect(self.get_sample_position)
        self.push_get_sample_position_map_end.clicked.connect(self.get_sample_position)

        self.listView_samples.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)


        self.model_scans = QtGui.QStandardItemModel(self)
        self.push_create_scan.clicked.connect(self.create_new_scan)
        self.push_delete_scan.clicked.connect(self.delete_scan)
        self.listView_scans.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)

        self.push_batch_delete.clicked.connect(self.delete_batch_element)
        self.push_batch_info.clicked.connect(self.batch_info)
        self.push_create_measurement.clicked.connect(self.create_measurement)
        self.push_create_service.clicked.connect(self.create_service)
        self.push_create_map.clicked.connect(self.create_map)

        self.comboBox_scans.addItems(self.plan_funcs_names)
        self.comboBox_service_scan.addItems(self.service_plan_funcs_names)
        self.comboBox_service_scan.currentIndexChanged.connect(self.populate_parameter_grid)
        self.push_update_traj_list.clicked.connect(self.update_batch_traj)
        self.last_lut = 0

        self.service_parameter_values = []
        self.service_parameter_descriptions = []
        self.populate_parameter_grid(0)
        self.update_batch_traj()

    '''
    Dealing with batch experiemnts
    '''

    def create_batch_experiment(self):
        parent = self.model_batch.invisibleRootItem()
        batch_experiment = 'Batch experiment "{}" repeat {} times                                      '\
            .format(self.lineEdit_batch_experiment_name.text(), self.spinBox_sample_loop_rep.value())
        new_item = QtGui.QStandardItem(batch_experiment)
        new_item.setEditable(False)
        new_item.item_type = 'experiment'
        new_item.repeat=self.spinBox_sample_loop_rep.value()
        new_item.setIcon(icon_experiment)
        parent.appendRow(new_item)

    '''
    General methods used more than once
    '''

    def get_sample_position(self):
        sample_position_widget_dict = {
            'push_get_sample_position':
                {'x_widget': 'spinBox_sample_x',
                 'y_widget': 'spinBox_sample_y'},
            'push_get_sample_position_map_start':
                {'x_widget': 'spinBox_sample_x_map_start',
                 'y_widget': 'spinBox_sample_y_map_start'},
            'push_get_sample_position_map_end':
                {'x_widget': 'spinBox_sample_x_map_end',
                 'y_widget': 'spinBox_sample_y_map_end'}

        }

        sender_object = QObject().sender().objectName()
        x_value = self.sample_stage.x.position
        x_widget = getattr(self, sample_position_widget_dict[sender_object]['x_widget'])
        x_widget.setValue(x_value)
        y_value = self.sample_stage.y.position
        y_widget = getattr(self,sample_position_widget_dict[sender_object]['y_widget'])
        y_widget.setValue(y_value)

    ''' 
    Dealing with samples
    '''
    def create_new_sample(self):
        if self.lineEdit_sample_name.text():
            x = self.spinBox_sample_x.value()
            y = self.spinBox_sample_y.value()
            name = self.lineEdit_sample_name.text()
            comment = self.lineEdit_sample_comment.text()
            item = QtGui.QStandardItem(f'{name} at X {x} Y {y}')
            item.setDropEnabled(False)
            item.item_type = 'sample'
            item.setCheckable(True)
            item.setEditable(False)
            item.x = x
            item.y = y
            item.name = name
            item.comment = comment
            item.setIcon(icon_sample)

            parent = self.model_samples.invisibleRootItem()
            parent.appendRow(item)
            self.listView_samples.setModel(self.model_samples)
        else:
            self.message_box('Warning','Sample name is empty')



    def delete_sample(self):
        view = self.listView_samples
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    '''
    Dealing with scans
    '''

    def delete_scan(self):
        view = self.listView_scans
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def create_new_scan(self):
        if self.lineEdit_scan_name.text():
            scan_type= self.comboBox_scans.currentText()
            traj = self.comboBox_lut.currentText()
            repeat =  self.spinBox_scan_repeat.value()
            delay = self.spinBox_scan_delay.value()
            name = self.lineEdit_scan_name.text()
            item = QtGui.QStandardItem(f'{scan_type} with {traj}, {repeat} times with {delay} s delay')
            item.setDropEnabled(False)
            item.item_type = 'scan'
            item.scan_type = scan_type
            item.trajectory = self.comboBox_lut.currentIndex()
            item.repeat = repeat
            item.name = name
            item.delay = delay
            item.setCheckable(True)
            item.setEditable(False)
            item.setIcon(icon_scan)

            parent = self.model_scans.invisibleRootItem()
            parent.appendRow(item)
            self.listView_scans.setModel(self.model_scans)
        else:
            self.message_box('Warning','Scan name is empty')


    def delete_batch_element(self):
        if self.treeView_batch.selectedIndexes():
            selected_index = self.treeView_batch.selectedIndexes()[0]
            item = self.model_batch.itemFromIndex(selected_index)
            if item.item_type == 'experiment':
                self.treeView_batch.model().removeRows(item.row(), 1)
            else:
                item.parent().removeRow(item.row())

    '''
    Dealing with measurements
    '''

    def create_measurement(self):
        if self.treeView_batch.model().rowCount():
            if self.treeView_batch.selectedIndexes():
                selected_index = self.treeView_batch.selectedIndexes()[0]
                parent = self.model_batch.itemFromIndex(selected_index)
                if parent.item_type == 'experiment':
                    if self.radioButton_priority_sample.isChecked():
                        if self.listView_samples.model() is not None:
                            for index in range(self.listView_samples.model().rowCount()):
                                item_sample = self.listView_samples.model().item(index)
                                if item_sample.checkState():
                                    new_item_sample = self.clone_sample_item(item_sample)
                                    if self.listView_scans.model() is not None:
                                        scans_selected = 0
                                        for index in range(self.listView_scans.model().rowCount()):
                                            item_scan = self.listView_scans.model().item(index)
                                            if item_scan.checkState():
                                                scans_selected = 1
                                                new_item_scan = self.clone_scan_item(item_scan)
                                                new_item_sample.appendRow(new_item_scan)
                                                new_item_scan.setCheckable(False)
                                                new_item_scan.setEditable(False)
                                                new_item_scan.setIcon(icon_scan)
                                    if scans_selected:
                                        parent.appendRow(new_item_sample)
                                        new_item_sample.setCheckable(False)
                                        new_item_sample.setEditable(False)
                    else:
                        if self.listView_scans.model() is not None:
                            for index in range(self.listView_scans.model().rowCount()):
                                item_scan = self.listView_scans.model().item(index)
                                if item_scan.checkState():
                                    new_item_scan = self.clone_scan_item(item_scan)
                                    if self.listView_samples.model() is not None:
                                        samples_selected=0
                                        for index in range(self.listView_samples.model().rowCount()):
                                            item_sample = self.listView_samples.model().item(index)
                                            if item_scan.checkState():
                                                samples_selected = 1
                                                new_item_sample = self.clone_sample_item(item_sample)
                                                new_item_scan.appendRow(new_item_sample)
                                                new_item_scan.setCheckable(False)
                                                new_item_scan.setEditable(False)
                                                new_item_scan.setIcon(icon_scan)
                                        if samples_selected:
                                            parent.appendRow(new_item_scan)
                                            new_item_scan.setCheckable(False)
                                            new_item_scan.setEditable(False)

                    self.treeView_batch.expand(self.model_batch.indexFromItem(parent))

                    for index in range(parent.rowCount()):
                        self.treeView_batch.expand(self.model_batch.indexFromItem(parent.child(index)))
                    self.treeView_batch.setModel(self.model_batch)

    def clone_sample_item(self, item_sample):
        new_item_sample = QtGui.QStandardItem(item_sample.text())
        new_item_sample.item_type = 'sample'
        new_item_sample.x = item_sample.x
        new_item_sample.y = item_sample.y
        new_item_sample.name = item_sample.name
        new_item_sample.setIcon(icon_sample)
        return new_item_sample

    def clone_scan_item(self, item_scan):
        new_item_scan = QtGui.QStandardItem(item_scan.text())
        new_item_scan.item_type = 'scan'
        new_item_scan.trajectory = item_scan.trajectory
        new_item_scan.scan_type = item_scan.scan_type
        new_item_scan.repeat = item_scan.repeat
        new_item_scan.delay = item_scan.delay
        new_item_scan.name = item_scan.name
        return new_item_scan

    '''
    Dealing with services
    '''
    def create_service(self):
        #parse parameters
        service_params = dict()
        for i in range(len(self.service_param1)):
            variable = self.service_param2[i].text().split('=')[0]
            if (self.service_params_types[i] == int) or (self.service_params_types[i] == float):
                service_params[f'{variable}'] = f'{self.service_param1[i].value()}'
            elif (self.service_params_types[i] == bool):
                service_params[f'{variable}'] = f'{bool(self.service_param1[i].checkState())}'
            elif (self.service_params_types[i] == str):
                service_params[f'{variable}'] = f'{self.service_param1[i].text()}'
        service_plan=self.service_plan_funcs[self.comboBox_services.currentIndex()]
        new_item_service = QtGui.QStandardItem(f'Service: {self.comboBox_services.currentText()}')
        new_item_service.item_type = 'service'
        new_item_service.setIcon(icon_service)
        new_item_service.service_plan = service_plan
        new_item_service.service_params = service_params

        if self.treeView_batch.model().rowCount():
            if self.treeView_batch.selectedIndexes():
                selected_index = self.treeView_batch.selectedIndexes()[0]
                parent = self.model_batch.itemFromIndex(selected_index)
                if parent.item_type == 'experiment':
                    parent.appendRow(new_item_service)
                    new_item_service.setCheckable(False)
                    new_item_service.setEditable(False)
                    self.treeView_batch.expand(self.model_batch.indexFromItem(parent))
                elif parent.item_type == 'sample':
                    parent.insertRow(0,new_item_service)
                    new_item_service.setCheckable(False)
                    new_item_service.setEditable(False)
                    self.treeView_batch.expand(self.model_batch.indexFromItem(parent))

    def batch_info(self):
        if self.treeView_batch.model().rowCount():
            if self.treeView_batch.selectedIndexes():
                selected_index = self.treeView_batch.selectedIndexes()[0]
                item = self.model_batch.itemFromIndex(selected_index)
                if item.item_type == 'service':
                    message_box(f'Batch element: {item.item_type}')

    def populate_parameter_grid(self, index):
        for i in range(len(self.service_parameter_values)):
            self.gridLayout_service_parameters_service.removeWidget(self.service_parameter_values[i])
            self.gridLayout_service_parameters_service.removeWidget(self.service_parameter_descriptions[i])
            self.service_parameter_values[i].deleteLater()
            self.service_parameter_descriptions[i].deleteLater()
        service_plan_func = self.service_plan_funcs[self.comboBox_service_scan.currentText()]

        [self.service_parameter_values, self.service_parameter_descriptions, self.service_parameter_types]\
            = parse_plan_parameters(service_plan_func)

        for i in range(len(self.service_parameter_values)):
            self.gridLayout_service_parameters.addWidget(self.service_parameter_values[i], i, 0, QtCore.Qt.AlignTop)
            self.gridLayout_service_parameters.addWidget(self.service_parameter_descriptions[i], i, 1, QtCore.Qt.AlignTop)

    def update_batch_traj(self):
        self.trajectories = self.traj_manager.read_info(silent=True)
        self.comboBox_lut.clear()
        self.comboBox_lut.addItems(
            ['{}-{}'.format(lut, self.trajectories[lut]['name']) for lut in self.trajectories if lut != '9'])


    def create_map(self):
        if self.radioButton_sample_map_1D.isChecked():
            x_coord = np.linspace(self.spinBox_sample_x_map_start.value(),self.spinBox_sample_x_map_end.value(),
                                self.spinBox_sample_x_map_steps.value())
            y_coord = np.linspace(self.spinBox_sample_y_map_start.value(),self.spinBox_sample_y_map_end.value(),
                                self.spinBox_sample_x_map_steps.value())
            xy_coord = np.column_stack((x_coord,y_coord))

        elif self.radioButton_sample_map_2D.isChecked():
            x_coord = np.ndarray(0)
            y_coord = np.ndarray(0)
            y_points = np.linspace(self.spinBox_sample_y_map_start.value(), self.spinBox_sample_y_map_end.value(),
                                  self.spinBox_sample_y_map_steps.value())
            print(f' Y-points {y_points}')
            for i in range(int(self.spinBox_sample_y_map_steps.value())):
                print(i)
                x_line = np.linspace(self.spinBox_sample_x_map_start.value(),self.spinBox_sample_x_map_end.value(),
                                self.spinBox_sample_x_map_steps.value())
                y_line = np.ones(len(x_line))*(y_points[i])
                print(f'Y-line {y_line}')

                x_coord = np.append(x_coord, x_line)
                y_coord = np.append(y_coord, y_line)

        xy_coord = np.column_stack((x_coord, y_coord))
        print(xy_coord)











