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
                 hhm=None,
                 scan_manager=None,
                 detector_dict=[],
                 aux_plan_funcs = {},
                 parent = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent

        self.element = 'Titanium (22)'
        self.e0 = '4966'
        self.edge = 'K'


        self.scan_manager = scan_manager
        self.detector_dict = detector_dict
        self.widget_energy_selector = widget_energy_selector.UIEnergySelector()
        self.layout_energy_selector.addWidget(self.widget_energy_selector)
        #communication between the Energy Selector widget and Trajectory Manager
        #
        self.widget_energy_selector.edit_E0.textChanged.connect(self.update_E0)
        self.widget_energy_selector.comboBox_edge.currentTextChanged.connect(self.update_edge)
        self.widget_energy_selector.comboBox_element.currentTextChanged.connect(self.update_element)

        #
        self.hhm = hhm
        self.hhm.angle_offset.subscribe(self.update_angle_offset)
        self.populate_detectors()
        self.push_create_scan.clicked.connect(self.create_scan)
        self.push_add_to_manager.clicked.connect(self.add_scan_to_manager)
        self.push_delete_scan.clicked.connect(self.delete_scan)

        self.figure_trajectory, self.canvas_trajectory, self.toolbar_trajectory = setup_figure(self, self.layout_trajectory)

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
        update_figure([self.figure_trajectory.ax], self.toolbar_trajectory, self.canvas_trajectory)
        self.figure_trajectory.ax.plot(x, y)
        self.figure_trajectory.ax.set_xlabel('Time, s')
        self.figure_trajectory.ax.set_ylabel('Energy, eV')
        self.canvas_trajectory.draw_idle()

    def update_local_manager_list(self):
        self.listWidget_local_manager.clear()
        scan_defs = [scan['scan_def']  for scan in self.scan_manager.scan_list_local]
        self.listWidget_local_manager.addItems(scan_defs )
        self.parent.widget_run.update_scan_defs(scan_defs)

    def delete_scan(self):
        idx = self.listWidget_local_manager.currentRow()
        self.scan_manager.delete_local_scan(idx)
        self.update_local_manager_list()


