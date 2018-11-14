import inspect

import re
import pkg_resources
from PyQt5 import uic, QtWidgets, QtCore

from PyQt5 import uic, QtGui, QtCore, QtWidgets
from PyQt5.QtCore import QThread
from PyQt5.Qt import QSplashScreen, QObject

import os
import sys

from isstools.trajectory.trajectory import trajectory_manager
from isstools.batch.batch import BatchManager
from isstools.batch.table_batch import XASBatchExperiment
from isstools.widgets import widget_batch_manual
from bluesky.plan_stubs import mv


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_batch_mode_new.ui')


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
                 *args,sample_stage = None, **kwargs):

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
        self.sample_stage = sample_stage

        self.widget_batch_manual = widget_batch_manual.UIBatchManual(self.plan_funcs,
                                                                     self.service_plan_funcs,
                                                                     self.hhm,
                                                                     self.motors_dict,
                                                                     sample_stage=self.sample_stage
                                                                    )

        self.layout_batch_manual.addWidget(self.widget_batch_manual)





        self.layout_batch_manual

        self.batch_running = False
        self.batch_pause = False
        self.batch_abort = False
        self.batch_results = {}
        self.push_batch_pause.clicked.connect(self.pause_unpause_batch)
        self.push_batch_abort.clicked.connect(self.abort_batch)



        self.push_run_batch_manual.clicked.connect(self.start_batch)




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

    def check_pause_abort_batch(self):
        if self.batch_abort:
            print('**** Aborting Batch! ****')
            raise Exception('Abort button pressed by user')
        elif self.batch_pause:
            self.label_batch_step.setText('[Paused] {}'.format(self.label_batch_step.text()))
            while self.batch_pause:
                QtCore.QCoreApplication.processEvents()

    def re_abort(self):
        if self.RE.state != 'idle':
            self.RE.abort()
            self.RE.is_aborted = True

    def start_batch(self):
        print('[Launching Threads]')
        self.run_batch()

    def run_batch(self, print_only=False):
        batch = self.widget_batch_manual.treeView_batch.model()
        plans_dict = {x.__name__: x for x in  self.plan_funcs}
        self.RE(self.batch_parse_and_run(self.hhm, self.sample_stage, batch, plans_dict))

    def batch_parse_and_run(self, hhm,sample_stage,batch,plans_dict ):
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



