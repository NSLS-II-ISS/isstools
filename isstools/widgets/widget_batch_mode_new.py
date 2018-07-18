import inspect
import re
import pkg_resources
from PyQt5 import uic, QtWidgets, QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from PyQt5 import uic, QtGui, QtCore, QtWidgets
from PyQt5.QtCore import QThread
from PyQt5.Qt import QSplashScreen, QObject
import numpy as np
import collections
import time as ttime
import os

from isstools.elements import elements
from isstools.trajectory.trajectory import trajectory_manager
from isstools.batch.batch import BatchManager
from isstools.batch.table_batch import XASBatchExperiment
import json
import pandas as pd
from bluesky.plan_stubs import mv

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_batch_mode_new.ui')

path_icon_experiment = pkg_resources.resource_filename('isstools', 'icons/experiment.png')
icon_experiment = QtGui.QIcon()
icon_experiment.addPixmap(QtGui.QPixmap(path_icon_experiment), QtGui.QIcon.Normal, QtGui.QIcon.Off)

path_icon_sample = pkg_resources.resource_filename('isstools', 'icons/sample.png')
icon_sample = QtGui.QIcon()
icon_sample.addPixmap(QtGui.QPixmap(path_icon_sample), QtGui.QIcon.Normal, QtGui.QIcon.Off)

path_icon_scan = pkg_resources.resource_filename('isstools', 'icons/scan.png')
icon_scan = QtGui.QIcon()
icon_scan.addPixmap(QtGui.QPixmap(path_icon_scan), QtGui.QIcon.Normal, QtGui.QIcon.Off)

