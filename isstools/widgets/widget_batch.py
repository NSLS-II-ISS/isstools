import sys

import pkg_resources
from PyQt5 import uic
from bluesky.plan_stubs import mv
from xas.trajectory import trajectory_manager
from isstools.widgets import widget_batch_manual
from isstools.widgets import widget_autopilot
from isstools.dialogs.BasicDialogs import message_box
from random import random
from isstools.batch.autopilot_routines import TrajectoryStack

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_batch.ui')


class UIBatch(*uic.loadUiType(ui_path)):
    def __init__(self,
                 plan_funcs,
                 service_plan_funcs,
                 hhm,
                 RE,
                 sample_stage,
                 parent_gui,
                 motors_dict,
                 camera_dict,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.plan_funcs = plan_funcs
        self.service_plan_funcs = service_plan_funcs
        self.RE = RE
        self.hhm = hhm
        self.sample_stage = sample_stage
        self.parent_gui = parent_gui

        self.widget_batch_manual = widget_batch_manual.UIBatchManual(plan_funcs,
                                                                     service_plan_funcs,
                                                                     hhm,
                                                                     sample_stage=sample_stage
                                                                     )
        self.layout_batch_manual.addWidget(self.widget_batch_manual)

        self.push_run_batch.clicked.connect(self.run_batch)

    def run_batch(self, testing=False):
        print('[Batch scan] Starting...')
        batch = self.widget_batch_manual.treeView_batch.model()
        self.RE(self.batch_parse_and_run(self.hhm, self.sample_stage, batch, self.plan_funcs, testing=testing))


    def randomize_position(self):
        if self.widget_batch_manual.checkBox_randomize.isChecked():
            delta_x = (random() - 0.5) * self.widget_batch_manual.spinBox_randomize_step.value()*2
            delta_y = (random() - 0.5) * self.widget_batch_manual.spinBox_randomize_step.value()*2
        else:
            delta_x = 0
            delta_y = 0

        print(f'>>>>>>>>>>>>>>>>>>> {delta_x}')
        print(f'>>>>>>>>>>>>>>>>>>> {delta_y}')
        return delta_x, delta_y


    def batch_parse_and_run(self, hhm, sample_stage, batch, plans_dict, testing=False):
        #sample_stage = None
        sys.stdout = self.parent_gui.emitstream_out
        # tm = trajectory_manager(hhm)
        traj_stack = TrajectoryStack(hhm)
        for ii in range(batch.rowCount()): # go through all experiments
            experiment = batch.item(ii)
            repeat = experiment.repeat
            for indx in range(repeat): # repeat as needed
                if repeat > 1:
                    exper_index = f'{(indx + 1):04d}'
                else:
                    exper_index = ''
                for jj in range(experiment.rowCount()): # go inside expeirmrnt and go through its contents
                    step = experiment.child(jj)
                    if step.item_type == 'sample':
                        sample = step
                        #randomization
                        delta_x, delta_y = self.randomize_position()
                        if testing:
                            print('would have moved there', sample.x + delta_x, sample.y + delta_y)
                        else:
                            yield from mv(sample_stage.x, sample.x + delta_x, sample_stage.y, sample.y + delta_y)

                        for kk in range(sample.rowCount()):
                            child_item = sample.child(kk)
                            if child_item.item_type == 'scan':
                                scan=child_item


                                plan = plans_dict[scan.scan_type]
                                sample_name = '{} {} {}'.format(sample.name, scan.name, exper_index)
                                self.label_batch_step.setText(sample_name)
                                kwargs = {'name': sample_name,
                                          'comment': '',
                                          'delay': scan.delay,
                                          'n_cycles': scan.repeat,
                                          'stdout': self.parent_gui.emitstream_out,
                                          'autofoil' : scan.autofoil}
                                if testing:
                                    print('would have changed traj', scan.trajectory)

                                else:
                                    traj_stack.set_traj(scan.trajectory)

                                # traj_index = traj_stack.which_slot_for_traj(scan.trajectory)
                                # if self.hhm.lut_number_rbv.read()['hhm_lut_number_rbv']['value'] != traj_index:
                                #     if traj_index:
                                #         traj_stack.set_traj(traj_index)
                                #     else:
                                if testing:
                                    print('would have done the plan', scan.name)
                                else:
                                    yield from plan(**kwargs)

                            elif child_item.item_type == 'service':
                                service = child_item
                                kwargs = {'stdout': self.parent_gui.emitstream_out}
                                if testing:
                                    print('would have done service', service.name)
                                else:
                                    yield from service.service_plan(**service.service_params, **kwargs)

                    elif step.item_type == 'scan':
                        scan = step
                        # traj_index = scan.trajectory
                        # if self.hhm.lut_number_rbv.read()['hhm_lut_number_rbv']['value'] != traj_index + 1:
                        #     tm.init(traj_index + 1)
                        if testing:
                            print('would have set the traj', scan.trajectory)
                        else:
                            traj_stack.set_traj(scan.trajectory)

                        for kk in range(step.rowCount()):
                            child_item = scan.child(kk)
                            if child_item.item_type == 'sample':
                                sample=child_item
                                # randomization
                                delta_x, delta_y = self.randomize_position()

                                if testing:
                                    print('would have moved there', sample.x + delta_x, sample.y + delta_y)
                                else:
                                    yield from mv(sample_stage.x, sample.x + delta_x, sample_stage.y,
                                                  sample.y + delta_y)

                                plan = plans_dict[scan.scan_type]

                                sample_name = '{} {} {}'.format(sample.name, scan.name, exper_index)
                                self.label_batch_step.setText(sample_name)
                                kwargs = {'name': sample_name,
                                          'comment': '',
                                          'delay': scan.delay,
                                          'n_cycles': scan.repeat,
                                          'stdout': self.parent_gui.emitstream_out}
                                if testing:
                                    print('would have done the scan', sample.name)
                                else:
                                    yield from plan(**kwargs)

                            elif child_item.item_type == 'service':
                                service = child_item
                                kwargs = {'stdout': self.parent_gui.emitstream_out}
                                if testing:
                                    print('would have done service', child_item.name)
                                else:
                                    yield from service.service_plan(**service.service_params, **kwargs)

                    elif step.item_type == 'service':
                        kwargs = {'stdout': self.parent_gui.emitstream_out}
                        if testing:
                            print('would have done service', step.name)
                        else:
                            yield from step.service_plan(**step.service_params, **kwargs)

        self.label_batch_step.setText('idle')