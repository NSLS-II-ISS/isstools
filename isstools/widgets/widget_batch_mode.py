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
import numpy as np
import collections
import time as ttime

from isstools.elements import elements
from isstools.trajectory.trajectory import trajectory_manager
from isstools.batch.batch import BatchManager

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_batch_mode.ui')

import json
import pandas as pd

class UIBatchMode(*uic.loadUiType(ui_path)):
    def __init__(self,
                 plan_funcs,
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
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()

        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]

        self.motors_dict = motors_dict
        self.mot_list = self.motors_dict.keys()
        self.mot_sorted_list = list(self.mot_list)
        self.mot_sorted_list.sort()

        self.traj_manager = trajectory_manager(hhm)
        self.create_log_scan = create_log_scan
        self.RE = RE
        self.db = db
        self.figure = scan_figure
        self.run_prep_traj = run_prep_traj

        self.gen_parser = gen_parser
        self.sample_stages = sample_stages
        self.parent_gui = parent_gui

        self.batch_mode_uids = []
        self.treeView_batch = elements.TreeView(self, 'all')
        self.treeView_samples_loop = elements.TreeView(self, 'sample')
        self.treeView_samples_loop_scans = elements.TreeView(self, 'scan', unique_elements=False)
        self.treeView_samples = elements.TreeView(self, 'sample')
        self.treeView_scans = elements.TreeView(self, 'scan')
        self.push_batch_delete_all.clicked.connect(self.delete_all_batch)
        self.gridLayout_22.addWidget(self.treeView_samples_loop, 1, 0)
        self.gridLayout_22.addWidget(self.treeView_samples_loop_scans, 1, 1)
        self.gridLayout_23.addWidget(self.treeView_samples, 0, 0)
        self.gridLayout_24.addWidget(self.treeView_batch, 0, 0)
        self.gridLayout_26.addWidget(self.treeView_scans, 0, 0)
        self.treeView_batch.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        # self.treeView_samples.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.treeView_samples.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self.treeView_scans.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self.treeView_samples_loop.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)
        self.treeView_samples_loop_scans.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)
        self.batch_running = False
        self.batch_pause = False
        self.batch_abort = False
        self.batch_results = {}
        self.push_batch_pause.clicked.connect(self.pause_unpause_batch)
        self.push_batch_abort.clicked.connect(self.abort_batch)
        self.push_replot_batch.clicked.connect(self.plot_batches)
        self.last_num_batch_text = 'i0'
        self.last_den_batch_text = 'it'

        self.analog_samp_time = '1'
        self.enc_samp_time = '1'
        self.adc_list = adc_list
        self.enc_list = enc_list
        self.xia = xia

        self.treeView_batch.header().hide()
        self.treeView_samples.header().hide()
        self.treeView_scans.header().hide()
        self.treeView_samples_loop.header().hide()
        self.treeView_samples_loop_scans.header().hide()

        self.push_create_sample.clicked.connect(self.create_new_sample_func)
        self.push_get_sample.clicked.connect(self.get_sample_pos)
        self.model_samples = QtGui.QStandardItemModel(self)
        self.treeView_samples.setModel(self.model_samples)

        self.push_add_sample.clicked.connect(self.add_new_sample_func)
        self.push_delete_sample.clicked.connect(self.delete_current_sample)
        self.model_batch = QtGui.QStandardItemModel(self)
        self.treeView_batch.setModel(self.model_batch)

        self.push_add_sample_loop.clicked.connect(self.add_new_sample_loop_func)
        self.push_delete_sample_loop.clicked.connect(self.delete_current_samples_loop)
        self.model_samples_loop = QtGui.QStandardItemModel(self)
        self.treeView_samples_loop.setModel(self.model_samples_loop)

        self.push_delete_sample_loop_scan.clicked.connect(self.delete_current_samples_loop_scans)
        self.model_samples_loop_scans = QtGui.QStandardItemModel(self)
        self.treeView_samples_loop_scans.setModel(self.model_samples_loop_scans)

        self.push_create_scan.clicked.connect(self.create_new_scan_func)
        self.push_delete_scan.clicked.connect(self.delete_current_scan)
        self.push_add_scan.clicked.connect(self.add_new_scan_func)
        self.model_scans = QtGui.QStandardItemModel(self)
        self.treeView_scans.setModel(self.model_scans)

        self.push_batch_run.clicked.connect(self.start_batch)
        self.push_batch_print_steps.clicked.connect(self.print_batch)
        self.push_batch_delete.clicked.connect(self.delete_current_batch)

        self.comboBox_scans.addItems(self.plan_funcs_names)
        self.comboBox_scans.currentIndexChanged.connect(self.populateParams_batch)
        self.push_create_scan_update.clicked.connect(self.update_batch_traj)
        try:
           self.update_batch_traj()
        except OSError as err:
            print('Error loading:', err)

        self.params1_batch = []
        self.params2_batch = []
        self.params3_batch = []
        if len(self.plan_funcs) != 0:
            self.populateParams_batch(0)

        self.comboBox_sample_loop_motor.addItems(self.mot_sorted_list)
        self.comboBox_sample_loop_motor.currentTextChanged.connect(self.update_loop_values)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.restore_add_loop)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.comboBox_sample_loop_motor.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.doubleSpinBox_motor_range_start.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.doubleSpinBox_motor_range_stop.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.doubleSpinBox_motor_range_step.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.radioButton_sample_rel.setDisabled)
        self.spinBox_sample_loop_rep.valueChanged.connect(self.radioButton_sample_abs.setDisabled)
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

    def addCanvas(self):
        self.figure_batch_waterfall = Figure()
        self.figure_batch_waterfall.set_facecolor(color='#FcF9F6')
        self.canvas_batch_waterfall = FigureCanvas(self.figure_batch_waterfall)
        self.canvas_batch_waterfall.motor = ''
        self.figure_batch_waterfall.ax = self.figure_batch_waterfall.add_subplot(111)
        self.toolbar_batch_waterfall = NavigationToolbar(self.canvas_batch_waterfall, self, coordinates=True)
        self.plot_batch_waterfall.addWidget(self.toolbar_batch_waterfall)
        self.plot_batch_waterfall.addWidget(self.canvas_batch_waterfall)
        self.canvas_batch_waterfall.draw_idle()
        self.cursor_batch_waterfall = Cursor(self.figure_batch_waterfall.ax, useblit=True, color='green',
                                             linewidth=0.75)

        self.figure_batch_average = Figure()
        self.figure_batch_average.set_facecolor(color='#FcF9F6')
        self.canvas_batch_average = FigureCanvas(self.figure_batch_average)
        self.canvas_batch_average.motor = ''
        self.figure_batch_average.ax = self.figure_batch_average.add_subplot(111)
        self.toolbar_batch_average = NavigationToolbar(self.canvas_batch_average, self, coordinates=True)
        self.plot_batch_average.addWidget(self.toolbar_batch_average)
        self.plot_batch_average.addWidget(self.canvas_batch_average)
        self.canvas_batch_average.draw_idle()
        self.cursor_batch_average = Cursor(self.figure_batch_average.ax, useblit=True, color='green', linewidth=0.75)

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

    def plot_batches(self, data):
        if self.parent_gui.run_mode == 'batch':
            self.figure_batch_waterfall.ax.clear()
            self.toolbar_batch_waterfall._views.clear()
            self.toolbar_batch_waterfall._positions.clear()
            self.toolbar_batch_waterfall._update_view()
            self.canvas_batch_waterfall.draw_idle()

            self.figure_batch_average.ax.clear()
            self.toolbar_batch_average._views.clear()
            self.toolbar_batch_average._positions.clear()
            self.toolbar_batch_average._update_view()
            self.canvas_batch_average.draw_idle()

            df = pd.read_msgpack(data['processing_ret']['data'])
            #df = pd.DataFrame.from_dict(json.loads(data['processing_ret']['data']))
            df = df.sort_values('energy')
            self.df = df

            md = data['processing_ret']['metadata']
            trajectory_name = md['trajectory_name']
            scan_name = md['name']
            sample_name = scan_name.split(' - ')[0]
            e0 = int(md['e0'])

            if sample_name in self.batch_results:
                self.batch_results[sample_name]['data'].append(df)
                self.batch_results[sample_name]['orig_all'] = self.batch_results[sample_name]['orig_all'].append(df,
                                                                                                                 ignore_index=True)
                self.gen_parser.interp_arrays = self.batch_results[sample_name]['orig_all']
                binned = self.gen_parser.bin(e0,
                                             e0 - 30,
                                             e0 + 50,
                                             10,
                                             0.2,
                                             0.04)
                self.batch_results[sample_name]['data_all'] = binned

            else:
                self.batch_results[sample_name] = {'data': [df]}
                self.batch_results[sample_name]['orig_all'] = df
                self.gen_parser.interp_df = self.batch_results[sample_name]['orig_all']
                binned = self.gen_parser.bin(e0,
                                             e0 - 30,
                                             e0 + 50,
                                             10,
                                             0.2,
                                             0.04)
                self.batch_results[sample_name]['data_all'] = binned

            largest_range = 0
            for sample_index, sample in enumerate(self.batch_results):
                for data_index, data_set in enumerate(self.batch_results[sample]['data']):
                    if self.listWidget_numerator_batch.count() == 0:
                        self.listWidget_numerator_batch.insertItems(0, list(data_set.keys()))
                        self.listWidget_denominator_batch.insertItems(0, list(data_set.keys()))
                        if len(data_set.keys()):
                            while self.listWidget_numerator_batch.count() == 0 or self.listWidget_denominator_batch.count() == 0:
                                QtCore.QCoreApplication.processEvents()
                        index_num = [index for index, item in enumerate(
                            [self.listWidget_numerator_batch.item(index) for index in
                             range(self.listWidget_numerator_batch.count())]) if item.text() == self.last_num_batch_text]
                        if len(index_num):
                            self.listWidget_numerator_batch.setCurrentRow(index_num[0])
                        index_den = [index for index, item in enumerate(
                            [self.listWidget_denominator_batch.item(index) for index in
                             range(self.listWidget_denominator_batch.count())]) if item.text() == self.last_den_batch_text]
                        if len(index_den):
                            self.listWidget_denominator_batch.setCurrentRow(index_den[0])

                    else:
                        if self.listWidget_numerator_batch.currentRow() != -1:
                            self.last_num_batch_text = self.listWidget_numerator_batch.currentItem().text()
                        if self.listWidget_denominator_batch.currentRow() != -1:
                            self.last_den_batch_text = self.listWidget_denominator_batch.currentItem().text()

                    energy_string = 'energy'
                    result = data_set[self.last_num_batch_text] / data_set[self.last_den_batch_text]

                    if self.checkBox_log_batch.checkState() > 0:
                        result = np.log(result)

                    if result.max() - result.min() > largest_range:
                        largest_range = result.max() - result.min()

            for sample_index, sample in enumerate(self.batch_results):
                for data_index, data_set in enumerate(self.batch_results[sample]['data']):

                    energy_string = 'energy'
                    result = data_set[self.last_num_batch_text] / data_set[self.last_den_batch_text]
                    data_set_all = self.batch_results[sample]['data_all']
                    result_all = data_set_all[self.last_num_batch_text] / data_set_all[self.last_den_batch_text]
                    # print('data_set', len(data_set['i0']))

                    if self.checkBox_log_batch.checkState() > 0:
                        result = np.log(result)
                        result_all = np.log(result_all)

                    distance_multiplier = 1.25

                    if data_index == 0:
                        text_y = (sample_index * largest_range * distance_multiplier) + (result.max() + result.min()) / 2
                        bbox_props = dict(boxstyle="round,pad=0.3", fc="white", ec="black", lw=1.3)
                        self.figure_batch_waterfall.ax.text(data_set[energy_string].iloc[-1], text_y, sample, size=11,
                                                            horizontalalignment='right', clip_on=True, bbox=bbox_props)
                        self.figure_batch_average.ax.text(data_set_all[energy_string].iloc[-1], text_y, sample, size=11,
                                                          horizontalalignment='right', clip_on=True, bbox=bbox_props)

                    self.figure_batch_waterfall.ax.plot(data_set[energy_string].iloc[:len(result)],
                                                        (sample_index * largest_range * distance_multiplier) + result)
                    self.figure_batch_average.ax.plot(data_set_all[energy_string].iloc[:len(result_all)],
                                                      (sample_index * largest_range * distance_multiplier) + result_all)
            self.canvas_batch_waterfall.draw_idle()
            self.canvas_batch_average.draw_idle()

    def create_new_sample_func(self):
        self.create_new_sample(self.lineEdit_sample_name.text(), self.doubleSpinBox_sample_x.value(),
                               self.doubleSpinBox_sample_y.value())

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

    def add_new_sample_func(self):
        indexes = self.treeView_samples.selectedIndexes()
        for index in indexes:
            item = index.model().itemFromIndex(index)
            self.add_new_sample(item)

    def delete_current_sample(self):
        view = self.treeView_samples
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def add_new_sample_loop_func(self):
        model_samples = self.treeView_samples_loop.model()
        data_samples = []
        for row in range(model_samples.rowCount()):
            index = model_samples.index(row, 0)
            data_samples.append(str(model_samples.data(index)))

        model_scans = self.treeView_samples_loop_scans.model()
        data_scans = []
        for row in range(model_scans.rowCount()):
            index = model_scans.index(row, 0)
            data_scans.append(str(model_scans.data(index)))

        self.add_new_sample_loop(data_samples, data_scans)

    def delete_current_samples_loop(self):
        view = self.treeView_samples_loop
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def delete_current_samples_loop_scans(self):
        view = self.treeView_samples_loop_scans
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def delete_current_scan(self):
        view = self.treeView_scans
        index = view.currentIndex()
        if index.row() < view.model().rowCount():
            view.model().removeRows(index.row(), 1)

    def create_new_scan_func(self):
        self.create_new_scan(self.comboBox_scans.currentText(), self.comboBox_lut.currentText())

    def add_new_scan_func(self):
        indexes = self.treeView_scans.selectedIndexes()
        for index in indexes:
            item = index.model().itemFromIndex(index)
            self.add_new_scan(item)

    def start_batch(self):
        print('[Launching Threads]')
        self.listWidget_numerator_batch.clear()
        self.listWidget_denominator_batch.clear()
        self.figure_batch_waterfall.ax.clear()
        self.canvas_batch_waterfall.draw_idle()
        self.figure_batch_average.ax.clear()
        self.canvas_batch_average.draw_idle()
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

    def create_new_sample(self, name, x, y):
        parent = self.model_samples.invisibleRootItem()
        item = QtGui.QStandardItem('{} X:{} Y:{}'.format(name, x, y))
        item.setDropEnabled(False)
        item.item_type = 'sample'
        item.x = x
        item.y = y
        # subitem = QtGui.QStandardItem('X: {}'.format(x))
        # subitem.setEnabled(False)
        # item.appendRow(subitem)
        # subitem = QtGui.QStandardItem('Y: {}'.format(y))
        # subitem.setEnabled(False)
        # item.appendRow(subitem)
        parent.appendRow(item)
        self.treeView_samples.expand(self.model_samples.indexFromItem(item))

    def add_new_sample(self, item):
        parent = self.model_batch.invisibleRootItem()
        new_item = item.clone()
        new_item.item_type = 'sample'
        new_item.x = item.x
        new_item.y = item.y
        new_item.setEditable(False)
        new_item.setDropEnabled(False)
        name = new_item.text()[:new_item.text().find(' X:')]  # .split()[0]
        new_item.setText('Move to "{}" X:{} Y:{}'.format(name, item.x, item.y))
        for index in range(item.rowCount()):
            subitem = QtGui.QStandardItem(item.child(index))
            subitem.setEnabled(False)
            subitem.setDropEnabled(False)
            new_item.appendRow(subitem)
        parent.appendRow(new_item)

    def select_all_samples(self):
        if len(self.treeView_samples.selectedIndexes()) < self.model_samples.rowCount():
            self.treeView_samples.selectAll()
        else:
            self.treeView_samples.clearSelection()

    def create_new_scan(self, curr_type, traj):

        run_params = {}
        for i in range(len(self.params1_batch)):
            if (self.param_types_batch[i] == int):
                run_params[self.params3_batch[i].text().split('=')[0]] = self.params2_batch[i].value()
            elif (self.param_types_batch[i] == float):
                run_params[self.params3_batch[i].text().split('=')[0]] = self.params2_batch[i].value()
            elif (self.param_types_batch[i] == bool):
                run_params[self.params3_batch[i].text().split('=')[0]] = bool(self.params2_batch[i].checkState())
            elif (self.param_types_batch[i] == str):
                run_params[self.params3_batch[i].text().split('=')[0]] = self.params2_batch[i].text()
        params = str(run_params)[1:-1].replace(': ', ':').replace(',', '').replace("'", "")

        parent = self.model_scans.invisibleRootItem()
        if self.comboBox_lut.isEnabled():
            item = QtGui.QStandardItem('{} Traj:{} {}'.format(curr_type, traj, params))
        else:
            item = QtGui.QStandardItem('{} {}'.format(curr_type, params))
        item.setDropEnabled(False)
        item.item_type = 'sample'
        parent.appendRow(item)
        self.treeView_samples.expand(self.model_samples.indexFromItem(item))

    def add_new_scan(self, item):
        parent = self.model_batch.invisibleRootItem()
        new_item = item.clone()
        new_item.item_type = 'scan'
        new_item.setEditable(False)
        new_item.setDropEnabled(False)
        name = new_item.text().split()[0]
        new_item.setText('Run {}'.format(new_item.text()))
        for index in range(item.rowCount()):
            subitem = QtGui.QStandardItem(item.child(index))
            subitem.setEnabled(False)
            subitem.setDropEnabled(False)
            new_item.appendRow(subitem)
        parent.appendRow(new_item)

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

    def populateParams_batch(self, index):
        if self.comboBox_scans.currentText()[: 5] != 'tscan':
            self.comboBox_lut.setEnabled(False)
        else:
            self.comboBox_lut.setEnabled(True)

        for i in range(len(self.params1_batch)):
            self.gridLayout_31.removeWidget(self.params1_batch[i])
            self.gridLayout_31.removeWidget(self.params2_batch[i])
            self.gridLayout_31.removeWidget(self.params3_batch[i])
            self.params1_batch[i].deleteLater()
            self.params2_batch[i].deleteLater()
            self.params3_batch[i].deleteLater()
        self.params1_batch = []
        self.params2_batch = []
        self.params3_batch = []
        self.param_types_batch = []
        plan_func = self.plan_funcs[index]
        signature = inspect.signature(plan_func)
        for i in range(0, len(signature.parameters)):
            default = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))
            if default == str(signature.parameters[list(signature.parameters)[i]]):
                default = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))
            self.addParamControl(list(signature.parameters)[i], default,
                                 signature.parameters[list(signature.parameters)[i]].annotation,
                                 grid=self.gridLayout_31,
                                 params=[self.params1_batch, self.params2_batch, self.params3_batch])
            self.param_types_batch.append(signature.parameters[list(signature.parameters)[i]].annotation)

    def addParamControl(self, name, default, annotation, grid, params):
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
        try:
            self.last_lut = 0
            current_index = 0
            self.current_uid_list = []
            if print_only is False:
                self.parent_gui.run_mode = 'batch'
                self.batch_running = True
                self.batch_pause = False
                self.batch_abort = False

                # Send sampling time to the pizzaboxes:
                value = int(
                    round(float(self.analog_samp_time) / self.adc_list[0].sample_rate.value * 100000))

                for adc in self.adc_list:
                    adc.averaging_points.put(str(value))

                for enc in self.enc_list:
                    enc.filter_dt.put(float(self.enc_samp_time) * 100000)

                if self.xia is not None:
                    if self.xia.input_trigger is not None:
                        self.xia.input_trigger.unit_sel.put(1)  # ms, not us
                        self.xia.input_trigger.period_sp.put(int(self.xia_samp_time))

                self.batch_results = {}

            for batch_index in range(self.model_batch.rowCount()):
                index = self.model_batch.index(batch_index, 0)
                text = str(self.model_batch.data(index))
                item = self.model_batch.item(batch_index)
                font = QtGui.QFont()
                font.setWeight(QtGui.QFont.Bold)
                item.setFont(font)
                item.setText(text)

                if text.find('Move to ') == 0:
                    name = text[text.find('"') + 1:text.rfind('"')]
                    item_x = text[text.find('" X:') + 4:text.find(' Y:')]
                    item_y = text[text.find(' Y:') + 3:]
                    print('Move to sample "{}" (X: {}, Y: {})'.format(name, item_x, item_y))
                    ### Uncomment
                    if print_only == False:
                        self.label_batch_step.setText('Move to sample "{}" (X: {}, Y: {})'.format(name, item_x, item_y))
                        self.check_pause_abort_batch()

                        self.motors_dict[self.stage_x]['object'].move(item_x, wait=False)
                        self.motors_dict[self.stage_y]['object'].move(item_y, wait=False)
                        ttime.sleep(0.2)
                        while (self.motors_dict[self.stage_x]['object'].moving or \
                                       self.motors_dict[self.stage_y]['object'].moving):
                            QtCore.QCoreApplication.processEvents()
                            ### Uncomment

                if text.find('Run ') == 0:
                    scan_type = text.split()[0]

                    scans = collections.OrderedDict({})
                    scans_text = text[text.find(' ') + 1:]  # scans_tree.child(scans_index).text()
                    scan_name = scans_text[:scans_text.find(' ')]
                    scans_text = scans_text[scans_text.find(' ') + 1:]

                    i = 2
                    if scan_name in scans:
                        sn = scan_name
                        while sn in scans:
                            sn = '{}-{}'.format(scan_name, i)
                            i += 1
                        scan_name = sn
                    scans[scan_name] = collections.OrderedDict((k.strip(), v.strip()) for k, v in
                                                               (item.split(':') for item in scans_text.split(' ') if
                                                                len(item) > 1))
                    # print(json.dumps(scans, indent=2))

                    for scan in scans:
                        if 'Traj' in scans[scan]:
                            lut = scans[scan]['Traj'][:scans[scan]['Traj'].find('-')]
                            traj_name = scans[scan]['Traj'][scans[scan]['Traj'].find('-') + 1:]
                            ### Uncomment
                            if self.last_lut != lut:
                                print('Init trajectory {} - {}'.format(lut, traj_name))
                                if print_only == False:
                                    self.label_batch_step.setText('Init trajectory {} - {}'.format(lut, traj_name))
                                    self.check_pause_abort_batch()
                                    self.traj_manager.init(int(lut))
                                self.last_lut = lut
                            print('Prepare trajectory {} - {}'.format(lut, traj_name))
                            if print_only == False:
                                self.label_batch_step.setText('Prepare trajectory {} - {}'.format(lut, traj_name))
                                self.check_pause_abort_batch()
                                self.run_prep_traj()

                        if 'name' in scans[scan]:
                            old_name = scans[scan]['name']
                            scans[scan]['name'] = '{}-{}'.format(scans[scan]['name'],
                                                                 traj_name[:traj_name.find('.txt')])

                        if scan.find('-') != -1:
                            scan_name = scan[:scan.find('-')]
                        else:
                            scan_name = scan

                        ### Uncomment
                        if print_only == False:
                            if 'name' in scans[scan]:
                                self.label_batch_step.setText(
                                    'Execute {} - name: {}'.format(scan_name, scans[scan]['name']))
                                self.check_pause_abort_batch()
                            else:
                                self.label_batch_step.setText('Execute {}'.format(scan_name))
                                self.check_pause_abort_batch()
                            uid = self.plan_funcs[self.plan_funcs_names.index(scan_name)](**scans[scan])
                            if uid:
                                self.batch_mode_uids.extend(uid)
                        ### Uncomment (previous line)

                        if 'name' in scans[scan]:
                            print('Execute {} - name: {}'.format(scan_name, scans[scan]['name']))
                            scans[scan]['name'] = old_name
                        else:
                            print('Execute {}'.format(scan_name))

                if text == 'Sample Loop':
                    print('Running Sample Loop...')

                    repetitions = item.child(0).text()
                    rep_type = repetitions[:repetitions.find(':')]
                    if rep_type == 'Repetitions':
                        repetitions = np.arange(int(repetitions[repetitions.find(':') + 1:]))
                    elif rep_type == 'Motor':
                        repetitions = repetitions.split(' ')
                        rep_motor = repetitions[0][repetitions[0].find(':') + 1:]
                        rep_motor = self.motors_dict[rep_motor]['object']
                        rep_start = float(repetitions[1][repetitions[1].find(':') + 1:])
                        rep_stop = float(repetitions[2][repetitions[2].find(':') + 1:])
                        rep_step = float(repetitions[3][repetitions[3].find(':') + 1:])
                        repetitions = np.arange(rep_start, rep_stop + rep_step, rep_step)

                    primary = item.child(1).text()
                    primary = primary[primary.find(':') + 1:]

                    samples = collections.OrderedDict({})
                    if item.child(2).text() != 'Samples':
                        raise Exception('Where are the samples?')
                    samples_tree = item.child(2)
                    for sample_index in range(samples_tree.rowCount()):
                        sample_text = samples_tree.child(sample_index).text()
                        sample_name = sample_text[:sample_text.find(' X:')]
                        sample_text = sample_text[sample_text.find(' X:') + 1:].split()
                        samples[sample_name] = collections.OrderedDict({sample_text[0][
                                                                        0:sample_text[0].find(':')]: float(
                            sample_text[0][sample_text[0].find(':') + 1:]), sample_text[1][
                                                                            0:sample_text[1].find(':')]: float(
                            sample_text[1][sample_text[1].find(':') + 1:])})

                    scans = collections.OrderedDict({})
                    if item.child(3).text() != 'Scans':
                        raise Exception('Where are the scans?')
                    scans_tree = item.child(3)
                    for scans_index in range(scans_tree.rowCount()):
                        scans_text = scans_tree.child(scans_index).text()
                        scan_name = scans_text[:scans_text.find(' ')]
                        scans_text = scans_text[scans_text.find(' ') + 1:]

                        i = 2
                        if scan_name in scans:
                            sn = scan_name
                            while sn in scans:
                                sn = '{}-{}'.format(scan_name, i)
                                i += 1
                            scan_name = sn
                        scans[scan_name] = collections.OrderedDict((k.strip(), v.strip()) for k, v in
                                                                   (item.split(':') for item in scans_text.split(' ') if
                                                                    len(item) > 1))

                    # print(json.dumps(samples, indent=2))
                    # print(json.dumps(scans, indent=2))

                    print('-' * 40)
                    for step_number, rep in enumerate(repetitions):
                        print('Step #{}'.format(step_number + 1))
                        if rep_type == 'Motor':
                            print('Move {} to {} {}'.format(rep_motor.name, rep, rep_motor.egu))
                            ### Uncomment
                            if print_only == False:
                                self.label_batch_step.setText(
                                    'Move {} to {} {}  |  Loop step number: {}/{}'.format(rep_motor.name, rep,
                                                                                          rep_motor.egu,
                                                                                          step_number + 1,
                                                                                          len(repetitions)))
                                self.check_pause_abort_batch()
                                if hasattr(rep_motor, 'move'):
                                    rep_motor.move(rep)
                                elif hasattr(rep_motor, 'put'):
                                    rep_motor.put(rep)
                                    ### Uncomment

                        if primary == 'Samples':
                            for index, sample in enumerate(samples):
                                print('-' * 40)
                                print('Move to sample {} (X: {}, Y: {})'.format(sample, samples[sample]['X'],
                                                                                samples[sample]['Y']))
                                ### Uncomment
                                if print_only == False:
                                    self.label_batch_step.setText(
                                        'Move to sample {} (X: {}, Y: {}) | Loop step number: {}/{}'.format(sample,
                                                                                                            samples[
                                                                                                                sample][
                                                                                                                'X'],
                                                                                                            samples[
                                                                                                                sample][
                                                                                                                'Y'],
                                                                                                            step_number + 1,
                                                                                                            len(
                                                                                                                repetitions)))
                                    self.check_pause_abort_batch()
                                    self.motors_dict[self.stage_x]['object'].move(samples[sample]['X'], wait=False)
                                    self.motors_dict[self.stage_y]['object'].move(samples[sample]['Y'], wait=False)
                                    ttime.sleep(0.2)
                                    while (self.motors_dict[self.stage_x]['object'].moving or \
                                                   self.motors_dict[self.stage_y]['object'].moving):
                                        QtCore.QCoreApplication.processEvents()
                                ### Uncomment

                                for scan in scans:
                                    if 'Traj' in scans[scan]:
                                        lut = scans[scan]['Traj'][:scans[scan]['Traj'].find('-')]
                                        traj_name = scans[scan]['Traj'][scans[scan]['Traj'].find('-') + 1:]
                                        ### Uncomment
                                        if self.last_lut != lut:
                                            print('Init trajectory {} - {}'.format(lut, traj_name))
                                            if print_only == False:
                                                self.label_batch_step.setText(
                                                    'Init trajectory {} - {} | Loop step number: {}/{}'.format(lut,
                                                                                                               traj_name,
                                                                                                               step_number + 1,
                                                                                                               len(
                                                                                                                   repetitions)))
                                                self.check_pause_abort_batch()
                                                self.traj_manager.init(int(lut))
                                            self.last_lut = lut
                                        print('Prepare trajectory {} - {}'.format(lut, traj_name))
                                        if print_only == False:
                                            self.label_batch_step.setText(
                                                'Prepare trajectory {} - {} | Loop step number: {}/{}'.format(lut,
                                                                                                              traj_name,
                                                                                                              step_number + 1,
                                                                                                              len(
                                                                                                                  repetitions)))
                                            self.check_pause_abort_batch()
                                            self.run_prep_traj()

                                    if 'name' in scans[scan]:
                                        old_name = scans[scan]['name']
                                        scans[scan]['name'] = '{} - {} - {} - {}'.format(sample, scans[scan]['name'],
                                                                                         traj_name[
                                                                                         :traj_name.find('.txt')],
                                                                                         rep + 1)

                                    if scan.find('-') != -1:
                                        scan_name = scan[:scan.find('-')]
                                    else:
                                        scan_name = scan

                                    ### Uncomment
                                    if print_only == False:
                                        if 'name' in scans[scan]:
                                            self.label_batch_step.setText(
                                                'Execute {} - name: {} | Loop step number: {}/{}'.format(scan_name,
                                                                                                         scans[scan][
                                                                                                             'name'],
                                                                                                         step_number + 1,
                                                                                                         len(
                                                                                                             repetitions)))
                                            self.check_pause_abort_batch()
                                        else:
                                            self.label_batch_step.setText(
                                                'Execute {} | Loop step number: {}'.format(scan_name, step_number + 1))
                                            self.check_pause_abort_batch()
                                        uid = self.plan_funcs[self.plan_funcs_names.index(scan_name)](**scans[scan])
                                        if uid:
                                            self.batch_mode_uids.extend(uid)
                                    ### Uncomment (previous line)
                                    if 'name' in scans[scan]:
                                        print('Execute {} - name: {}'.format(scan_name, scans[scan]['name']))
                                        scans[scan]['name'] = old_name
                                    else:
                                        print('Execute {}'.format(scan_name))






                        elif primary == 'Scans':
                            for index_scan, scan in enumerate(scans):
                                for index, sample in enumerate(samples):
                                    print('-' * 40)
                                    print('Move to sample {} (X: {}, Y: {})'.format(sample, samples[sample]['X'],
                                                                                    samples[sample]['Y']))
                                    ### Uncomment
                                    if print_only == False:
                                        self.label_batch_step.setText(
                                            'Move to sample {} (X: {}, Y: {}) | Loop step number: {}/{}'.format(sample,
                                                                                                                samples[
                                                                                                                    sample][
                                                                                                                    'X'],
                                                                                                                samples[
                                                                                                                    sample][
                                                                                                                    'Y'],
                                                                                                                step_number + 1,
                                                                                                                len(
                                                                                                                    repetitions)))
                                        self.check_pause_abort_batch()
                                        self.motors_dict[self.stage_x]['object'].move(samples[sample]['X'], wait=False)
                                        self.motors_dict[self.stage_y]['object'].move(samples[sample]['Y'], wait=False)
                                        ttime.sleep(0.2)
                                        while (self.motors_dict[self.stage_x]['object'].moving or \
                                                       self.motors_dict[self.stage_y]['object'].moving):
                                            QtCore.QCoreApplication.processEvents()
                                    ### Uncomment

                                    lut = scans[scan]['Traj'][:scans[scan]['Traj'].find('-')]
                                    traj_name = scans[scan]['Traj'][scans[scan]['Traj'].find('-') + 1:]
                                    if self.last_lut != lut:
                                        print('Init trajectory {} - {}'.format(lut, traj_name))
                                        if print_only == False:
                                            self.label_batch_step.setText(
                                                'Init trajectory {} - {} | Loop step number: {}/{}'.format(lut,
                                                                                                           traj_name,
                                                                                                           step_number + 1,
                                                                                                           len(
                                                                                                               repetitions)))
                                            self.check_pause_abort_batch()
                                            self.traj_manager.init(int(lut))
                                        self.last_lut = lut
                                    print('Prepare trajectory {} - {}'.format(lut, traj_name))
                                    if print_only == False:
                                        self.label_batch_step.setText(
                                            'Prepare trajectory {} - {} | Loop step number: {}/{}'.format(lut,
                                                                                                          traj_name,
                                                                                                          step_number + 1,
                                                                                                          len(
                                                                                                              repetitions)))
                                        self.check_pause_abort_batch()
                                        self.run_prep_traj()

                                    old_name = scans[scan]['name']
                                    scans[scan]['name'] = '{} - {} - {} - {}'.format(sample, scans[scan]['name'],
                                                                                     traj_name[:traj_name.find('.txt')],
                                                                                     rep + 1)

                                    if scan.find('-') != -1:
                                        scan_name = scan[:scan.find('-')]
                                    else:
                                        scan_name = scan

                                    print('Execute {} - name: {}'.format(scan_name, scans[scan]['name']))
                                    ### Uncomment
                                    if print_only == False:
                                        self.label_batch_step.setText(
                                            'Execute {} - name: {} | Loop step number: {}/{}'.format(scan_name,
                                                                                                     scans[scan][
                                                                                                         'name'],
                                                                                                     step_number + 1,
                                                                                                     len(repetitions)))
                                        self.check_pause_abort_batch()
                                        uid = self.plan_funcs[self.plan_funcs_names.index(scan_name)](**scans[scan])
                                        if uid:
                                            self.batch_mode_uids.extend(uid)
                                    ### Uncomment (previous line)
                                    scans[scan]['name'] = old_name

                        print('-' * 40)

                font = QtGui.QFont()
                item.setFont(font)
                item.setText(text)

            if print_only == False:
                self.batch_running = False
                self.batch_processor.go = 0
                self.label_batch_step.setText('Finished (Idle)')

        except Exception as e:
            print(e)
            print('Batch run aborted!')
            font = QtGui.QFont()
            item.setFont(font)
            item.setText(text)
            self.batch_running = False
            self.batch_processor.go = 0
            self.label_batch_step.setText('Aborted! (Idle)')
            return

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
