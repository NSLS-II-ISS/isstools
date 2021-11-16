import os
from subprocess import call

from isstools.widgets import widget_energy_selector


import numpy as np
import pkg_resources
from PyQt5 import uic, QtWidgets, QtCore, QtGui

from isstools.conversions import xray
from isstools.dialogs import UpdateAngleOffset
from isstools.elements.figure_update import update_figure
from xas.trajectory import TrajectoryCreator
from isstools.elements.figure_update import setup_figure
from ophyd import utils as ophyd_utils
from xas.bin import xas_energy_grid
from isstools.dialogs.BasicDialogs import question_message_box, message_box

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_scan_manager.ui')

class UIScanManager(*uic.loadUiType(ui_path)):
    trajectoriesChanged = QtCore.pyqtSignal()

    def __init__(self,
                 hhm= None,
                 scan_manager=None,
                 detector_dict=[],
                 parent = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.hhm = hhm
        self.element = 'Titanium (22)'
        self.e0 = '4966'
        self.edge = 'K'

        self.scan_manager = scan_manager
        self.detector_dict = detector_dict
        self.widget_energy_selector = widget_energy_selector.UIEnergySelector()
        self.layout_energy_selector.addWidget(self.widget_energy_selector)

        self.widget_energy_selector.edit_E0.textChanged.connect(self.update_E0)
        self.widget_energy_selector.comboBox_edge.currentTextChanged.connect(self.update_edge)
        self.widget_energy_selector.comboBox_element.currentTextChanged.connect(self.update_element)

        self.hhm.angle_offset.subscribe(self.update_angle_offset)
        self.populate_detectors()
        self.push_create_scan.clicked.connect(self.create_scan)
        self.push_add_to_manager.clicked.connect(self.add_scan_to_manager)
        self.push_delete_scan.clicked.connect(self.delete_scan)
        self.listWidget_local_manager.doubleClicked.connect(self.local_list_clicked)

        self.figure_trajectory, self.canvas_trajectory, self.toolbar_trajectory = setup_figure(self, self.layout_trajectory)
        self.figure_trajectory.ax1 = self.figure_trajectory.add_subplot(111)
        self.figure_trajectory.ax2 = self.figure_trajectory.ax1.twinx()
        self.update_local_manager_list()

    def update_angle_offset(self, pvname = None, value=None, char_value=None, **kwargs):
        self.label_angle_offset.setText('{0:.8f}'.format(value))


    def populate_detectors(self):
        detector_names = ['Pilatus 100k', 'Xspress3']
        for detector in detector_names:
            qitem = QtWidgets.QCheckBox(detector)
            qitem.setCheckState(False)
            qitem.setTristate(False)
            self.verticalLayout_detectors.addWidget(qitem)

    @property
    def _mono_scan(self):
        return self.tabWidget_mono_scan.tabText(self.tabWidget_scan_type.currentIndex()).lower()
        #WIP

    @property
    def _scan_type(self):
        return self.tabWidget_scan_type.tabText(self.tabWidget_scan_type.currentIndex()).lower()

    @property
    def _traj_dict(self):
        if self.radioButton_flypath_standard.isChecked():
             traj_dict = {'type': 'standard',
                          'preedge_duration': float(self.edit_ds2_pree_duration.text()),
                          'edge_duration': float(self.edit_ds2_edge_duration.text()),
                          'postedge_duration': float(self.edit_ds2_poste_duration.text()),
                          'preedge_flex': float(self.edit_preedge_flex_frac.text()),
                          'postedge_flex': float(self.edit_postedge_flex_frac.text())}
        elif self.radioButton_flypath_doublesine.isChecked():
            traj_dict = {'type': 'double_sine',
                         'preedge_duration': float(self.edit_ds_pree_duration.text()),
                         'postedge_duration': float(self.edit_ds_poste_duration.text())}
        elif self.radioButton_flypath_sine.isChecked():
            traj_dict = {'type': 'sine',
                         'duration': float(self.edit_sine_total_duration.text())}

        traj_common = {'pad': float(self.edit_pad_time.text()),
                       'repeat': int(self.spinBox_tiling_repetitions.value()),
                       'single_direction': self.checkBox_traj_single_dir.isChecked(),
                       'revert': self.checkBox_traj_revert.isChecked(),
                       'filename' : ''}

        return {**traj_dict, **traj_common}

    @property
    def _step_dict(self):
        return {'preedge_stepsize': float(self.edit_preedge_spacing.text()),
                'XANES_stepsize': float(self.edit_xanes_spacing.text()),
                'EXAFS_stepsize': float(self.edit_exafs_spacing.text()),
                'preedge_dwelltime': float(self.edit_preedge_dwell.text()),
                'XANES_dwelltime': float(self.edit_xanes_dwell.text()),
                'EXAFS_dwelltime': float(self.edit_exafs_dwell.text()),
                'k_power': int(self.comboBox_exafs_dwell_kpower.currentText()),
                'revert': self.checkBox_energy_down.isChecked()}

    @property
    def _scan_parameters(self):
        scan_type = self._scan_type
        scan_parameters_common = {'element': self.widget_energy_selector.comboBox_element.currentText(),
                                  'edge': self.widget_energy_selector.comboBox_edge.currentText(),
                                  'e0': float(self.widget_energy_selector.edit_E0.text()),
                                  'preedge_start': float(self.edit_preedge_start.text()),
                                  'XANES_start': float(self.edit_xanes_start.text()),
                                  'XANES_end': float(self.edit_xanes_end.text()),
                                  'EXAFS_end': float(self.edit_exafs_end.text())}

        if scan_type == 'fly scan':
            return {**scan_parameters_common, **self._traj_dict}
        elif scan_type == 'step scan':
            return {**scan_parameters_common, **self._step_dict}

    @property
    def _scan_detectors(self):
        det_list = []
        for j in range(1, self.verticalLayout_detectors.count()):
            checkBox = self.verticalLayout_detectors.itemAt(j).widget()
            if checkBox.isChecked():
                det_list.append(checkBox.text())
        return det_list

    def create_scan(self):
        self.new_scan_dict = {'scan_type' : self._scan_type,
                              'scan_parameters' : self._scan_parameters}
        self.new_scan_aux_parameters = {'detectors' : self._scan_detectors,
                                        'offset' : float(self.label_angle_offset.text())}
        self.scan_manager.create_lightweight_trajectory(self.new_scan_dict, self.plot_trajectory_func)


    def add_scan_to_manager(self):
        name = self.lineEdit_scan_name.text()
        if name !='':
            self.scan_manager.add_scan(self.new_scan_dict, self.new_scan_aux_parameters, name)
            self.update_local_manager_list()
        else:
            message_box('Warning', 'Scan name is empty')

    def plot_trajectory_func(self, x, y):
        update_figure([self.figure_trajectory.ax1,self.figure_trajectory.ax2 ],
                      self.toolbar_trajectory,
                      self.canvas_trajectory)
        self.figure_trajectory.ax1.plot(x, y)
        self.figure_trajectory.ax1.set_xlabel('Time, s')
        self.figure_trajectory.ax1.set_ylabel('Energy, eV')
        self.figure_trajectory.ax2.plot(x[:-1], np.abs(np.diff(y) / np.diff(x)), 'r')
        self.figure_trajectory.ax2.set_ylabel('Velocity (eV/s)')
        self.canvas_trajectory.draw_idle()

    def update_local_manager_list(self):
        self.listWidget_local_manager.clear()
        scan_defs = [scan['scan_def']  for scan in self.scan_manager.scan_list_local]
        self.listWidget_local_manager.addItems(scan_defs )
        self.parent.widget_run.update_scan_defs(scan_defs)

    def delete_scan(self):
        selection = self.listWidget_local_manager.selectedIndexes()
        if selection != []:
            self.scan_manager.delete_local_scan(selection[0].row())
            self.update_local_manager_list()

    def local_list_clicked(self):
        selection = self.listWidget_local_manager.selectedIndexes()
        if selection != []:
            local_scan = self.scan_manager.scan_list_local[selection[0].row()]
            uid = local_scan['uid']
            global_scan = self.scan_manager.scan_dict[uid]
            params = ''
            for k, v in global_scan['scan_parameters'].items():
                params += f' {v}: {k} \n'
            scan_info = f" {local_scan['scan_def']} \n UID: {uid} \n {params}"
            message_box('Scan information', scan_info)

    def update_offset(self):
        dlg = UpdateAngleOffset.UpdateAngleOffset(self.label_angle_offset.text(), parent=self)
        if dlg.exec_():
            try:
                self.hhm.angle_offset.put(float(dlg.getValues()))
                self.update_angle_offset(value=float(dlg.getValues()))
            except Exception as exc:
                if type(exc) == ophyd_utils.errors.LimitError:
                    print('[New offset] {}. No reason to be desperate, though.'.format(exc))
                else:
                    print('[New offset] Something went wrong, not the limit: {}'.format(exc))
                return 1
            return 0

    def update_E0(self, text):
        self.e0 = text

    def update_edge(self, text):
        self.edge = text

    def update_element(self, text):
        self.element = text