#___________________________________________________________________________________________________-


    def _update_figures(self):
        # Plot single trajectory motion
        update_figure([self.figure_single_trajectory.ax, self.figure_single_trajectory.ax2],
                       self.toolbar_single_trajectory,self.canvas_single_trajectory)
        # self.figure_single_trajectory.ax.plot(self.traj_creator.time, self.traj_creator.energy, 'ro')
        self.figure_single_trajectory.ax.plot(self.trajectory_creator.time_grid, self.trajectory_creator.energy_grid, 'b')
        self.figure_single_trajectory.ax.set_xlabel('Time (s)')
        self.figure_single_trajectory.ax.set_ylabel('Energy (eV)')
        # self.figure_single_trajectory.ax2.plot(self.traj_creator.time_grid[:-1], self.traj_creator.energy_grid_der,  'r')
        self.figure_single_trajectory.ax2.plot(self.trajectory_creator.time_grid[:-1], np.diff(self.trajectory_creator.energy_grid) / np.diff(self.trajectory_creator.time_grid), 'r')
        self.figure_single_trajectory.ax2.set_ylabel('Velocity (eV/s)')
        self.canvas_single_trajectory.draw_idle()

        update_figure([self.figure_full_trajectory.ax],
                      self.toolbar_full_trajectory, self.canvas_full_trajectory)

        # Draw
        self.figure_full_trajectory.ax.plot(self.trajectory_creator.e_bin, self.trajectory_creator.time_per_bin, 'b', label='trajectory')
        # self.figure_full_trajectory.ax.plot(self.traj_creator_ref.e_bin, self.traj_creator_ref.time_per_bin, ':', color=[0.5, 0.5, 0.5], alpha=0.75, label='reference')
        self.figure_full_trajectory.ax.legend()
        self.figure_full_trajectory.ax.set_xlabel\
            ('Energy, eV')
        self.figure_full_trajectory.ax.set_ylabel('time per energy point, s')

        self.canvas_full_trajectory.draw_idle()

    def _compute_time_per_bin(self, t, e, e0):
        edge_start = -30
        edge_end = 50
        preedge_spacing = 5
        if e0 < 14000:
            xanes_spacing = 0.2
        elif e0 >= 14000 and e0 < 21000:
            xanes_spacing = 0.3
        elif e0 >= 21000:
            xanes_spacing = 0.4
        else:
            xanes_spacing = 0.3
        exafs_k_spacing = 0.04
        idx = np.argsort(e)
        e_bin = xas_energy_grid(e[idx], e0, edge_start, edge_end, preedge_spacing, xanes_spacing, exafs_k_spacing)
        e_edges = np.hstack((e_bin[0], e_bin[:-1] + 0.5*np.diff(e_bin), e_bin[-1]))
        t_edges = np.interp(e_edges, e[idx], t[idx])
        # zxgzdfg
        return e_bin, np.diff(t_edges)


    def save_trajectory(self):
        # TODO: move the saving method to the trajectory class
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save trajectory...', self.trajectory_manager.trajectory_path, '*.txt',
                                                         options=QtWidgets.QFileDialog.DontConfirmOverwrite)[0]
        if filename[-4:] == '.txt':
            filename = filename[:-4]
        print(filename)
        if len(filename):
            fileName, fileExtension = os.path.splitext(filename)
            if fileExtension is not '.txt':
                filename = fileName + '.txt'
            print(filename)
            if (os.path.isfile(filename)):
                ret = self.questionMessage('Save trajectory...', '{} already exists. Do you want to replace it?'.format(
                    filename.rsplit('/', 1)[1]))
                if not ret:
                    print('Aborted!')
                    return
            np.savetxt(filename,
                       self.trajectory_creator.energy_grid, fmt='%.6f',
                       header = f'element: {self.trajectory_creator.elem}, edge: {self.trajectory_creator.edge}, E0: {self.trajectory_creator.e0}')#, scan_direction: {self.traj_creator.direction}')
            call(['chmod', '666', filename])
            # self.trajectory_path = filename[:filename.rfind('/')] + '/'
            self.label_current_trajectory.setText(filename.rsplit('/', 1)[1])
            self.push_plot_traj.setEnabled(True)
            print('Trajectory saved! [{}]'.format(filename))

    def plot_traj_file(self):
        self.trajectory_creator.load_trajectory_file(self.trajectory_manager.trajectory_path + self.label_current_trajectory.text(),
                                                     float(self.label_angle_offset.text()), is_energy=True)
        self._update_figures()
        print('Trajectory Load: Done')
        self.push_save_trajectory.setDisabled(True)

    def load_trajectory(self):
        self.trajectory_manager.load(orig_file_name=self.label_current_trajectory.text(),
                                     new_file_path=self.comboBox_slot_to_load_trajectory.currentText(),
                                     is_energy=True, offset=float(self.label_angle_offset.text()))

        self.trajectoriesChanged.emit()

    def init_trajectory(self):
        self.trajectory_manager.init(int(self.comboBox_slot_to_init_trajectory.currentText()))

    def read_trajectory_info(self):
        self.trajectory_manager.read_info()

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

    def get_traj_names(self):
        filepath = QtWidgets.QFileDialog.getOpenFileName(directory=self.trajectory_manager.trajectory_path, filter='*.txt', parent=self)[0]
        self.label_current_trajectory.setText(filepath.rsplit('/', 1)[1])
        # self.trajectory_path = filepath[:filepath.rfind('/')] + '/'
        self.push_plot_traj.setEnabled(True)

    def update_E0(self, text):
        self.e0 = text

    def update_edge(self, text):
        self.edge = text

    def update_element(self, text):
        self.element = text

    def update_repetitions_spinbox(self):
        if self.checkBox_traj_single_dir.isChecked():
            self.spinBox_tiling_repetitions.setValue(1)
            self.spinBox_tiling_repetitions.setEnabled(0)
        else:
            self.spinBox_tiling_repetitions.setEnabled(1)

    def questionMessage(self, title, question):
        reply = QtWidgets.QMessageBox.question(self, title,
                                               question,
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            return True
        elif reply == QtWidgets.QMessageBox.No:
            return False
        else:
            return False
