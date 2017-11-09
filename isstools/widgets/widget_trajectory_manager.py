import collections
import os
from subprocess import call

import numpy as np
import pkg_resources

from PyQt5 import uic, QtWidgets
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure

from ophyd import utils as ophyd_utils

import isstools.widgets.widget_general_info
from isstools.conversions import xray
from isstools.dialogs import UpdateAngleOffset

from isstools.trajectory.trajectory import trajectory, trajectory_manager


import isstools.widgets.widget_energy_selector

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_trajectory_manager.ui')
print(ui_path)

class UITrajectoryManager(*uic.loadUiType(ui_path)):
    def __init__(self,
                 hhm=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.addCanvas()

        self.element = 'Scandium (21)'
        self.e0 = '4492'
        self.edge = 'K'

        self.widget_energy_selector = isstools.widgets.widget_energy_selector.UIEnergySelector()
        self.layout_energy_selector_trajectory.addWidget(self.widget_energy_selector)
        #communication between the Energy Selector widget and Trajectory Manager
        self.widget_energy_selector.edit_E0.textChanged.connect(self.update_E0)
        self.widget_energy_selector.comboBox_edge.currentTextChanged.connect(self.update_edge)
        self.widget_energy_selector.comboBox_element.currentTextChanged.connect(self.update_element)


        self.hhm = hhm
        self.hhm.angle_offset.subscribe(self.update_angle_offset)
        self.traj_manager = trajectory_manager(hhm)
        self.comboBox_slot_to_load_trajectory.addItems(['1', '2', '3', '4', '5', '6', '7', '8'])
        self.comboBox_slot_to_init_trajectory.addItems(['1', '2', '3', '4', '5', '6', '7', '8'])
        self.comboBox_slot_to_init_trajectory.setCurrentIndex(self.traj_manager.current_lut() - 1)
        self.trajectories = self.traj_manager.read_info(silent=True)
        self.trajectories = collections.OrderedDict(sorted(self.trajectories.items()))
        #self.update_batch_traj()


        self.traj_creator = trajectory()
        self.trajectory_path = '/GPFS/xf08id/trajectory/'
        self.push_build_trajectory.clicked.connect(self.build_trajectory)
        self.push_save_trajectory.clicked.connect(self.save_trajectory)
        self.push_update_offset.clicked.connect(self.update_offset)
        self.push_select_traj_file.clicked.connect(self.get_traj_names)
        self.push_load_trajectory.clicked.connect(self.load_trajectory)
        self.push_init_trajectory.clicked.connect(self.init_trajectory)
        self.push_read_traj_info.clicked.connect(self.read_trajectory_info)
        self.push_prepare_trajectory.clicked.connect(self.run_prep_traj)
        self.push_plot_traj.clicked.connect(self.plot_traj_file)
        self.push_plot_traj.setDisabled(True)
        self.push_save_trajectory.setDisabled(True)

    def addCanvas(self):
        self.figure_single_trajectory = Figure()
        self.figure_single_trajectory.set_facecolor(color='#FcF9F6')
        self.canvas_single_trajectory = FigureCanvas(self.figure_single_trajectory)
        self.figure_single_trajectory.ax = self.figure_single_trajectory.add_subplot(111)
        self.figure_single_trajectory.ax2 = self.figure_single_trajectory.ax.twinx()
        self.toolbar_single_trajectory = NavigationToolbar(self.canvas_single_trajectory, self, coordinates=True)

        self.plot_single_trajectory.addWidget(self.toolbar_single_trajectory)
        self.plot_single_trajectory.addWidget(self.canvas_single_trajectory)
        self.canvas_single_trajectory.draw_idle()

        self.figure_full_trajectory = Figure()
        self.figure_full_trajectory.set_facecolor(color='#FcF9F6')
        self.canvas_full_trajectory = FigureCanvas(self.figure_full_trajectory)
        self.figure_full_trajectory.add_subplot(111)
        self.figure_full_trajectory.ax = self.figure_full_trajectory.add_subplot(111)
        self.toolbar_full_trajectory = NavigationToolbar(self.canvas_full_trajectory, self,coordinates=True)

        self.plot_full_trajectory.addWidget(self.toolbar_full_trajectory)
        self.plot_full_trajectory.addWidget(self.canvas_full_trajectory)
        self.canvas_full_trajectory.draw_idle()

    def update_angle_offset(self, pvname = None, value=None, char_value=None, **kwargs):
        self.label_angle_offset.setText('{0:.8f}'.format(value))

    def build_trajectory(self):
        E0 = float(self.e0)
        preedge_lo = int(self.edit_preedge_lo.text())
        preedge_hi = int(self.edit_preedge_hi.text())
        edge_hi = int(self.edit_edge_hi.text())

        postedge_k = float(self.edit_postedge_hi.text())
        postedge_hi = xray.k2e(postedge_k,
                               E0) - E0  # (1000 * ((postedge_k ** 2) + (16.2009 ** 2) * E0/1000) / (16.2009 ** 2)) - E0

        velocity_preedge = int(self.edit_velocity_preedge.text())
        velocity_edge = int(self.edit_velocity_edge.text())
        velocity_postedge = int(self.edit_velocity_postedge.text())

        preedge_stitch_lo = int(self.edit_preedge_stitch_lo.text())
        preedge_stitch_hi = int(self.edit_preedge_stitch_hi.text())
        edge_stitch_lo = int(self.edit_edge_stitch_lo.text())
        edge_stitch_hi = int(self.edit_edge_stitch_hi.text())
        postedge_stitch_lo = int(self.edit_postedge_stitch_lo.text())
        postedge_stitch_hi = int(self.edit_postedge_stitch_hi.text())

        padding_preedge = float(self.edit_padding_preedge.text())
        padding_postedge = float(self.edit_padding_postedge.text())

        sine_duration = float(self.edit_sine_total_duration.text())

        traj_type = self.tabWidget_2.tabText(self.tabWidget_2.currentIndex())
        if traj_type == 'Double Sine':
            dsine_preedge_duration = float(self.edit_ds_pree_duration.text())
            dsine_postedge_duration = float(self.edit_ds_poste_duration.text())
        else:
            dsine_preedge_duration = float(self.edit_ds2_pree_duration.text())
            dsine_postedge_duration = float(self.edit_ds2_poste_duration.text())

        vel_edge = float(self.edit_vel_edge.text())
        #Define element and edge
        self.traj_creator.element = '{}'.format(self.element)
        self.traj_creator.edge = '{}'.format(self.edge)
        self.traj_creator.E0 = '{}'.format(self.e0)
        # Create and interpolate trajectory
        self.traj_creator.define(edge_energy=E0, offsets=([preedge_lo, preedge_hi, edge_hi, postedge_hi]),
                                 velocities=([velocity_preedge, velocity_edge, velocity_postedge]), \
                                 stitching=([preedge_stitch_lo, preedge_stitch_hi, edge_stitch_lo, edge_stitch_hi,
                                             postedge_stitch_lo, postedge_stitch_hi]), \
                                 servocycle=16000, padding_lo=padding_preedge, padding_hi=padding_postedge,
                                 sine_duration=sine_duration,
                                 dsine_preedge_duration=dsine_preedge_duration,
                                 dsine_postedge_duration=dsine_postedge_duration, trajectory_type=traj_type,
                                 vel_edge=vel_edge)
        self.traj_creator.interpolate()

        # Revert trajectory if checkbox checked
        if self.checkBox_traj_revert.isChecked() and self.checkBox_traj_revert.isEnabled():
            self.traj_creator.revert()

        # Plot single trajectory motion
        self.figure_single_trajectory.ax.clear()
        self.figure_single_trajectory.ax2.clear()
        self.toolbar_single_trajectory._views.clear()
        self.toolbar_single_trajectory._positions.clear()
        self.toolbar_single_trajectory._update_view()
        self.figure_single_trajectory.ax.plot(self.traj_creator.time, self.traj_creator.energy, 'ro')
        self.figure_single_trajectory.ax.plot(self.traj_creator.time_grid, self.traj_creator.energy_grid, 'b')
        self.figure_single_trajectory.ax.set_xlabel('Time (s)')
        self.figure_single_trajectory.ax.set_ylabel('Energy (eV)')
        self.figure_single_trajectory.ax2.plot(self.traj_creator.time_grid[0:-1], self.traj_creator.energy_grid_der,
                                               'r')
        self.figure_single_trajectory.ax2.set_ylabel('Velocity (eV/s)')
        self.canvas_single_trajectory.draw_idle()

        # Tile trajectory
        self.figure_full_trajectory.ax.clear()
        self.toolbar_full_trajectory._views.clear()
        self.toolbar_full_trajectory._positions.clear()
        self.toolbar_full_trajectory._update_view()
        self.canvas_full_trajectory.draw_idle()
        self.traj_creator.tile(reps=self.spinBox_tiling_repetitions.value(),
                               single_direction=self.checkBox_traj_single_dir.isChecked())

        # Convert to encoder counts
        self.traj_creator.e2encoder(float(self.label_angle_offset.text()))

        # Draw
        self.figure_full_trajectory.ax.plot(self.traj_creator.encoder_grid, 'b')
        self.figure_full_trajectory.ax.set_xlabel('Servo event / 1/16000 s')
        self.figure_full_trajectory.ax.set_ylabel('Encoder count')
        self.canvas_full_trajectory.draw_idle()

        self.push_save_trajectory.setEnabled(True)

    def save_trajectory(self):
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save trajectory...', self.trajectory_path, '*.txt')[0]
        if len(filename):
            fileName, fileExtension = os.path.splitext(filename)
            if fileExtension is not '.txt':
                filename = fileName + '.txt'
            np.savetxt(filename,
                   self.traj_creator.energy_grid, fmt='%.6f',
                       header='element: {}\nedge: {}\nE0: {}\n'
                       .format(self.traj_creator.element, self.traj_creator.edge, self.traj_creator.E0))
            call(['chmod', '666', filename])
            self.trajectory_path = filename[:filename.rfind('/')] + '/'
            self.label_current_trajectory.setText(filename.rsplit('/', 1)[1])
            self.push_plot_traj.setEnabled(True)
            print('Trajectory saved! [{}]'.format(filename))

    def plot_traj_file(self):
        self.traj_creator.load_trajectory_file(self.trajectory_path + self.label_56.text(),
                                               float(self.label_angle_offset.text()), is_energy=True)

        self.figure_single_trajectory.ax.clear()
        self.figure_single_trajectory.ax2.clear()
        self.toolbar_single_trajectory._views.clear()
        self.toolbar_single_trajectory._positions.clear()
        self.toolbar_single_trajectory._update_view()
        self.figure_full_trajectory.ax.clear()
        self.toolbar_full_trajectory._views.clear()
        self.toolbar_full_trajectory._positions.clear()
        self.toolbar_full_trajectory._update_view()
        self.canvas_single_trajectory.draw_idle()
        self.canvas_full_trajectory.draw_idle()

        self.figure_full_trajectory.ax.plot(np.arange(0, len(self.traj_creator.energy_grid_loaded) / 16000, 1 / 16000),
                                            self.traj_creator.energy_grid_loaded, 'b')
        self.figure_full_trajectory.ax.set_xlabel('Time /s')
        self.figure_full_trajectory.ax.set_ylabel('Energy /eV')
        self.figure_full_trajectory.ax.set_title(self.label_56.text())
        self.canvas_full_trajectory.draw_idle()
        print('Trajectory Load: Done')

        self.push_save_trajectory.setDisabled(True)

    def load_trajectory(self):
        self.traj_manager.load(orig_file_name=self.label_current_trajectory.text(), new_file_path=self.comboBox_slot_to_save_trajectory.currentText(),
                               is_energy=True, offset=float(self.label_angle_offset.text()),
                               orig_file_path=self.trajectory_path, ip='10.8.2.86')
        self.update_batch_traj()

    def init_trajectory(self):
        self.run_start.setDisabled(True)
        self.traj_manager.init(int(self.comboBox_slot_to_init_trajectory.currentText()))
        self.run_start.setEnabled(True)

    def read_trajectory_info(self):
        self.traj_manager.read_info()

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
        filepath = QtWidgets.QFileDialog.getOpenFileName(directory=self.trajectory_path, filter='*.txt', parent=self)[0]
        self.label_current_trajectory.setText(filepath.rsplit('/', 1)[1])
        self.trajectory_path = filepath[:filepath.rfind('/')] + '/'
        self.push_plot_traj.setEnabled(True)

    def run_prep_traj(self):
        self.RE(self.prep_traj_plan())

    def update_E0(self, text):
        self.e0 = text

    def update_edge(self, text):
        self.edge = text

    def update_element(self, text):
        self.element = text
