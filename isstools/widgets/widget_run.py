import datetime
from timeit import default_timer as timer

import numpy as np
import pkg_resources
from PyQt5 import uic, QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from xas.xray import generate_energy_grid

from isstools.dialogs.BasicDialogs import question_message_box, message_box
from isstools.elements.figure_update import update_figure, setup_figure

from bluesky.callbacks import LivePlot

from ..elements.liveplots import XASPlot#, XASPlotX
from ..elements.elements import remove_special_characters

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_run.ui')



class UIRun(*uic.loadUiType(ui_path)):
    # plansAdded = QtCore.pyqtSignal()

    def __init__(self,
                 scan_manager = None,
                 sample_manager=None,
                 plan_processor=None,
                 sample_env_dict=None,
                 hhm=None,
                 johann_spectrometer_motor=None,
                 parent=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.scan_manager = scan_manager
        self.sample_manager = sample_manager
        self.plan_processor = plan_processor
        self.sample_env_dict = sample_env_dict
        self.hhm = hhm
        self.johann_spectrometer_motor = johann_spectrometer_motor
        self.push_run_scan.clicked.connect(self.run_scan)
        self.push_run_test_scan.clicked.connect(self.run_test_scan)
        self.push_queue_scan.clicked.connect(self.queue_scan)
        self.plan_processor.status_update_signal.connect(self.handle_execution_buttons)
        self.update_scan_defs()
        self.update_sample_defs()
        # self.update_conditions()

        self.figure, self.canvas, self.toolbar = setup_figure(self, self.layout_plot)
        self.figure.ax1 = self.figure.ax
        self.figure.ax2 = self.figure.ax.twinx()
        self.figure.ax3 = self.figure.ax.twinx()

    def update_scan_defs(self):
        scan_defs = [scan['scan_def'] for scan in self.scan_manager.scan_list_local]
        self.comboBox_scan_defs.clear()
        self.comboBox_scan_defs.addItems(scan_defs)

    def update_sample_defs(self):
        sample_defs = [s.name for s in self.sample_manager.samples]
        self.comboBox_sample_defs.clear()
        self.comboBox_sample_defs.addItems(sample_defs)

    # def update_conditions(self):
    #     cond_tuples = [(k, v['shortcut']) for k, v in self.sample_env_dict.items()]
    #     conds_keys = [i[0] for i in cond_tuples]
    #     conds_shortcuts = [i[1] for i in cond_tuples]
    #     self.comboBox_condition.clear()
    #     self.comboBox_condition.addItems(conds_shortcuts)

    def make_plans(self):
        sample_idx = self.comboBox_sample_defs.currentIndex()
        scan_idx = self.comboBox_scan_defs.currentIndex()

        # name = self.lineEdit_exp_name.text()

        sample_name = self.sample_manager.sample_name_at_index(sample_idx)
        sample_comment = self.sample_manager.sample_comment_at_index(sample_idx)
        sample_uid = self.sample_manager.sample_uid_at_index(sample_idx)
        metadata = {'sample_uid' : sample_uid, 'sample_name' : sample_name, 'sample_comment' : sample_comment}

        suffix = self.lineEdit_suffix.text()
        if (suffix == '') or (suffix.isspace()):
            name = sample_name
        else:
            name = f'{sample_name} {suffix}'

        # name = remove_special_characters(name)
        comment = self.lineEdit_exp_comment.text()
        repeat = self.spinBox_scan_repeat.value()
        delay = self.spinBox_scan_delay.value()
        return self.scan_manager.generate_plan_list(name, comment, repeat, delay, scan_idx, metadata=metadata)
        # if name:
        #
        # else:
        #     message_box('Error', 'Please provide the name for the sample')

    def _queue_scan(self, add_at='tail'):
        plans = self.make_plans()
        if plans:
            self.plan_processor.add_plans(plans, add_at=add_at)

    def queue_scan(self):
        self._queue_scan()

    def run_scan(self):
        self._queue_scan(add_at='head')
        self.plan_processor.run()

    def run_test_scan(self):
        suffix = self.lineEdit_suffix.text()
        repeat = self.spinBox_scan_repeat.value()
        self.lineEdit_suffix.setText(f'{suffix} test')
        self.spinBox_scan_repeat.setValue(1)
        self._queue_scan(add_at='head')
        self.lineEdit_suffix.setText(suffix)
        self.spinBox_scan_repeat.setValue(repeat)
        self.plan_processor.run()

    def handle_execution_buttons(self):
        if self.plan_processor.status == 'idle':
            self.push_run_test_scan.setEnabled(True)
            self.push_run_scan.setEnabled(True)
        elif (self.plan_processor.status == 'running') or (self.plan_processor.status == 'paused'):
            self.push_run_test_scan.setEnabled(False)
            self.push_run_scan.setEnabled(False)

    def draw_interpolated_data(self, df):
        update_figure([self.figure.ax2, self.figure.ax1, self.figure.ax3], self.toolbar, self.canvas)
        if 'i0' in df and 'it' in df and 'energy' in df:
            transmission = np.array(np.log(df['i0'] / df['it']))
        if 'i0' in df and 'iff' in df and 'energy' in df:
            fluorescence = np.array(df['iff'] / df['i0'])
        if 'it' in df and 'ir' in df and 'energy' in df:
            reference = np.array(np.log(df['it'] / df['ir']))

        energy = np.array(df['energy'])
        edge = int(len(energy) * 0.02)
        #print(f'Before drawing in draw_interpolated_data:{__file__}')
        self.figure.ax1.plot(energy[edge:-edge], transmission[edge:-edge], color='r', label='Transmission')
        #print(f'After drawing in draw_interpolated_data:{__file__}')
        self.figure.ax1.legend(loc=2)
        self.figure.ax2.plot(energy[edge:-edge], fluorescence[edge:-edge], color='g', label='Total fluorescence')
        self.figure.ax2.legend(loc=1)
        self.figure.ax3.plot(energy[edge:-edge], reference[edge:-edge], color='b', label='Reference')
        self.figure.ax3.legend(loc=3)
        self.canvas.draw_idle()

    def make_xasplot_func(self, plan_name, plan_kwargs):

        detectors = plan_kwargs['detectors']

        if plan_name in ['step_scan_plan', 'step_scan_von_hamos_plan', 'step_scan_johann_herfd_plan']:
            motor_name = self.hhm.energy.name
        elif plan_name in ['step_scan_johann_xes_plan']:
            motor_name = self.johann_spectrometer_motor.energy.name
        elif plan_name in ['fly_scan_plan', 'fly_scan_von_hamos_plan', 'fly_scan_johann_herfd_plan']:
            return []
        else:
            motor_name = 'time'

        update_figure([self.figure.ax2, self.figure.ax1, self.figure.ax3], self.toolbar, self.canvas)

        xasplot_list = []
        liveplot_kwargs_list = [{'num_name': 'apb_ave_ch1_mean', 'den_name': 'apb_ave_ch2_mean', 'result_name': 'Transmission',
                                'log': True, 'ax': self.figure.ax1, 'color': 'r', 'legend_keys': ['Transmission']},
                               {'num_name': 'apb_ave_ch2_mean', 'den_name': 'apb_ave_ch3_mean', 'result_name': 'Reference',
                                'log': True, 'ax': self.figure.ax2, 'color': 'b', 'legend_keys': ['Reference']},
                               {'num_name': 'apb_ave_ch4_mean', 'den_name': 'apb_ave_ch1_mean', 'result_name': 'PIPS TFY',
                                'log': False, 'ax': self.figure.ax3, 'color': 'g', 'legend_keys': ['PIPS TFY']}, ]
        if 'Pilatus 100k' in detectors:
            liveplot_kwargs_list.append(
                {'num_name': 'pil100k_stats1_total', 'den_name': 'apb_ave_ch1_mean', 'result_name': 'HERFD',
                 'log': False, 'ax': self.figure.ax3, 'color': 'm', 'legend_keys': ['HERFD']})
        if 'Xspress3' in detectors:
            liveplot_kwargs_list.append(
                {'num_name': 'xs_channel1_rois_roi01_value', 'den_name': 'apb_ave_ch2_mean', 'result_name': 'SDD',
                 'log': False, 'ax': self.figure.ax3, 'color': 'm', 'legend_keys': ['SDD']})
        for liveplot_kwargs in liveplot_kwargs_list:
            _xasplot = self._xasplot_from_dict(liveplot_kwargs, motor_name)
            xasplot_list.append(_xasplot)

        return xasplot_list

    def _xasplot_from_dict(self, kwargs, motor_name):
        return XASPlot(kwargs['num_name'], kwargs['den_name'], kwargs['result_name'], motor_name, log=kwargs['log'],
                       ax=kwargs['ax'], color=kwargs['color'], legend_keys=kwargs['legend_keys'])




