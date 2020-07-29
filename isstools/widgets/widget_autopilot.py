import os
import sys

import pkg_resources
import json
from PyQt5 import uic, QtCore, QtWidgets, QtGui
from PyQt5.Qt import QObject
from bluesky.plan_stubs import mv
from isstools.batch.table_batch import XASBatchExperiment
from xas.trajectory import trajectory_manager
from isstools.widgets import widget_batch_manual
from isscloudtools import gdrive, initialize
import numpy as np
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_autopilot.ui')
from isstools.dialogs.BasicDialogs import message_box
from xas.trajectory import trajectory, trajectory_manager


from isstools.batch.autopilot_routines import Experiment, TrajectoryStack




class UIAutopilot(*uic.loadUiType(ui_path)):
    def __init__(self,
                 # plan_funcs,
                 # service_plan_funcs,
                 # motors_dict,
                 hhm,
                 RE,
                 # db,
                 # sample_stage,
                 # parent_gui,

                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        #self.addCanvas()
        #
        # self.plan_funcs = plan_funcs
        # self.service_plan_funcs = service_plan_funcs
        # self.plan_funcs_names = plan_funcs.keys()
        # self.service_plan_funcs_names = service_plan_funcs.keys()
        #
        # self.motors_dict = motors_dict
        # self.mot_list = self.motors_dict.keys()
        # self.mot_sorted_list = list(self.mot_list)
        # self.mot_sorted_list.sort()
        self.hhm = hhm
        # self.traj_manager = trajectory_manager(hhm)
        #

        self.RE = RE

        self.service = initialize.get_gdrive_service()
        self.service_sheets = initialize.get_gsheets_service()
        self.sheet = self.service_sheets.spreadsheets()
        # self.db = db
        # self.sample_stage = sample_stage
        # self.parent_gui = parent_gui
        #
        # self.batch_mode_uids = []
        # self.sample_stage = sample_stage
        #
        # self.widget_batch_manual = widget_batch_manual.UIBatchManual(self.plan_funcs,
        #                                                              self.service_plan_funcs,
        #                                                              self.hhm,
        #                                                              self.motors_dict,
        #                                                              sample_stage=self.sample_stage
        #                                                             )
        #
        # self.layout_batch_manual.addWidget(self.widget_batch_manual)
        #
        #
        #

        #
        # self.layout_batch_manual
        #print
        # self.batch_running = False
        # self.batch_pause = False
        # self.batch_abort = False
        # self.batch_results = {}
        #
        #
        #
        self.push_proposal_list.clicked.connect(self.get_proposal_list_gdrive)
        self.push_select_proposals.clicked.connect(self.select_proposals)
        self.push_run_autopilot.clicked.connect(self.run_autopilot)
        #
        #
        self.listWidget_proposals.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
        self.element_list =[i['symbol'] for i in json.loads(json_data)]
        #
        # #setting up sample table
        # pushButtons_load = [self.pushButton_load_sample_def_11,
        #                     self.pushButton_load_sample_def_12,
        #                     self.pushButton_load_sample_def_13,
        #                     self.pushButton_load_sample_def_21,
        #                     self.pushButton_load_sample_def_22,
        #                     self.pushButton_load_sample_def_23,
        #                     self.pushButton_load_sample_def_31,
        #                     self.pushButton_load_sample_def_32,
        #                     self.pushButton_load_sample_def_33
        #                     ]
        # for button in  pushButtons_load:
        #     button.clicked.connect(self.load_sample_definition)
        # #%getattr(self, f'pushButton_show_sample_def_{i}')
        # pushButtons_show = [self.pushButton_show_sample_def_11,
        #                     self.pushButton_show_sample_def_12,
        #                     self.pushButton_show_sample_def_13,
        #                     self.pushButton_show_sample_def_21,
        #                     self.pushButton_show_sample_def_22,
        #                     self.pushButton_show_sample_def_23,
        #                     self.pushButton_show_sample_def_31,
        #                     self.pushButton_show_sample_def_32,
        #                     self.pushButton_show_sample_def_33
        #                     ]
        # for button in pushButtons_show:
        #     button.clicked.connect(self.show_sample_definition)
        #
        # self.coordinates = ['11',
        #                     '12',
        #                     '13',
        #                     '21',
        #                     '22',
        #                     '23',
        #                     '31',
        #                     '32',
        #                     '33']
        # for x in self.coordinates:
        #     getattr(self,'pushButton_update_reference_{}'.format(x)).clicked.connect(self.update_reference)
        #
        # self.push_run_spreadsheet_batch.clicked.connect(self.run_spreadsheet_batch)
        #
        #
        #
        # self.tableWidget_sample_def.setColumnCount(7)
        self.table_keys = ['Proposal', 'SAF', 'Sample holder ID', 'Sample #', 'Sample label', 'Comment', 'Composition',
                           'Element', 'Concentration', 'Edge','Energy', 'k-range', '# of scans' ]


        self.tableWidget_sample_def.setColumnCount(len(self.table_keys))
        self.tableWidget_sample_def.setHorizontalHeaderLabels(self.table_keys)


        # for j in range(7):
        #     self.tableWidget_sample_def.setColumnWidth(j,widths[j])
        # #doen setting table


    def get_proposal_list_gdrive(self):
        cycle = self.RE.md['cycle']
        year = self.RE.md['year']

        fid_year = gdrive.folder_exists_in_root(self.service, year)
        fid_cycle = gdrive.folder_exists(self.service, fid_year, cycle)
        files = gdrive.get_file_list(self.service, fid_cycle)['files']
        self.file_names = np.array([i['name'] for i in files])
        self.file_ids = np.array([i['id'] for i in files])

        if files:
            self.listWidget_proposals.clear()
            for file in files:
                self.listWidget_proposals.addItem(file['name'])
        else:
            message_box('Error','No proposal definition files found')


    def select_proposals(self):

        selected_items = (self.listWidget_proposals.selectedItems())
        selected_file_ids = []

        for item in selected_items:
            file_id = self.file_ids[item.text() == self.file_names]
            selected_file_ids.append(file_id[0])

        self.batch_experiment = []
        qtable_row_index = 0

        for file_id, name in zip(selected_file_ids, selected_items):
            result = self.sheet.values().get(spreadsheetId=file_id, range='Sheet1').execute()
            sheet_data = result['values']

            for i, row in enumerate(sheet_data):
                if i > 0: # skip the header
                    # sample_holder_id, sample_num, saf_num, sample_label, comment, composition, hazards = row[:6]
                    # 'Sample holder ID', 'Sample #', 'SAF #', 'Sample label', 'Comment', 'Composition', 'Hazards'
                    sample_info = [name.text()]+row[:6]
                    els = row[7::6]
                    el_concs = row[8::6]
                    edges = row[9::6]
                    energies = row[10::6]
                    kranges = row[11::6]
                    nscanss = row[12::6]

                    for el, el_conc, edge, energy, krange, nscans in zip(els, el_concs, edges, energies, kranges, nscanss):
                        if el in self.element_list: # check if the element exists

                            # create entry for the experimental plan
                            entry_list = sample_info + [el, el_conc, edge, energy, krange, nscans]
                            entry = {}
                            for key, value in zip(self.table_keys, entry_list):
                                entry[key] = value
                            self.batch_experiment.append(entry)

                            # update table in the widget
                            self.tableWidget_sample_def.insertRow(qtable_row_index)
                            for j, item in enumerate(entry_list):
                                self.tableWidget_sample_def.setItem(qtable_row_index, j, QtWidgets.QTableWidgetItem(item))
                            qtable_row_index += 1



    def run_autopilot(self):

        traj_stack = TrajectoryStack(self.hhm)

        for step in self.batch_experiment:
            # ['Proposal', 'SAF', 'Sample holder ID', 'Sample #', 'Sample label', 'Comment', 'Composition',
            #  'Element', 'Concentration', 'Edge', 'Energy', 'k-range', '# of scans']


            experiment = Experiment(step['Sample label'],
                                    step['Comment'],
                                    step['# of scans'],
                                    0, # delay
                                    step['Element'],
                                    step['Edge'],
                                    step['Energy'],
                                    -200, # preedge
                                    step['k-range'],
                                    10, # t1
                                    20 * step['k-range']/16) # t2

            traj_stack.set_traj(experiment.traj_signature)

            print('success')





    def define_trajectories(self):
        for experiment in self.batch_experiment:
            # d = self.experiment
            traj = trajectory(self.hhm)
            kwargs = dict(
                edge_energy=experiment['Energy'],
                offsets=([experiment['pre-edge start'], d['pre-edge stop'],
                          d['post-edge stop'], xray.k2e(d['k-range'], d['Energy']) - d['Energy']]),
                trajectory_type='Double Sine',
                dsine_preedge_duration=d['time 1'],
                dsine_postedge_duration=d['time 2'],
            )
            print(kwargs)
            traj.define(**kwargs)

            # Add some more parameters manually:
            traj.elem = d['Element']
            traj.edge = d['Edge']
            traj.e0 = d['Energy']

            traj.interpolate()
            traj.revert()
            self.trajectories.append(traj)

    def save_trajectories(self):
        for ut in self.unique_trajectories:
            filename = os.path.join(self.trajectory_folder, 'trajectory_{}.txt'.format(str(uuid.uuid4())[:8]))
            self.trajectory_filenames.append(filename)
            print(f'Saving {filename}...')
            np.savetxt(filename, ut.energy_grid, fmt='%.6f',
                       header=f'element: {ut.elem}, edge: {ut.edge}, E0: {ut.e0}')
            call(['chmod', '666', filename])

    def load_trajectories(self):
        offset = self.hhm.angle_offset.value
        print(offset)
        for i, traj_file in enumerate(self.trajectory_filenames):
            self.trajectory_manager.load(os.path.basename(traj_file),i+1,is_energy=True, offset=offset )


    # def retrieve_info_from_proposals(self):



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
        x_value = self.sample_stage.x.position
        y_value = self.sample_stage.y.position

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


    def abort_batch(self):
        if self.batch_running == True:
            self.batch_abort = True
            self.re_abort()

    def check_pause_abort_batch(self):
        if self.batch_abort:
            print('**** Aborting Batch! ****')
            raise Exception('Abort button pressed by user')
        elif self.batch_pause:
            self.label_batch_step.setText('[Paused] {}'.format(self.label_batch_step.text()))
            while self.batch_pause:
                QtCore.QCoreApplication.processEvents()

    def start_batch(self):
        print('[Launching Threads]')
        batch = self.widget_batch_manual.treeView_batch.model()
        self.RE(self.batch_parse_and_run(self.hhm, self.sample_stage, batch, self.plan_funcs))

    def batch_parse_and_run(self, hhm,sample_stage,batch,plans_dict):
        sys.stdout =  self.parent_gui.emitstream_out
        tm = trajectory_manager(hhm)
        for ii in range(batch.rowCount()):
            experiment = batch.item(ii)
            repeat=experiment.repeat
            for indx in range(repeat):
                exper_index = ''
                if repeat>1:
                    exper_index = f'{(indx+1):04d}'
                for jj in range(experiment.rowCount()):
                    print(experiment.rowCount())
                    step = experiment.child(jj)
                    if  step.item_type == 'sample':
                        sample = step
                        print('  ' + sample.name)
                        print('  ' + str(sample.x))
                        print('  ' + str(sample.y))
                        yield from mv(sample_stage.x, sample.x, sample_stage.y, sample.y)
                        #print(f'moving to {sample.x}, {sample y}')
                        for kk in range(sample.rowCount()):
                            scan = sample.child(kk)
                            traj_index= scan.trajectory
                            print('      ' + scan.scan_type)
                            plan = plans_dict[scan.scan_type]
                            sample_name =  '{} {} {}'.format(sample.name, scan.name, exper_index)
                            print(sample_name)
                            kwargs = {'name': sample_name,
                                      'comment': '',
                                      'delay': 0,
                                      'n_cycles': scan.repeat,
                                      'stdout': self.parent_gui.emitstream_out}
                            tm.init(traj_index+1)
                            yield from plan(**kwargs)
                    elif step.item_type == 'scan':
                        scan = step
                        traj_index = scan.trajectory
                        print('  ' + scan.scan_type)
                        tm.init(traj_index + 1)
                        for kk in range(step.rowCount()):
                            sample = scan.child(kk)
                            yield from mv(sample_stage.x, sample.x, sample_stage.y, sample.y)
                            plan = plans_dict[scan.scan_type]
                            print('     ' + sample.name)
                            print('     ' + str(sample.x))
                            print('     ' + str(sample.y))
                            sample_name = '{} {} {}'.format(sample.name, scan.name, exper_index)
                            print(sample_name)
                            kwargs = {'name': sample_name,
                                      'comment': '',
                                      'delay': 0,
                                      'n_cycles': repeat,
                                      'stdout': self.parent_gui.emitstream_out}

                            yield from plan(**kwargs)
                    elif step.item_type == 'service':
                        yield from step.service_plan(**step.service_params)



