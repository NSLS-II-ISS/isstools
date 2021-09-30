import pkg_resources
from PyQt5 import uic, QtGui, QtCore, QtWidgets
from PyQt5.Qt import Qt

from PyQt5.QtWidgets import QMenu
from isstools.elements import elements
from isstools.elements.parameter_handler import parse_plan_parameters
from xas.trajectory import trajectory_manager
from isstools.dialogs.BasicDialogs import message_box

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_batch_manual.ui')
from isstools.elements.batch_elements import *
from isstools.elements.batch_elements import (_create_batch_experiment, _create_new_sample, _create_new_scan, _clone_scan_item, _clone_sample_item)
import json
from isstools.dialogs import UpdateSampleInfo, UpdateScanInfo
from isstools.dialogs.BasicDialogs import question_message_box
import bluesky.plan_stubs as bps


class UIBatchManual(*uic.loadUiType(ui_path)):
    def __init__(self,
                 plan_funcs,
                 service_plan_funcs,
                 hhm,
                 sample_stage = None,
                 parent_gui = None,
                 sample_positioner = None,
                 RE = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.plan_funcs = plan_funcs
        self.service_plan_funcs = service_plan_funcs
        self.plan_funcs_names = plan_funcs.keys()
        self.service_plan_funcs_names = service_plan_funcs.keys()
        self.sample_stage = sample_stage
        self.RE = RE
        self.batch_mode_uids = []
        self.traj_manager = trajectory_manager(hhm)

        # sample functions
        self.push_create_batch_experiment.clicked.connect(self.create_batch_experiment)
        self.model_batch = QtGui.QStandardItemModel(self)
        self.model_samples = QtGui.QStandardItemModel(self)

        self.treeView_batch = elements.TreeView(self, 'all')
        self.treeView_batch.header().hide()
        self.treeView_batch.setModel(self.model_batch)
        self.treeView_batch.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeView_batch.customContextMenuRequested.connect(self.scan_batch_menu)
        self.treeView_batch.type = 'treeView'
        self.treeView_batch.setSelectionMode(4)  #ContiguousSelection
        self.gridLayout_batch_definition.addWidget(self.treeView_batch, 0, 0)

        '''
        WIP add horizontal scrollbar
        self.treeView_batch.header().horizontalScrollBar()
        '''


        self.push_create_sample.clicked.connect(self.create_new_sample)
        # self.push_create_sample_grid.clicked.connect(self.create_sample_grid)

        self.push_delete_sample.clicked.connect(self.delete_sample)
        self.push_delete_all_samples.clicked.connect(self.delete_all_samples)

        self.push_save_samples.clicked.connect(self.save_samples)
        self.push_load_samples.clicked.connect(self.load_samples)

        self.push_check_all.clicked.connect(self.check_all_samples)
        self.push_uncheck_all.clicked.connect(self.uncheck_all_samples)

        self.push_get_sample_position.clicked.connect(self.get_sample_position)
        self.push_get_sample_position_map_start.clicked.connect(self.get_sample_position)
        self.push_get_sample_position_map_end.clicked.connect(self.get_sample_position)

        self.listView_samples.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listView_samples.customContextMenuRequested.connect(self.sample_context_menu)
        self.listView_samples.type  = 'listView'
        self.listView_scans.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listView_scans.customContextMenuRequested.connect(self.scan_context_menu)
        self.listView_scans.type  = 'listView'

        self.model_scans = QtGui.QStandardItemModel(self)
        self.push_create_scan.clicked.connect(self.create_new_scan)
        self.push_delete_scan.clicked.connect(self.delete_scan)
        self.push_batch_delete.clicked.connect(self.delete_batch_element)
        self.push_batch_info.clicked.connect(self.batch_info)
        self.push_create_measurement.clicked.connect(self.create_measurement)
        self.push_create_service.clicked.connect(self.create_service)
        self.push_create_map.clicked.connect(self.create_map)
        self.checkBox_auto_position.toggled.connect(self.enable_user_position_input)
        self.enable_user_position_input()

        self.comboBox_scans.addItems(self.plan_funcs_names)
        self.comboBox_service_plan.addItems(self.service_plan_funcs_names)
        self.comboBox_service_plan.currentIndexChanged.connect(self.populate_service_parameters)
        self.push_update_traj_list.clicked.connect(self.update_batch_traj)
        self.last_lut = 0

        self.service_parameter_values = []
        self.service_parameter_descriptions = []
        self.populate_service_parameters(0)
        self.update_batch_traj()

        self.push_import_from_autopilot.clicked.connect(self.get_info_from_autopilot)

        self.sample_positioner = sample_positioner
        self.parent_gui = parent_gui.parent_gui
        self.settings = parent_gui.parent_gui.settings

    '''
    Dealing with batch experiemnts
    '''
    def create_batch_experiment(self):
        experiment_name = self.lineEdit_batch_experiment_name.text()
        experiment_rep = self.spinBox_exp_rep.value()
        _create_batch_experiment(experiment_name, experiment_rep, model=self.model_batch)
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
                 'y_widget': 'spinBox_sample_y_map_end'},
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

    def _check_the_xystage_vs_xylabel(self, tolerance=0.015):
        x_act = self.sample_stage.x.position
        y_act = self.sample_stage.y.position
        x_nom = self.spinBox_sample_x.value()
        y_nom = self.spinBox_sample_y.value()
        if not (np.isclose(x_act, x_nom, tolerance) & np.isclose(y_act, y_nom, tolerance)):
            self.spinBox_sample_x.setValue(x_act)
            self.spinBox_sample_y.setValue(y_act)

    def _create_one_sample(self):
        sample_name = self.lineEdit_sample_name.text()
        if sample_name:
            sample_x = self.spinBox_sample_x.value()
            sample_y = self.spinBox_sample_y.value()
            sample_comment = self.lineEdit_sample_comment.text()
            _create_new_sample(sample_name, sample_comment, sample_x, sample_y, model=self.model_samples)
            self.listView_samples.setModel(self.model_samples)
        else:
            message_box('Warning', 'Sample name is empty')

    def create_new_sample(self):
        if self.checkBox_auto_position.isChecked():
            self._check_the_xystage_vs_xylabel()
        step_size = self.spinBox_grid_spacing.value()
        n_x = self.spinBox_grid_x_points.value()
        n_y = self.spinBox_grid_y_points.value()
        x_array = np.arange(n_x, dtype=float)
        x_array -= np.median(x_array)
        y_array = np.arange(n_y, dtype=float)
        y_array -= np.median(y_array)
        x_mesh, y_mesh = np.meshgrid(x_array*step_size, y_array*step_size)
        x_mesh = x_mesh.ravel()
        y_mesh = y_mesh.ravel()

        radius = self.spinBox_sample_radius.value()
        if radius > 0:
            r_mesh = np.sqrt(x_mesh**2 + y_mesh**2)
            x_mesh = x_mesh[r_mesh <= radius]
            y_mesh = y_mesh[r_mesh <= radius]

        xs = self.spinBox_sample_x.value() + x_mesh
        ys = self.spinBox_sample_y.value() + y_mesh

        npt = xs.size
        x_orig = self.spinBox_sample_x.value()
        y_orig = self.spinBox_sample_y.value()

        base_name = self.lineEdit_sample_name.text()
        counter = 1
        for _x, _y in zip(xs, ys):
            _name = f'{base_name}'
            if npt > 1:
                _name += f' pos {counter:02d}'
            self.lineEdit_sample_name.setText(_name)
            self.spinBox_sample_x.setValue(_x)
            self.spinBox_sample_y.setValue(_y)
            self._create_one_sample()
            counter += 1
        self.lineEdit_sample_name.setText(base_name)
        self.spinBox_sample_x.setValue(x_orig)
        self.spinBox_sample_y.setValue(y_orig)

    def delete_sample(self):
        view = self.listView_samples
        index = view.currentIndex()
        if (view.model().rowCount()>0) and (index.row() < view.model().rowCount()):
            view.model().removeRows(index.row(), 1)

    def delete_all_samples(self):
        view = self.listView_samples
        n_rows = view.model().rowCount()
        for i in range(n_rows):
            view.model().removeRows(0, 1)

    def save_samples(self):
        samples = []
        for index in range(self.listView_samples.model().rowCount()):
            b = self.listView_samples.model().item(index)
            sample = {}
            sample['name'] = b.name
            sample['comment'] = b.comment
            sample['x'] = b.x
            sample['y'] = b.y
            samples.append(sample)

        print(samples)
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save trajectory...', '/nsls2/xf08id/Sandbox', '*.smpl',
                                                         options=QtWidgets.QFileDialog.DontConfirmOverwrite)[0]
        print(filename)
        if not filename.endswith('.smpl'):
            filename = filename + '.smpl'

        with open(filename, 'w') as f:
            f.write(json.dumps(samples))


    def load_samples(self):
        filename = QtWidgets.QFileDialog.getOpenFileName(directory='/nsls2/xf08id/Sandbox',
                                                         filter='*.smpl', parent=self)[0]
        print(filename)
        if filename:
            with open(filename, 'r') as f:
                samples = json.loads(f.read())
            print(samples)
            for sample in samples:
                _create_new_sample(sample['name'], sample['comment'], sample['x'], sample['y'], model=self.model_samples)
            self.listView_samples.setModel(self.model_samples)

    def check_all_samples(self):
        for i in range(self.model_samples.rowCount()):
            item = self.model_samples.item(i)
            item.setCheckState(2)

    def uncheck_all_samples(self):
        for i in range(self.model_samples.rowCount()):
            item = self.model_samples.item(i)
            item.setCheckState(0)

    def get_info_from_autopilot(self):
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
            message_box('Error', 'Autopilot is not  defined')


    def modify_item(self):
        sender_object = QObject().sender()
        selection = sender_object.selectedIndexes()
        if selection != []:
            index = sender_object.currentIndex()
            if sender_object.type == 'treeView':
                item = sender_object.model().itemFromIndex(sender_object.selectedIndexes()[0])
            else:
                item = sender_object.model().item(index.row())
            if item.item_type =='sample':
                dlg = UpdateSampleInfo.UpdateSampleInfo(str(item.name), str(item.comment),
                                                        item.x, item.y, 0,  parent=self)
                if dlg.exec_():
                    item.name, item.comment, item.x, item.y, _ = dlg.getValues()
                    item.setText(f'{item.name} at X {item.x} Y {item.y}')
            elif item.item_type == 'scan':
                scan_types = [self.comboBox_scans.itemText(i) for i in range(self.comboBox_scans.count())]
                trajectories = [self.comboBox_lut.itemText(i) for i in range(self.comboBox_lut.count())]

                dlg = UpdateScanInfo.UpdateScanInfo(str(item.name), str(item.scan_type),
                                                item.trajectory, item.repeat, item.delay,
                                                scan_types, trajectories,
                                                parent=self)

                if dlg.exec_():
                    item.name, item.scan_type, item.trajectory, item.repeat, item.delay = dlg.getValues()
                    item.setText(f'{item.scan_type} with {item.name} {item.repeat} times with {item.delay} s delay')
    '''
    Dealing with scans
    '''
    def delete_scan(self):

        view = self.listView_scans
        index = view.currentIndex()
        if (view.model().rowCount()>0) and (index.row() < view.model().rowCount()):
            view.model().removeRows(index.row(), 1)

    def create_new_scan(self):
        scan_name = self.lineEdit_scan_name.text()
        if scan_name:
            scan_type= self.comboBox_scans.currentText()
            scan_traj = int(self.comboBox_lut.currentText()[0])
            scan_repeat =  self.spinBox_scan_repeat.value()
            scan_delay = self.spinBox_scan_delay.value()
            scan_autofoil = False
            # name = self.lineEdit_scan_name.text()
            _create_new_scan(scan_name, scan_type, scan_traj, scan_repeat, scan_delay, scan_autofoil, model=self.model_scans)
            
            self.listView_scans.setModel(self.model_scans)
        else:
            message_box('Warning','Scan name is empty')

    def delete_batch_element(self):
        if self.treeView_batch.selectedIndexes():
            selected_index = self.treeView_batch.selectedIndexes()[0]
            item = self.model_batch.itemFromIndex(selected_index)
            if item.item_type=='experiment':
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
                                    new_item_sample = _clone_sample_item(item_sample)
                                    if self.listView_scans.model() is not None:
                                        scans_selected = 0
                                        for index in range(self.listView_scans.model().rowCount()):
                                            item_scan = self.listView_scans.model().item(index)
                                            if item_scan.checkState():
                                                scans_selected = 1
                                                new_item_scan = _clone_scan_item(item_scan)
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
                                    new_item_scan = _clone_scan_item(item_scan)
                                    print(f' Repeat {new_item_scan.repeat}')
                                    if self.listView_samples.model() is not None:
                                        samples_selected=0
                                        for index in range(self.listView_samples.model().rowCount()):
                                            item_sample = self.listView_samples.model().item(index)
                                            if item_sample.checkState():
                                                samples_selected = 1
                                                new_item_sample = _clone_sample_item(item_sample)
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
                else:
                    message_box('Warning', 'Select experiment before adding measurements')
            else:
                message_box('Warning', 'Select experiment before adding measurements')
        else:
            message_box('Warning', 'Select experiment before adding measurements')



    # def _create_measurement(self, parent):


    '''
    Dealing with services
    '''
    def create_service(self):
        #parse parameters
        service_params = dict()
        for i in range(len(self.service_parameter_values)):
            variable = self.service_parameter_descriptions[i].text().split('=')[0]
            if (self.service_parameter_types[i] == int) or (self.service_parameter_types[i] == float):
                service_params[f'{variable}'] = f'{self.service_parameter_values[i].value()}'
            elif (self.service_parameter_types[i] == bool):
                service_params[f'{variable}'] = f'{bool(self.service_parameter_values[i].checkState())}'
            elif (self.service_parameter_types[i] == str):
                service_params[f'{variable}'] = f'{self.service_parameter_values[i].text()}'
        service_plan=self.service_plan_funcs[self.comboBox_service_plan.currentText()]
        new_item_service = QtGui.QStandardItem(f'Service: {self.comboBox_service_plan.currentText()}')
        new_item_service.item_type = 'service'
        new_item_service.setIcon(icon_service)
        new_item_service.service_plan = service_plan
        new_item_service.service_params = service_params

        if self.treeView_batch.model().rowCount():
            if self.treeView_batch.selectedIndexes():
                selected_index = self.treeView_batch.selectedIndexes()[0]
                index = selected_index.row()
                item = self.model_batch.itemFromIndex(selected_index)
                # New code starts here
                if item.item_type == 'sample':
                    parent_item = item.parent()
                    if parent_item.item_type == 'scan':
                        parent_item.insertRow(index,new_item_service)
                        new_item_service.setCheckable(False)
                        new_item_service.setEditable(False)
                        self.treeView_batch.expand(self.model_batch.indexFromItem(parent_item))

                # if item.item_type == 'experiment':
                #     item.appendRow(new_item_service)
                # elif parent.item_type == 'sample':
                #     item.insertRow(0, new_item_service)



    def batch_info(self):
        if self.treeView_batch.model().rowCount():
            if self.treeView_batch.selectedIndexes():
                selected_index = self.treeView_batch.selectedIndexes()[0]
                item = self.model_batch.itemFromIndex(selected_index)
                if item.item_type == 'service':
                    message_box(f'Batch element: {item.item_type}')

    def populate_service_parameters(self, index):
        for i in range(len(self.service_parameter_values)):
            self.gridLayout_service_parameters.removeWidget(self.service_parameter_values[i])
            self.gridLayout_service_parameters.removeWidget(self.service_parameter_descriptions[i])
            self.service_parameter_values[i].deleteLater()
            self.service_parameter_descriptions[i].deleteLater()
        service_plan_func = self.service_plan_funcs[self.comboBox_service_plan.currentText()]

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
        if self.treeView_batch.model().rowCount() and self.treeView_batch.selectedIndexes():
            parent = self.model_batch.itemFromIndex(self.treeView_batch.selectedIndexes()[0])
            if (parent.item_type == 'experiment') and (self.listView_scans.model() is not None):
                for index in range(self.listView_scans.model().rowCount()):
                    item_scan = self.listView_scans.model().item(index)
                    if item_scan.checkState():
                        new_item_scan = _clone_scan_item(item_scan)
                        #calculate_map

                        if self.radioButton_sample_map_1D.isChecked():
                            x_coord = np.linspace(self.spinBox_sample_x_map_start.value(),self.spinBox_sample_x_map_end.value(),
                                                int(self.spinBox_sample_x_map_steps.value()))
                            y_coord = np.linspace(self.spinBox_sample_y_map_start.value(),self.spinBox_sample_y_map_end.value(),
                                                int(self.spinBox_sample_x_map_steps.value()))
                            xy_coord = np.column_stack((x_coord,y_coord))

                        elif self.radioButton_sample_map_2D.isChecked():
                            x_coord = np.ndarray(0)
                            y_coord = np.ndarray(0)
                            y_points = np.linspace(self.spinBox_sample_y_map_start.value(), self.spinBox_sample_y_map_end.value(),
                                                  int(self.spinBox_sample_y_map_steps.value()))

                            if int(self.spinBox_sample_y_map_steps.value()) == 0:
                                message_box('Warning', 'Select nonzero number of steps ')
                                return
                            for i in range(int(self.spinBox_sample_y_map_steps.value())):
                                x_line = np.linspace(self.spinBox_sample_x_map_start.value(),self.spinBox_sample_x_map_end.value(),
                                                int(self.spinBox_sample_x_map_steps.value()))

                                y_line = np.ones(len(x_line))*(y_points[i])

                                x_coord = np.append(x_coord, x_line)
                                y_coord = np.append(y_coord, y_line)

                            xy_coord = np.column_stack((x_coord, y_coord))
                        print(xy_coord)

                        if self.lineEdit_map_name.text():
                            for index in range(len(xy_coord)):
                                x = xy_coord[index, 0]
                                y = xy_coord[index, 1]
                                name = f'{self.lineEdit_map_name.text()} at {x:.3f} {y:.3f}'

                                item = QtGui.QStandardItem(name)
                                new_item_scan.appendRow(item)
                                item.setDropEnabled(False)
                                item.item_type = 'sample'
                                item.setEditable(False)
                                item.x = x
                                item.y = y
                                item.name = name
                                item.comment = self.lineEdit_map_comment.text()
                                item.setIcon(icon_sample)
                        else:
                            message_box('Warning', 'Select nonzero number of steps ')

                        parent.appendRow(new_item_scan)
                        new_item_scan.setCheckable(False)
                        new_item_scan.setEditable(False)


                    self.treeView_batch.expand(self.model_batch.indexFromItem(parent))

            for index in range(parent.rowCount()):
                self.treeView_batch.expand(self.model_batch.indexFromItem(parent.child(index)))
                self.treeView_batch.setModel(self.model_batch)
        else:
            message_box('Warning','Select experiment before adding map')

    def move_to_sample(self):
            sender_object = QObject().sender()
            selection = sender_object.selectedIndexes()
            if selection != []:
                index = sender_object.currentIndex()
                item = sender_object.model().item(index.row())
                ret = question_message_box(self, 'Moving to sample', 'Are you sure?')
                if ret:
                    self.RE(bps.mv(self.sample_positioner.sample_stage.x, item.x))
                    self.RE(bps.mv(self.sample_positioner.sample_stage.y, item.y))

    def sample_context_menu(self,QPos):
        menu = QMenu()
        modify = menu.addAction("&Modify")
        move_to_sample = menu.addAction("Mo&ve to sample")
        parentPosition = self.listView_samples.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition+QPos)
        action = menu.exec_()
        if action == modify:
            self.modify_item()
        elif action == move_to_sample:
            self.move_to_sample()

    def scan_context_menu(self,QPos):
        menu = QMenu()
        modify = menu.addAction("&Modify")
        parentPosition = self.listView_scans.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition+QPos)
        action = menu.exec_()
        if action == modify:
            self.modify_item()

    def scan_batch_menu(self,QPos):
        menu = QMenu()
        modify = menu.addAction("&Modify")
        copy = menu.addAction("&Copy")
        paste = menu.addAction("&Paste")

        parentPosition = self.treeView_batch.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition+QPos)
        action = menu.exec_()
        if action == modify:
            self.modify_item()
        elif action == copy:
            pass
        elif action == paste:
            pass


    def enable_user_position_input(self):
        self.spinBox_sample_x.setEnabled(not self.checkBox_auto_position.isChecked())
        self.spinBox_sample_y.setEnabled(not self.checkBox_auto_position.isChecked())
        self.push_get_sample_position.setEnabled(not self.checkBox_auto_position.isChecked())






