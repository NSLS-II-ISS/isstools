import inspect
import re
import pkg_resources
from PyQt5 import uic, QtGui, QtCore, QtWidgets


from isstools.elements import elements
from isstools.trajectory.trajectory import trajectory_manager
from isstools.batch.batch import BatchManager


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
                 motors_dict,
                 sample_stage = None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        #self.addCanvas()

        self.plan_funcs = plan_funcs
        self.service_plan_funcs = service_plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        self.service_plan_funcs_names = [plan.__name__ for plan in service_plan_funcs]
        self.sample_stage = sample_stage
        self.motors_dict = motors_dict
        self.mot_list = self.motors_dict.keys()
        self.mot_sorted_list = list(self.mot_list)
        self.mot_sorted_list.sort()
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
        self.push_get_sample.clicked.connect(self.get_sample_pos)
        self.listView_samples.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)


        self.model_scans = QtGui.QStandardItemModel(self)
        self.push_create_scan.clicked.connect(self.create_new_scan)
        self.push_delete_scan.clicked.connect(self.delete_scan)
        self.listView_scans.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)

        self.push_batch_delete.clicked.connect(self.delete_batch_element)
        self.push_create_measurement.clicked.connect(self.create_measurement)
        self.push_create_service.clicked.connect(self.create_service)

        self.comboBox_scans.addItems(self.plan_funcs_names)
        self.comboBox_services.addItems(self.service_plan_funcs_names)

        self.comboBox_services.currentIndexChanged.connect(self.populate_service_parameters)
        self.push_update_traj_list.clicked.connect(self.update_batch_traj)


        try:
            self.update_batch_traj()
        except OSError as err:
             print('Error loading:', err)

        self.last_lut = 0

        self.service_param1 = []
        self.service_param2 = []
        self.service_params_types = []
        self.populate_service_parameters(0)

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
            self.message_box_name_empty('Sample name is empty')

    def get_sample_pos(self):
        x_value = self.sample_stage.x.position
        y_value = self.sample_stage.y.position
        self.spinBox_sample_x.setValue(x_value)
        self.spinBox_sample_y.setValue(y_value)

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
            self.message_box_name_empty('Scan name is empty')


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
        service_params = []
        print(service_params)
        print(len(self.service_param1))
        for i in range(len(self.service_param1)):
            print(f'Cycle {i}')
            variable = self.service_param2[i].text().split('=')[0]
            if (self.service_params_types[i] == int) or (self.service_params_types[i] == float):
                service_params.append(f'{variable} = {self.service_param1[i].value()}')
                print('int')
            elif (self.service_params_types[i] == bool):
                service_params.append(f'{variable} = {bool(self.service_param1[i].checkState())}')
                print('bool')
            elif (self.service_params_types[i] == str):
                service_params.append(f'{variable} = {self.service_param1[i].text()}')
                print('str')
        print(service_params)


        new_item_service = QtGui.QStandardItem(f'Service: {self.comboBox_services.currentText()}')
        new_item_service.item_type = 'service'
        new_item_service.setIcon(icon_service)

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







    def update_loop_values(self, text):
        for motor in self.motors_dict:
            if self.comboBox_sample_loop_motor.currentText() == self.motors_dict[motor]['name']:
                curr_mot = self.motors_dict[motor]['object']
                break
        if self.radioButton_sample_rel.isChecked():
            if curr_mot.connected == True:
                self.push_add_sample_loop.setEnabled(True)
                self.spinBox_motor_range_start.setValue(-0.5)
                self.spinBox_motor_range_stop.setValue(0.5)
                self.spinBox_motor_range_step.setValue(0.25)
                self.push_add_sample_loop.setEnabled(True)
            else:
                self.push_add_sample_loop.setEnabled(False)
                self.spinBox_motor_range_start.setValue(0)
                self.spinBox_motor_range_stop.setValue(0)
                self.spinBox_motor_range_step.setValue(0.025)
        else:
            if curr_mot.connected == True:
                self.push_add_sample_loop.setEnabled(True)
                curr_pos = curr_mot.read()[curr_mot.name]['value']
                self.spinBox_motor_range_start.setValue(curr_pos - 0.1)
                self.spinBox_motor_range_stop.setValue(curr_pos + 0.1)
                self.spinBox_motor_range_step.setValue(0.025)
            else:
                self.push_add_sample_loop.setEnabled(False)
                self.spinBox_motor_range_start.setValue(0)
                self.spinBox_motor_range_stop.setValue(0)
                self.spinBox_motor_range_step.setValue(0.025)

    def restore_add_loop(self, value):
        if value:
            self.push_add_sample_loop.setEnabled(True)

    def set_loop_values(self, checked):
        if checked:
            self.spinBox_motor_range_start.setValue(-0.5)
            self.spinBox_motor_range_stop.setValue(0.5)
            self.spinBox_motor_range_step.setValue(0.25)
            self.push_add_sample_loop.setEnabled(True)
        else:
            motor_text = self.comboBox_sample_loop_motor.currentText()
            self.update_loop_values(motor_text)




    def populate_service_parameters(self, index):
        for i in range(len(self.service_param1)):
            self.gridLayout_services.removeWidget(self.service_param1[i])
            self.gridLayout_services.removeWidget(self.service_param2[i])

            self.service_param1[i].deleteLater()
            self.service_param2[i].deleteLater()

        self.service_param1 = []
        self.service_param2 = []

        self.service_params_types = []
        plan_func = self.service_plan_funcs[index]
        signature = inspect.signature(plan_func)


        for i in range(0, len(signature.parameters)):
            default = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))

            if default == str(signature.parameters[list(signature.parameters)[i]]):
                default = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))

            self.add_parameters(list(signature.parameters)[i], default,
                                signature.parameters[list(signature.parameters)[i]].annotation,
                                grid=self.gridLayout_services,
                                params=[self.service_param1, self.service_param2])
            self.service_params_types.append(signature.parameters[list(signature.parameters)[i]].annotation)


    def add_parameters(self, name, default, annotation, grid, params):
        rows = int(grid.count() / 2)
        param1 = None
        def_val = ''
        if default.find('=') != -1:
            def_val = re.sub(r'.*=', '', default)
        if annotation == int:
            param1 = QtWidgets.QSpinBox()
            param1.setMaximum(100000)
            param1.setMinimum(-100000)
            def_val = int(def_val)
            param1.setValue(def_val)
        elif annotation == float:
            param1 = QtWidgets.QDoubleSpinBox()
            param1.setMaximum(100000)
            param1.setMinimum(-100000)
            def_val = float(def_val)
            param1.setValue(def_val)
        elif annotation == bool:
            param1 = QtWidgets.QCheckBox()
            if def_val == 'True':
                def_val = True
            else:
                def_val = False
            param1.setCheckState(def_val)
            param1.setTristate(False)
        elif annotation == str:
            param1 = QtWidgets.QLineEdit()
            def_val = str(def_val)
            param1.setText(def_val)

        if param1 is not None:
            param2 = QtWidgets.QLabel(default)

            grid.addWidget(param1, rows, 1, QtCore.Qt.AlignTop)
            grid.addWidget(param2, rows, 2, QtCore.Qt.AlignTop)
            params[0].append(param1)
            params[1].append(param2)


    def update_batch_traj(self):
        self.trajectories = self.traj_manager.read_info(silent=True)
        self.comboBox_lut.clear()
        self.comboBox_lut.addItems(
            ['{}-{}'.format(lut, self.trajectories[lut]['name']) for lut in self.trajectories if lut != '9'])



    def check_pause_abort_batch(self):
        if self.batch_abort:
            print('**** Aborting Batch! ****')
            raise Exception('Abort button pressed by user')
        elif self.batch_pause:
            self.label_batch_step.setText('[Paused] {}'.format(self.label_batch_step.text()))
            while self.batch_pause:
                QtCore.QCoreApplication.processEvents()



    def message_box_name_empty(self, message):
        messageBox = QtWidgets.QMessageBox()
        messageBox.setText(message)
        messageBox.addButton(QtWidgets.QPushButton('OK'), QtWidgets.QMessageBox.YesRole)
        messageBox.setWindowTitle("Warning")
        ret = messageBox.exec_()
        return ret




