import sys

import pkg_resources
from PyQt5 import uic
from bluesky.plan_stubs import mv
from xas.trajectory import trajectory_manager
from isstools.widgets import widget_batch_manual

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_batch_mode_new.ui')


class UIBatchModeNew(*uic.loadUiType(ui_path)):
    def __init__(self,
                 plan_funcs,
                 service_plan_funcs,
                 hhm,
                 RE,
                 sample_stage,
                 parent_gui,
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
        self.push_run_batch_manual.clicked.connect(self.run_batch_manual)

    def run_batch_manual(self):
        print('[Launching Threads]')
        batch = self.widget_batch_manual.treeView_batch.model()
        self.RE(self.batch_parse_and_run(self.hhm, self.sample_stage, batch, self.plan_funcs))

    def batch_parse_and_run(self, hhm, sample_stage, batch, plans_dict):
        sys.stdout = self.parent_gui.emitstream_out
        tm = trajectory_manager(hhm)
        for ii in range(batch.rowCount()):
            experiment = batch.item(ii)
            repeat = experiment.repeat
            for indx in range(repeat):
                if repeat > 1:
                    exper_index = f'{(indx+1):04d}'
                else:
                    exper_index = ''
                for jj in range(experiment.rowCount()):
                    print(experiment.rowCount())
                    step = experiment.child(jj)
                    if step.item_type == 'sample':
                        sample = step
                        #self.label_batch_step.setText (sample.name)
                        #print('  ' + str(sample.x))
                        #print('  ' + str(sample.y))
                        yield from mv(sample_stage.x, sample.x, sample_stage.y, sample.y)
                        # print(f'moving to {sample.x}, {sample y}')
                        for kk in range(sample.rowCount()):
                            scan = sample.child(kk)
                            traj_index = scan.trajectory
                            #print('      ' + scan.scan_type)
                            plan = plans_dict[scan.scan_type]
                            sample_name = '{} {} {}'.format(sample.name, scan.name, exper_index)
                            self.label_batch_step.setText(sample_name)
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
                            self.label_batch_step.setText(sample_name)
                            kwargs = {'name': sample_name,
                                      'comment': '',
                                      'delay': 0,
                                      'n_cycles': scan.repeat,
                                      'stdout': self.parent_gui.emitstream_out}

                            yield from plan(**kwargs)
                    elif step.item_type == 'service':
                        yield from step.service_plan(**step.service_params)
        self.label_batch_step.setText('idle')