class ItemSample(QtGui.QStandardItem):
    name = ''
    x = 0
    y = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class UIBatchModeNew(*uic.loadUiType(ui_path)):
    def __init__(self,
                 plan_funcs,
                 service_plan_funcs,
                 motors_dict,
                 hhm,
                 RE,
                 db,
                 gen_parser,
                 adc_list,
                 enc_list,
                 xia,
                 run_prep_traj,
                 scan_figure,
                 create_log_scan,
                 sample_stages,

                 parent_gui,
                 *args,test_motor = None, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        #self.addCanvas()

        self.plan_funcs = plan_funcs
        self.service_plan_funcs = service_plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        self.service_plan_funcs_names = [plan.__name__ for plan in service_plan_funcs]

        self.motors_dict = motors_dict
        self.mot_list = self.motors_dict.keys()
        self.mot_sorted_list = list(self.mot_list)
        self.mot_sorted_list.sort()
        self.hhm = hhm
        self.traj_manager = trajectory_manager(hhm)
        self.create_log_scan = create_log_scan

        self.RE = RE
        self.db = db
        self.figure = scan_figure
        self.run_prep_traj = run_prep_traj

        self.sample_stages = sample_stages
        self.parent_gui = parent_gui

        self.batch_mode_uids = []
        self.test_motor = test_motor
        self.treeView_batch = elements.TreeView(self, 'all')
        # self.treeView_samples_loop = elements.TreeView(self, 'sample')
        # self.treeView_samples_loop_scans = elements.TreeView(self, 'scan', unique_elements=False)
        # self.treeView_samples = elements.TreeView(self, 'sample')

        self.push_batch_delete_all.clicked.connect(self.delete_all_batch)
        self.gridLayout_batch_definition.addWidget(self.treeView_batch, 0, 0)


        self.batch_running = False
        self.batch_pause = False
        self.batch_abort = False
        self.batch_results = {}
        self.push_batch_pause.clicked.connect(self.pause_unpause_batch)
        self.push_batch_abort.clicked.connect(self.abort_batch)
        self.last_num_batch_text = 'i0'
        self.last_den_batch_text = 'it'

        self.analog_samp_time = '1'
        self.enc_samp_time = '1'
        self.adc_list = adc_list
        self.enc_list = enc_list
        self.xia = xia

        # sample functions
        self.push_create_batch_experiment.clicked.connect(self.create_batch_experiment)
        self.model_batch = QtGui.QStandardItemModel(self)
        self.treeView_batch.header().hide()
        self.treeView_batch.setModel(self.model_batch)
        self.model_samples = QtGui.QStandardItemModel(self)
        self.push_create_sample.clicked.connect(self.create_new_sample)
        self.push_delete_sample.clicked.connect(self.delete_sample)
        self.push_get_sample.clicked.connect(self.get_sample_pos)

        self.model_scans = QtGui.QStandardItemModel(self)
        self.push_create_scan.clicked.connect(self.create_new_scan_func)
        self.push_delete_scan.clicked.connect(self.delete_scan)

        self.push_batch_run.clicked.connect(self.start_batch)
        self.push_batch_delete.clicked.connect(self.delete_current_batch)
        self.push_create_measurement.clicked.connect(self.create_measurement)

        self.comboBox_scans.addItems(self.plan_funcs_names)
        self.comboBox_services.addItems(self.service_plan_funcs_names)
        self.comboBox_scans.currentIndexChanged.connect(self.populate_scan_parameters)
        self.comboBox_services.currentIndexChanged.connect(self.populate_service_parameters)
        self.push_create_scan_update.clicked.connect(self.update_batch_traj)

        #setting up sample table
        pushButtons_load = [self.pushButton_load_sample_def_11,
                            self.pushButton_load_sample_def_12,
                            self.pushButton_load_sample_def_13,
                            self.pushButton_load_sample_def_21,
                            self.pushButton_load_sample_def_22,
                            self.pushButton_load_sample_def_23,
                            self.pushButton_load_sample_def_31,
                            self.pushButton_load_sample_def_32,
                            self.pushButton_load_sample_def_33
                            ]
        for button in  pushButtons_load:
            button.clicked.connect(self.load_sample_definition)
        #%getattr(self, f'pushButton_show_sample_def_{i}')
        pushButtons_show = [self.pushButton_show_sample_def_11,
                            self.pushButton_show_sample_def_12,
                            self.pushButton_show_sample_def_13,
                            self.pushButton_show_sample_def_21,
                            self.pushButton_show_sample_def_22,
                            self.pushButton_show_sample_def_23,
                            self.pushButton_show_sample_def_31,
                            self.pushButton_show_sample_def_32,
                            self.pushButton_show_sample_def_33
                            ]
        for button in pushButtons_show:
            button.clicked.connect(self.show_sample_definition)

        self.coordinates = ['11',
                            '12',
                            '13',
                            '21',
                            '22',
                            '23',
                            '31',
                            '32',
                            '33']
        for x in self.coordinates:
            getattr(self,'pushButton_update_reference_{}'.format(x)).clicked.connect(self.update_reference)

        self.push_run_spreadsheet_batch.clicked.connect(self.run_spreadsheet_batch)



        self.tableWidget_sample_def.setColumnCount(7)
        self.tableWidget_sample_def.setHorizontalHeaderLabels(["Proposal", "SAF","Sample name",
                                                               "Composition", "Element","Edge","Energy"])
        widths = [80, 80, 200, 90, 80, 80, 80]
        for j in range(7):
            self.tableWidget_sample_def.setColumnWidth(j,widths[j])
        #doen setting table

        try:
           self.update_batch_traj()
        except OSError as err:
            print('Error loading:', err)

        self.widget_scan_param1 = []
        self.widget_scan_param2 = []
        self.widget_scan_param3 = []
        self.widget_service_param1 = []
        self.widget_service_param2 = []
        self.widget_service_param3 = []

        if len(self.plan_funcs) != 0:
            self.populate_scan_parameters(0)

        #if len(self.service_plan_funcs) != 0:
        #    self.populate_service_parameters(0)

        self.comboBox_sample_loop_motor.addItems(self.mot_sorted_list)
        self.comboBox_sample_loop_motor.currentTextChanged.connect(self.update_loop_values)

        spinBox_connects = [self.restore_add_loop,
                            self.comboBox_sample_loop_motor.setDisabled,
                            self.doubleSpinBox_motor_range_start.setDisabled,
                            self.doubleSpinBox_motor_range_stop.setDisabled,
                            self.doubleSpinBox_motor_range_step.setDisabled,
                            self.radioButton_sample_rel.setDisabled,
                            self.radioButton_sample_abs.setDisabled,
                            ]
        for changer in spinBox_connects:
            self.spinBox_sample_loop_rep.valueChanged.connect(changer)

        self.radioButton_sample_rel.toggled.connect(self.set_loop_values)
        self.last_lut = 0

        self.push_load_csv.clicked.connect(self.load_csv)
        self.push_save_csv.clicked.connect(self.save_csv)

        #checking which xystage to use:
        self.stage_x = ''
        self.stage_y = ''
        for stage in self.sample_stages:
            if stage['x'] in self.motors_dict and stage['y'] in self.motors_dict:
                if self.motors_dict[stage['x']]['object'].connected and\
                        self.motors_dict[stage['y']]['object'].connected:
                    self.stage_x = stage['x']
                    self.stage_y = stage['y']
                    break
        if self.stage_x == '' or self.stage_y == '':
            print('No stage set! Batch mode will not work!')

    def run_spreadsheet_batch(self):
        for coord in self.coordinates:
            if getattr(self, 'checkBox_run_cell_{}'.format(coord)).isChecked():
                experiment = getattr(self,'batch_experiment_{}'.format(coord))
                reference_x= getattr(self,'reference_x_{}'.format(coord))
                reference_y = getattr(self, 'reference_y_{}'.format(coord))

                experiment.batch_create_trajectories()
                experiment.create_unique_trajectories()
                experiment.assign_trajectory_number()
                experiment.save_trajectories()
                experiment.load_trajectories()
                #print(self.plan_funcs[3])
                #
                self.RE(experiment.plan_trajectory_priority(reference_x,reference_y,
                                                            sample_stage_x=self.test_motor.x,
                                                            sample_stage_y=self.test_motor.y,
                                                            plan=self.plan_funcs[0]))

    def update_reference(self):
        sender = QObject()
        sender_object = sender.sender().objectName()
        coord=sender_object[-2:]
        #TODO
        if self.stage_x not in self.mot_list:
            raise Exception('Stage X was not passed to the GUI')
        if self.stage_y not in self.mot_list:
            raise Exception('Stage Y was not passed to the GUI')

        if not self.motors_dict[self.stage_x]['object'].connected or \
                not self.motors_dict[self.stage_y]['object'].connected:
            raise Exception('Stage IOC not connected')

        x_value = self.motors_dict[self.stage_x]['object'].position
        y_value = self.motors_dict[self.stage_y]['object'].position



        setattr(self, 'reference_x_{}'.format(coord),x_value)
        setattr(self, 'reference_y_{}'.format(coord),y_value)

        getattr(self, 'lineEdit_reference_x_{}'.format(coord)).setText('{:.3f}'.format(x_value))
        getattr(self, 'lineEdit_reference_y_{}'.format(coord)).setText('{:.3f}'.format(y_value))


    def load_sample_definition(self):
        sender = QObject()
        sender_object = sender.sender().objectName()
        coord=sender_object[-2:]
        excel_file = QtWidgets.QFileDialog.getOpenFileNames(directory = '/nsls2/xf08id/Sandbox',
                   filter = '*.xlsx', parent = self)[0]
        if len(excel_file):

            self.label_database_status.setText('Loading {} to Sample Frame {}'.
                                               format(os.path.basename(excel_file[0]), coord))
            setattr(self, 'batch_experiment_{}'.format(coord), XASBatchExperiment(excel_file=excel_file[0], hhm=self.hhm))
            print(self.batch_experiment_11)

    def show_sample_definition(self):
        sender = QObject()
        sender_object = sender.sender().objectName()
        coord=sender_object[-2:]
        if hasattr(self,'batch_experiment_{}'.format(coord)):
            exp=getattr(self,'batch_experiment_{}'.format(coord))
            self.tableWidget_sample_def.setRowCount(len(exp.experiment_table))
            self.label_database_status.setText(exp.name)
            for i in range(len(exp.experiment_table)):
                d =exp.experiment_table.iloc[i]
                fields=['Proposal','SAF','Sample name','Composition','Element','Edge','Energy']
                for j,field in enumerate(fields):
                    self.tableWidget_sample_def.setItem(i, j, QtWidgets.QTableWidgetItem(str(d[field])))
                self.tableWidget_sample_def.setRowHeight(i,24)
        else:
            self.label_database_status.setText('Please load Experimental Definition first')



    def pause_unpause_batch(self):
        if self.batch_running == True:
            self.batch_pause = not self.batch_pause
            if self.batch_pause:
                print('Pausing batch run... It will pause in the next step.')
                self.push_batch_pause.setText('Unpause')
            else:
                print('Unpausing batch run...')
                self.push_batch_pause.setText('Pause')
                self.label_batch_step.setText(self.label_batch_step.text()[9:])

    def abort_batch(self):
        if self.batch_running == True:
            self.batch_abort = True
            self.re_abort()

    '''
    Dealing with samples
    '''


    def create_new_sample(self):
        name = self.lineEdit_sample_name.text()
        x =  self.doubleSpinBox_sample_x.value()
        y = self.doubleSpinBox_sample_y.value()
        parent = self.model_samples.invisibleRootItem()
        item = QtGui.QStandardItem('Sample {} at X: {} Y: {}'.format(name, x, y))
        item.setDropEnabled(False)
        item.item_type = 'sample'
        item.setCheckable(True)
        item.setEditable(False)
        item.x = x
        item.y = y
        item.name = name
        item.setIcon(icon_sample)
        parent.appendRow(item)
        self.listView_samples.setModel(self.model_samples)

    def get_sample_pos(self):
        if self.stage_x not in self.mot_list:
            raise Exception('Stage X was not passed to the GUI')
        if self.stage_y not in self.mot_list:
            raise Exception('Stage Y was not passed to the GUI')

        if not self.motors_dict[self.stage_x]['object'].connected or \
                not self.motors_dict[self.stage_y]['object'].connected:
            raise Exception('Stage IOC not connected')

        x_value = self.motors_dict[self.stage_x]['object'].position
        y_value = self.motors_dict[self.stage_y]['object'].position
        self.doubleSpinBox_sample_x.setValue(x_value)
        self.doubleSpinBox_sample_y.setValue(y_value)

    def delete_sample(self):
        view = self.listView_samples
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)
    '''
    Dealing with batch experiemnts
    '''



    def create_batch_experiment(self):
        parent = self.model_batch.invisibleRootItem()
        batch_experiment = 'Batch experiment "{}" repeat {} times'.format(self.lineEdit_batch_experiment_name.text(),
                                                                        self.spinBox_sample_loop_rep.value())

        new_item = QtGui.QStandardItem(batch_experiment)
        new_item.setEditable(False)
        new_item.item_type = 'experiment'
        new_item.repeat=self.spinBox_sample_loop_rep.value()
        new_item.setIcon(icon_experiment)
        #new_item.repeat=int()
        parent.appendRow(new_item)


    def create_measurement(self):
        if self.treeView_batch.model().rowCount():
            if self.treeView_batch.selectedIndexes():
                selected_index = self.treeView_batch.selectedIndexes()[0]
                parent = self.model_batch.itemFromIndex(selected_index)
                if parent.item_type == 'experiment':
                    if self.listView_samples.model() is not None:
                        for index in range(self.listView_samples.model().rowCount()):
                            item_sample = self.listView_samples.model().item(index)

                            # experiment_icon_path = pkg_resources.resource_filename('isstools', 'icons/experiment.png')
                            # sample_icon_path = pkg_resources.resource_filename('isstools', 'icons/sample.png')
                            # scan_icon_path = pkg_resources.resource_filename('isstools', 'icons/scan.png')

                            if item_sample.checkState():
                                new_item_sample = QtGui.QStandardItem(item_sample.text())
                                new_item_sample.item_type = 'sample'
                                new_item_sample.x = item_sample.x
                                new_item_sample.y = item_sample.y
                                new_item_sample.name = item_sample.name
                                new_item_sample.setIcon(icon_sample)

                                if self.listView_scans.model() is not None:
                                    for index in range(self.listView_scans.model().rowCount()):
                                        item_scan = self.listView_scans.model().item(index)
                                        if item_scan.checkState():
                                            new_item_scan = QtGui.QStandardItem(item_scan.text())
                                            new_item_scan.item_type = 'scan'
                                            new_item_scan.trajectory = item_scan.trajectory
                                            new_item_scan.scan_type = item_scan.scan_type
                                            new_item_sample.appendRow(new_item_scan)
                                            new_item_scan.setCheckable(False)
                                            new_item_scan.setEditable(False)
                                            new_item_scan.setIcon(icon_scan)
                            parent.appendRow(new_item_sample)
                            new_item_sample.setCheckable(False)
                            new_item_sample.setEditable(False)
                    self.treeView_batch.expand(self.model_batch.indexFromItem(parent))

                    for index in range(parent.rowCount()):
                        self.treeView_batch.expand(self.model_batch.indexFromItem(parent.child(index)))
                    self.treeView_batch.setModel(self.model_batch)


    '''
    Dealing with scans
    '''

    def delete_scan(self):
        view = self.listView_scans
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def create_new_scan_func(self):
        self.create_new_scan(self.comboBox_scans.currentText(), self.comboBox_lut.currentText())

    def create_new_scan(self, scan_type, traj):
        run_params = {}
        for i in range(len(self.widget_scan_param1)):
            if (self.param_types_batch[i] == int):
                run_params[self.widget_scan_param3[i].text().split('=')[0]] = self.widget_scan_param2[i].value()
            elif (self.param_types_batch[i] == float):
                run_params[self.widget_scan_param3[i].text().split('=')[0]] = self.widget_scan_param2[i].value()
            elif (self.param_types_batch[i] == bool):
                run_params[self.widget_scan_param3[i].text().split('=')[0]] = bool(self.widget_scan_param2[i].checkState())
            elif (self.param_types_batch[i] == str):
                run_params[self.widget_scan_param3[i].text().split('=')[0]] = self.widget_scan_param2[i].text()
        params = str(run_params)[1:-1].replace(': ', ':').replace(',', '').replace("'", "")

        parent = self.model_scans.invisibleRootItem()
        if self.comboBox_lut.isEnabled():
            item = QtGui.QStandardItem('Scan {} with trajectory {} {}'.format(scan_type, traj, params))
        else:
            item = QtGui.QStandardItem('{} {}'.format(scan_type, params))
        item.setDropEnabled(False)
        item.item_type = 'scan'
        item.scan_type = scan_type
        item.trajectory = self.comboBox_lut.currentIndex()

        item.setCheckable(True)
        item.setEditable(False)
        item.setIcon(icon_scan)
        parent.appendRow(item)
        self.listView_scans.setModel(self.model_scans)


    def start_batch(self):
        print('[Launching Threads]')
        self.run_batch()

    def print_batch(self):
        print('\n***** Printing Batch Steps *****')
        self.run_batch(print_only=True)
        print('***** Finished Batch Steps *****')

    def delete_current_batch(self):
        view = self.treeView_batch
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def delete_all_batch(self):
        view = self.treeView_samples
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())

        view = self.treeView_scans
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())

        view = self.treeView_samples_loop
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())

        view = self.treeView_samples_loop_scans
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())

        view = self.treeView_batch
        if view.model().hasChildren():
            view.model().removeRows(0, view.model().rowCount())



        #


    # def add_new_scan(self, item):
    #     parent = self.model_batch.invisibleRootItem()
    #     new_item = item.clone()
    #     new_item.item_type = 'scan'
    #     new_item.setEditable(False)
    #     new_item.setDropEnabled(False)
    #     name = new_item.text().split()[0]
    #     new_item.setText('Run {}'.format(new_item.text()))
    #     for index in range(item.rowCount()):
    #         subitem = QtGui.QStandardItem(item.child(index))
    #         subitem.setEnabled(False)
    #         subitem.setDropEnabled(False)
    #         new_item.appendRow(subitem)
    #     parent.appendRow(new_item)

    def update_loop_values(self, text):
        for motor in self.motors_dict:
            if self.comboBox_sample_loop_motor.currentText() == self.motors_dict[motor]['name']:
                curr_mot = self.motors_dict[motor]['object']
                break
        if self.radioButton_sample_rel.isChecked():
            if curr_mot.connected == True:
                self.push_add_sample_loop.setEnabled(True)
                self.doubleSpinBox_motor_range_start.setValue(-0.5)
                self.doubleSpinBox_motor_range_stop.setValue(0.5)
                self.doubleSpinBox_motor_range_step.setValue(0.25)
                self.push_add_sample_loop.setEnabled(True)
            else:
                self.push_add_sample_loop.setEnabled(False)
                self.doubleSpinBox_motor_range_start.setValue(0)
                self.doubleSpinBox_motor_range_stop.setValue(0)
                self.doubleSpinBox_motor_range_step.setValue(0.025)
        else:
            if curr_mot.connected == True:
                self.push_add_sample_loop.setEnabled(True)
                curr_pos = curr_mot.read()[curr_mot.name]['value']
                self.doubleSpinBox_motor_range_start.setValue(curr_pos - 0.1)
                self.doubleSpinBox_motor_range_stop.setValue(curr_pos + 0.1)
                self.doubleSpinBox_motor_range_step.setValue(0.025)
            else:
                self.push_add_sample_loop.setEnabled(False)
                self.doubleSpinBox_motor_range_start.setValue(0)
                self.doubleSpinBox_motor_range_stop.setValue(0)
                self.doubleSpinBox_motor_range_step.setValue(0.025)

    def restore_add_loop(self, value):
        if value:
            self.push_add_sample_loop.setEnabled(True)

    def set_loop_values(self, checked):
        if checked:
            self.doubleSpinBox_motor_range_start.setValue(-0.5)
            self.doubleSpinBox_motor_range_stop.setValue(0.5)
            self.doubleSpinBox_motor_range_step.setValue(0.25)
            self.push_add_sample_loop.setEnabled(True)
        else:
            motor_text = self.comboBox_sample_loop_motor.currentText()
            self.update_loop_values(motor_text)

    def add_new_sample_loop(self, samples, scans):
        parent = self.model_batch.invisibleRootItem()
        new_item = QtGui.QStandardItem('Sample Loop')
        new_item.setEditable(False)

        if self.spinBox_sample_loop_rep.value():
            repetitions_item = QtGui.QStandardItem('Repetitions:{}'.format(self.spinBox_sample_loop_rep.value()))
        else:
            repetitions_item = QtGui.QStandardItem(
                'Motor:{} Start:{} Stop:{} Step:{}'.format(self.comboBox_sample_loop_motor.currentText(),
                                                           self.doubleSpinBox_motor_range_start.value(),
                                                           self.doubleSpinBox_motor_range_stop.value(),
                                                           self.doubleSpinBox_motor_range_step.value()))
        new_item.appendRow(repetitions_item)

        if self.radioButton_sample_loop.isChecked():
            primary = 'Samples'
        else:
            primary = 'Scans'
        primary_item = QtGui.QStandardItem('Primary:{}'.format(primary))
        new_item.appendRow(primary_item)

        samples_item = QtGui.QStandardItem('Samples')
        samples_item.setDropEnabled(False)
        for index in range(len(samples)):
            subitem = QtGui.QStandardItem(samples[index])
            subitem.setDropEnabled(False)
            samples_item.appendRow(subitem)
        new_item.appendRow(samples_item)

        scans_item = QtGui.QStandardItem('Scans')
        scans_item.setDropEnabled(False)
        for index in range(len(scans)):
            subitem = QtGui.QStandardItem(scans[index])
            subitem.setDropEnabled(False)
            scans_item.appendRow(subitem)
        new_item.appendRow(scans_item)

        parent.appendRow(new_item)
        self.treeView_batch.expand(self.model_batch.indexFromItem(new_item))
        for index in range(new_item.rowCount()):
            self.treeView_batch.expand(new_item.child(index).index())

    def populate_scan_parameters(self, index):
        # DEPRECATED
        # if self.comboBox_scans.currentText()[: 5] != 'tscan':
        #     self.comboBox_lut.setEnabled(False)
        # else:
        #     self.comboBox_lut.setEnabled(True)

        for i in range(len(self.widget_scan_param1)):
            self.gridLayout_scans.removeWidget(self.widget_scan_param1[i])
            self.gridLayout_scans.removeWidget(self.widget_scan_param2[i])
            self.gridLayout_scans.removeWidget(self.widget_scan_param3[i])
            self.widget_scan_param1[i].deleteLater()
            self.widget_scan_param2[i].deleteLater()
            self.widget_scan_param3[i].deleteLater()
        self.widget_scan_param1 = []
        self.widget_scan_param2 = []
        self.widget_scan_param3 = []
        self.param_types_batch = []
        plan_func = self.plan_funcs[index]
        signature = inspect.signature(plan_func)
        for i in range(0, len(signature.parameters)):
            default = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))
            if default == str(signature.parameters[list(signature.parameters)[i]]):
                default = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))
            self.add_parameters(list(signature.parameters)[i], default,
                                 signature.parameters[list(signature.parameters)[i]].annotation,
                                 grid=self.gridLayout_scans,
                                 params=[self.widget_scan_param1, self.widget_scan_param2, self.widget_scan_param3])
            self.param_types_batch.append(signature.parameters[list(signature.parameters)[i]].annotation)

    def populate_service_parameters(self, index):
        # DEPRECATED
        # if self.comboBox_scans.currentText()[: 5] != 'tscan':
        #     self.comboBox_lut.setEnabled(False)
        # else:
        #     self.comboBox_lut.setEnabled(True)

        for i in range(len(self.widget_scan_param1)):
            self.gridLayout_scans.removeWidget(self.widget_service_param1[i])
            self.gridLayout_scans.removeWidget(self.widget_service_param2[i])
            self.gridLayout_scans.removeWidget(self.widget_service_param3[i])
            self.widget_service_param1[i].deleteLater()
            self.widget_service_param2[i].deleteLater()
            self.widget_service_param3[i].deleteLater()
        self.widget_service_param1 = []
        self.widget_service_param2 = []
        self.widget_service_param3 = []
        self.param_types_batch = []
        plan_func = self.service_plan_funcs[index]
        signature = inspect.signature(plan_func)
        for i in range(0, len(signature.parameters)):
            default = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))
            if default == str(signature.parameters[list(signature.parameters)[i]]):
                default = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))
            self.add_parameters(list(signature.parameters)[i], default,
                                signature.parameters[list(signature.parameters)[i]].annotation,
                                grid=self.gridLayout_services,
                                params=[self.widget_service_param1, self.widget_service_param2, self.widget_service_param3])
            self.param_types_batch.append(signature.parameters[list(signature.parameters)[i]].annotation)

    def add_parameters(self, name, default, annotation, grid, params):
        rows = int((grid.count()) / 3)
        param1 = QtWidgets.QLabel(str(rows + 1))

        param2 = None
        def_val = ''
        if default.find('=') != -1:
            def_val = re.sub(r'.*=', '', default)
        if annotation == int:
            param2 = QtWidgets.QSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = int(def_val)
            param2.setValue(def_val)
        elif annotation == float:
            param2 = QtWidgets.QDoubleSpinBox()
            param2.setMaximum(100000)
            param2.setMinimum(-100000)
            def_val = float(def_val)
            param2.setValue(def_val)
        elif annotation == bool:
            param2 = QtWidgets.QCheckBox()
            if def_val == 'True':
                def_val = True
            else:
                def_val = False
            param2.setCheckState(def_val)
            param2.setTristate(False)
        elif annotation == str:
            param2 = QtWidgets.QLineEdit()
            def_val = str(def_val)
            param2.setText(def_val)

        if param2 is not None:
            param3 = QtWidgets.QLabel(default)
            grid.addWidget(param1, rows, 0, QtCore.Qt.AlignTop)
            grid.addWidget(param2, rows, 1, QtCore.Qt.AlignTop)
            grid.addWidget(param3, rows, 2, QtCore.Qt.AlignTop)
            params[0].append(param1)
            params[1].append(param2)
            params[2].append(param3)

    def update_batch_traj(self):
        self.trajectories = self.traj_manager.read_info(silent=True)
        self.comboBox_lut.clear()
        self.comboBox_lut.addItems(
            ['{}-{}'.format(lut, self.trajectories[lut]['name']) for lut in self.trajectories if lut != '9'])

    def load_csv(self):
        user_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/'.format(self.RE.md['year'],
                                                                  self.RE.md['cycle'],
                                                                  self.RE.md['PROPOSAL'])
        filename = QtWidgets.QFileDialog.getOpenFileName(caption='Select file to load',
                                                         directory=user_filepath,
                                                         filter='*.csv',
                                                         parent=self)[0]
        if filename:
            batman = BatchManager(self)
            batman.load_csv(filename)

    def save_csv(self):
        user_filepath = '/GPFS/xf08id/User Data/{}.{}.{}/'.format(self.RE.md['year'],
                                                                  self.RE.md['cycle'],
                                                                  self.RE.md['PROPOSAL'])
        filename = QtWidgets.QFileDialog.getSaveFileName(caption='Select file to save',
                                                         directory=user_filepath,
                                                         filter='*.csv',
                                                         parent=self)[0]
        if filename:
            if filename[-4:] != '.csv':
                filename += '.csv'
            batman = BatchManager(self)
            batman.save_csv(filename)

    def check_pause_abort_batch(self):
        if self.batch_abort:
            print('**** Aborting Batch! ****')
            raise Exception('Abort button pressed by user')
        elif self.batch_pause:
            self.label_batch_step.setText('[Paused] {}'.format(self.label_batch_step.text()))
            while self.batch_pause:
                QtCore.QCoreApplication.processEvents()

    def run_batch(self, print_only=False):
        print(self.test_motor)
        batch = self.treeView_batch.model()
        print(batch)
        plans_dict = {x.__name__: x for x in  self.plan_funcs}
        self.RE(self.batch_parse_and_run(self.hhm, self.test_motor, batch, plans_dict))

    def batch_parse_and_run(self, hhm,sample_stage,batch,plans_dict ):
        tm = trajectory_manager(hhm)
        print(tm)
        for ii in range(batch.rowCount()):
            experiment = batch.item(ii)
            print(experiment.item_type)
            repeat=experiment.repeat
            print(repeat)
            for jj in range(experiment.rowCount()):
                print(experiment.rowCount())
                sample = experiment.child(jj)
                print('  ' + sample.name)
                print('  ' + str(sample.x))
                print('  ' + str(sample.y))
                yield from mv(sample_stage.x, sample.x, sample_stage.y, sample.y)
                for kk in range(sample.rowCount()):
                    scan = sample.child(kk)
                    traj_index= scan.trajectory
                    print('      ' + scan.scan_type)
                    plan = plans_dict[scan.scan_type]
                    kwargs = {'name': sample.name,
                              'comment': '',
                              'delay': 0,
                              'n_cycles': repeat,
                              'stdout': self.parent_gui.emitstream_out}
                    tm.init(traj_index+1)
                    yield from plan(**kwargs)

    def setAnalogSampTime(self, text):
        self.analog_samp_time = text

    def setEncSampTime(self, text):
        self.enc_samp_time = text

    def setXiaSampTime(self, text):
        self.xia_samp_time = text

    def re_abort(self):
        if self.RE.state != 'idle':
            self.RE.abort()
            self.RE.is_aborted = True
