import numpy as np
from PyQt4 import uic, QtGui, QtCore
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import pkg_resources
import time as ttime
import math
import bluesky.plans as bp

from isstools.trajectory.trajectory  import trajectory
from isstools.trajectory.trajectory import trajectory_manager
from isstools.xasdata import xasdata
from isstools.xiaparser import xiaparser
from isstools.elements import elements
from isstools.dialogs import UpdateUserDialog
from isstools.conversions import xray
import os
from os import listdir
from os.path import isfile, join
import inspect
import re
import sys

ui_path = pkg_resources.resource_filename('isstools', 'ui/XLive.ui')

# def my_plan(dets, some, other, param):
#	...


def auto_redraw_factory(fnc):

    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback

class ScanGui(*uic.loadUiType(ui_path)):
    shutters_sig = QtCore.pyqtSignal()
    progress_sig = QtCore.pyqtSignal()

    def __init__(self, plan_funcs, tune_funcs, prep_traj_plan, RE, db, hhm, detectors, parent=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        #self.fig = fig = self.figure_content()
        self.addCanvas()
        self.run_start.clicked.connect(self.run_scan)
        self.push_build_trajectory.clicked.connect(self.build_trajectory)
        self.push_save_trajectory.clicked.connect(self.save_trajectory)
        self.prep_traj_plan = prep_traj_plan
        self.RE = RE
        self.RE.last_state = ''
        self.db = db
        self.hhm = hhm
        self.hhm.trajectory_progress.subscribe(self.update_progress)
        self.progress_sig.connect(self.update_progressbar) 
        self.progressBar.setValue(0)
        self.abs_parser = xasdata.XASdataAbs() 
        self.flu_parser = xasdata.XASdataFlu() 
        self.push_update_user.clicked.connect(self.update_user)

        # Write metadata in the GUI
        self.label_6.setText('{}'.format(RE.md['year']))
        self.label_7.setText('{}'.format(RE.md['cycle']))
        self.label_8.setText('{}'.format(RE.md['PROPOSAL']))
        self.label_9.setText('{}'.format(RE.md['SAF']))
        self.label_10.setText('{}'.format(RE.md['PI']))

        # Initialize 'trajectory' tab
        self.traj = trajectory()
        self.traj_manager = trajectory_manager(hhm)
        self.trajectory_path = '/GPFS/xf08id/trajectory/'
        self.get_traj_names()
        self.push_update_traj_list.clicked.connect(self.get_traj_names)
        self.comboBox_2.addItems(['1', '2', '3', '4', '5', '6', '7', '8', '9'])
        self.comboBox_3.addItems(['1', '2', '3', '4', '5', '6', '7', '8', '9'])
        # Commented to work without the Mono (IOC was off)
        #self.comboBox_3.setCurrentIndex(self.traj_manager.current_lut() - 1)
        self.push_load_trajectory.clicked.connect(self.load_trajectory)
        self.push_init_trajectory.clicked.connect(self.init_trajectory)
        self.push_read_traj_info.clicked.connect(self.read_trajectory_info)
        self.push_prepare_trajectory.clicked.connect(self.run_prep_traj)

        # Initialize XIA tab
        self.xia_parser = xiaparser.xiaparser()
        self.push_gain_matching.clicked.connect(self.run_gain_matching)

        # Initialize detectors
        self.xia = detectors['xia']
        self.pba1 = detectors['pba1']
        self.pba2 = detectors['pba2']

        # Initialize 'tune' tab
        self.push_tune.clicked.connect(self.run_tune)
        self.tune_funcs = tune_funcs
        self.tune_funcs_names = [tune.__name__ for tune in tune_funcs]
        self.comboBox_4.addItems(self.tune_funcs_names)

        # Initialize 'run' tab
        self.plan_funcs = plan_funcs
        self.plan_funcs_names = [plan.__name__ for plan in plan_funcs]
        self.run_type.addItems(self.plan_funcs_names)
        self.push_re_abort.clicked.connect(self.re_abort)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_re_state)
        self.timer.start(1000)

        self.run_type.currentIndexChanged.connect(self.populateParams)
        self.params1 = []
        self.params2 = []
        self.params3 = []
        self.populateParams(0)

        # Initialize epics elements
        self.shutter_a = elements.shutter('XF:08ID-PPS{Sh:FE}Pos-Sts', 'XF:08ID-PPS{Sh:FE}Cmd:Opn-Cmd', 'XF:08ID-PPS{Sh:FE}Cmd:Cls-Cmd', self.update_shutter)
        self.shutter_b = elements.shutter('XF:08IDA-PPS{PSh}Pos-Sts', 'XF:08IDA-PPS{PSh}Cmd:Opn-Cmd', 'XF:08IDA-PPS{PSh}Cmd:Cls-Cmd', self.update_shutter)
        self.push_fe_shutter.clicked.connect(self.toggle_fe_button)
        self.push_ph_shutter.clicked.connect(self.toggle_ph_button)

        if self.shutter_a.value == 0:
            self.push_fe_shutter.setStyleSheet("background-color: lime")
        else:
            self.push_fe_shutter.setStyleSheet("background-color: red")
        if self.shutter_b.value == 0:
            self.push_ph_shutter.setStyleSheet("background-color: lime")
        else:
            self.push_ph_shutter.setStyleSheet("background-color: red")
        self.shutters_sig.connect(self.change_shutter_color)

        # Initialize 'processing' tab
        self.push_select_file.clicked.connect(self.selectFile)
        self.push_bin.clicked.connect(self.process_bin)
        self.push_save_bin.clicked.connect(self.save_bin)

        # Redirect terminal output to GUI
        sys.stdout = EmittingStream(textWritten=self.normalOutputWritten)
        sys.stderr = EmittingStream(textWritten=self.normalOutputWritten)

    def update_user(self):
        dlg = UpdateUserDialog.UpdateUserDialog(self.label_6.text(), self.label_7.text(), self.label_8.text(), self.label_9.text(), self.label_10.text())
        if dlg.exec_():
            self.RE.md['year'], self.RE.md['cycle'], self.RE.md['PROPOSAL'], self.RE.md['SAF'], self.RE.md['PI'] = dlg.getValues()
            self.label_6.setText('{}'.format(self.RE.md['year']))
            self.label_7.setText('{}'.format(self.RE.md['cycle']))
            self.label_8.setText('{}'.format(self.RE.md['PROPOSAL']))
            self.label_9.setText('{}'.format(self.RE.md['SAF']))
            self.label_10.setText('{}'.format(self.RE.md['PI']))

    def update_shutter(self, pvname=None, value=None, char_value=None, **kwargs):
        if(pvname == 'XF:08ID-PPS{Sh:FE}Pos-Sts'):
            current_button = self.push_fe_shutter
        elif(pvname == 'XF:08IDA-PPS{PSh}Pos-Sts'):
            current_button = self.push_ph_shutter

        self.current_button = current_button
        if int(value) == 0:
            self.current_button_color = 'lime'
        if int(value) == 1:
            self.current_button_color = 'red'
        self.shutters_sig.emit()

    def change_shutter_color(self):
        self.current_button.setStyleSheet("background-color: " + self.current_button_color)

    def toggle_fe_button(self):
        #print('{}'.format(int(not self.shutter_a.value)))
        if(int(self.shutter_a.value)):
            self.shutter_a.open()
        else:
            self.shutter_a.close()

    def toggle_ph_button(self):
        #print('{}'.format(int(not self.shutter_b.value)))
        if(int(self.shutter_b.value)):
            self.shutter_b.open()
        else:
            self.shutter_b.close()

    def update_progress(self, pvname = None, value=None, char_value=None, **kwargs):
        self.progress_sig.emit()
        self.progressValue = value

    def update_progressbar(self):
        self.progressBar.setValue(int(self.progressValue))

    def getX(self, event):
        self.edit_E0_2.setText(str(int(np.round(event.xdata))))

    def selectFile(self):
        selected_filename = QtGui.QFileDialog.getOpenFileName(directory = '/GPFS/xf08id/User Data/', filter = '*.txt')
        if selected_filename:
            self.label_24.setText(selected_filename)
            self.process_bin_equal()

    def save_bin(self):
        self.abs_parser.data_manager.export_dat(self.label_24.text(), self.abs_parser.header_read.replace('Timestamp (s)   ','', 1)[:-1])

    def process_bin(self):
        #parser = xasdata.XASdataAbs()
        ax = self.figure_old_scans.add_subplot(111)
        print(self.label_24.text())
        self.abs_parser.loadInterpFile(self.label_24.text())
        ax.cla()
        self.abs_parser.plot(ax)

        ax = self.figure_old_scans_3.add_subplot(111)
        ax.cla()
        e0 = int(self.edit_E0_2.text())
        self.abs_parser.bin(e0, e0 + int(self.edit_edge_start.text()), e0 + int(self.edit_edge_end.text()), float(self.edit_preedge_spacing.text()), float(self.edit_xanes_spacing.text()), float(self.edit_exafs_spacing.text()))
        self.abs_parser.data_manager.plot(ax)

        self.canvas_old_scans_3.draw()


    def process_bin_equal(self):
        #parser = xasdata.XASdataAbs()
        ax = self.figure_old_scans.add_subplot(111)
        print(self.label_24.text())
        self.abs_parser.loadInterpFile(self.label_24.text())
        ax.cla()
        self.abs_parser.plot(ax)

        if not hasattr(self, 'bin_ax'):
            self.bin_ax = self.figure_old_scans_2.add_subplot(111)
        if not hasattr(self, 'bin_ax2'):
            self.bin_ax2 = self.bin_ax.twinx()
        self.bin_ax.cla()
        self.bin_ax2.cla()
        self.abs_parser.bin_equal()
        self.abs_parser.data_manager.plot(self.bin_ax)
        self.bin_ax.set_ylabel('Log(i0/it)', color='b')

        self.abs_parser.data_manager.plot_der(self.bin_ax2, 'r')
        self.bin_ax2.set_ylabel('Derivative', color='r')

        self.canvas_old_scans.draw()
        self.canvas_old_scans_2.draw()

        cid = self.canvas_old_scans_2.mpl_connect('button_press_event', self.getX)


    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def normalOutputWritten(self, text):
        """Append text to the QtextEdit_terminal."""
        # Maybe QtextEdit_terminal.append() works as well, but this is how I do it:
        cursor = self.textEdit_terminal.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(text)
        self.textEdit_terminal.setTextCursor(cursor)
        self.textEdit_terminal.ensureCursorVisible()
        #sys.__stdout__.writelines(text)

    def populateParams(self, index):
        for i in range(len(self.params1)):
            self.gridLayout_13.removeWidget(self.params1[i])
            self.gridLayout_13.removeWidget(self.params2[i])
            self.gridLayout_13.removeWidget(self.params3[i])
            self.params1[i].deleteLater()
            self.params2[i].deleteLater()
            self.params3[i].deleteLater()
        self.params1 = []
        self.params2 = []
        self.params3 = []
        self.param_types = []
        plan_func = self.plan_funcs[index]
        signature = inspect.signature(plan_func)
        for i in range(0, len(signature.parameters)):
            default = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))
            if default == str(signature.parameters[list(signature.parameters)[i]]):
                default = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))
            self.addParamControl(list(signature.parameters)[i], default, signature.parameters[list(signature.parameters)[i]].annotation)
            self.param_types.append(signature.parameters[list(signature.parameters)[i]].annotation)


    def addParamControl(self, name, default, annotation):
        rows = int(self.gridLayout_13.count()/3)
        param1 = QtGui.QLabel('Par ' + str(rows + 1))

        def_val = ''
        if default.find('=') != -1:
            def_val = re.sub(r'.*=', '', default)
        if annotation == int:
            param2 = QtGui.QSpinBox()
            def_val = int(def_val)
            param2.setValue(def_val)
        elif annotation == float:
            param2 = QtGui.QDoubleSpinBox()
            def_val = float(def_val)
            param2.setValue(def_val)
        elif annotation == bool:
            param2 = QtGui.QCheckBox()
            if def_val == 'True':
                def_val = True
            else:
                def_val = False
            param2.setCheckState(def_val)
            param2.setTristate(False)
        else:
            param2 = QtGui.QLineEdit()
            def_val = str(def_val)
            param2.setText(def_val)

        param3 = QtGui.QLabel(default)
        self.gridLayout_13.addWidget(param1, rows, 0)
        self.gridLayout_13.addWidget(param2, rows, 1)
        self.gridLayout_13.addWidget(param3, rows, 2)
        self.params1.append(param1)
        self.params2.append(param2)
        self.params3.append(param3)

    def get_traj_names(self):
        self.comboBox.clear()
        self.comboBox.addItems([f for f in sorted(listdir(self.trajectory_path)) if isfile(join(self.trajectory_path, f))])


    def addCanvas(self):
        self.figure = Figure()
        self.figure.set_facecolor(color='0.89')
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self.tab_2, coordinates=True)
        self.toolbar.setMaximumHeight(25)
        self.plots.addWidget(self.toolbar)
        self.plots.addWidget(self.canvas)
        self.canvas.draw()

        self.figure_single_trajectory = Figure()
        self.figure_single_trajectory.set_facecolor(color='0.89')
        self.canvas_single_trajectory = FigureCanvas(self.figure_single_trajectory)
        self.plot_single_trajectory.addWidget(self.canvas_single_trajectory)
        self.canvas_single_trajectory.draw()

        self.figure_full_trajectory = Figure()
        self.figure_full_trajectory.set_facecolor(color='0.89')
        self.canvas_full_trajectory = FigureCanvas(self.figure_full_trajectory)
        self.plot_full_trajectory.addWidget(self.canvas_full_trajectory)
        self.canvas_full_trajectory.draw()

        self.figure_tune = Figure()
        self.figure_tune.set_facecolor(color='0.89')
        self.canvas_tune = FigureCanvas(self.figure_tune)
        self.plot_tune.addWidget(self.canvas_tune)
        self.canvas_tune.draw()

        self.figure_gain_matching = Figure()
        self.figure_gain_matching.set_facecolor(color='0.89')
        self.canvas_gain_matching = FigureCanvas(self.figure_gain_matching)
        self.plot_gain_matching.addWidget(self.canvas_gain_matching)
        self.canvas_gain_matching.draw()

        self.figure_old_scans = Figure()
        self.figure_old_scans.set_facecolor(color='0.89')
        self.canvas_old_scans = FigureCanvas(self.figure_old_scans)
        self.toolbar_old_scans = NavigationToolbar(self.canvas_old_scans, self.tab_2, coordinates=True)
        self.plot_old_scans.addWidget(self.toolbar_old_scans)
        self.plot_old_scans.addWidget(self.canvas_old_scans)
        self.canvas_old_scans.draw()

        self.figure_old_scans_2 = Figure()
        self.figure_old_scans_2.set_facecolor(color='0.89')
        self.canvas_old_scans_2 = FigureCanvas(self.figure_old_scans_2)
        self.toolbar_old_scans_2 = NavigationToolbar(self.canvas_old_scans_2, self.tab_2, coordinates=True)
        self.plot_old_scans_2.addWidget(self.toolbar_old_scans_2)
        self.plot_old_scans_2.addWidget(self.canvas_old_scans_2)
        self.canvas_old_scans_2.draw()

        self.figure_old_scans_3 = Figure()
        self.figure_old_scans_3.set_facecolor(color='0.89')
        self.canvas_old_scans_3 = FigureCanvas(self.figure_old_scans_3)
        self.toolbar_old_scans_3 = NavigationToolbar(self.canvas_old_scans_3, self.tab_3, coordinates=True)
        self.plot_old_scans_3.addWidget(self.toolbar_old_scans_3)
        self.plot_old_scans_3.addWidget(self.canvas_old_scans_3)
        self.canvas_old_scans_3.draw()


    @property
    def plot_x(self):
        return self.plot_selection_dropdown.value()

    def figure_content(self):
        fig1 = Figure()
        fig1.set_facecolor(color='0.89')
        fig1.stale_callback = auto_redraw_factory(fig1.stale_callback)
        ax1f1 = fig1.add_subplot(111)
        ax1f1.plot(np.random.rand(5))
        self.ax = ax1f1
        return fig1

    def run_tune(self):
        if self.shutter_a.value == 1 or self.shutter_b.value == 1:
            ret = self.questionMessage('Shutter closed', 'Would you like to run the tuning with the shutter closed?') 
            if not ret:
                print ('Aborted!')
                return False 

        self.figure_tune.clf()
        self.tune_funcs[self.comboBox_4.currentIndex()](float(self.edit_tune_range.text()), float(self.edit_tune_step.text()), self.spinBox_tune_retries.value(), self.figure_tune)


    def run_prep_traj(self):
        self.RE(self.prep_traj_plan())


    def build_trajectory(self):
        E0 = int(self.edit_E0.text())
        preedge_lo = int(self.edit_preedge_lo.text())
        preedge_hi = int(self.edit_preedge_hi.text())
        edge_hi = int(self.edit_edge_hi.text())

        postedge_k = float(self.edit_postedge_hi.text())
        postedge_hi = xray.k2e(postedge_k, E0) #(1000 * ((postedge_k ** 2) + (16.2009 ** 2) * E0/1000) / (16.2009 ** 2)) - E0

        velocity_preedge = int (self.edit_velocity_preedge.text())
        velocity_edge = int(self.edit_velocity_edge.text())
        velocity_postedge = int(self.edit_velocity_postedge.text())

        preedge_stitch_lo = int(self.edit_preedge_stitch_lo.text())
        preedge_stitch_hi = int(self.edit_preedge_stitch_hi.text())
        edge_stitch_lo =  int(self.edit_edge_stitch_lo.text())
        edge_stitch_hi = int(self.edit_edge_stitch_hi.text())
        postedge_stitch_lo = int(self.edit_postedge_stitch_lo.text())
        postedge_stitch_hi = int(self.edit_postedge_stitch_hi.text())

        padding_preedge = float(self.edit_padding_preedge.text())
        padding_postedge = float(self.edit_padding_postedge.text())

        sine_duration = float(self.edit_sine_total_duration.text())

        dsine_preedge_duration = float(self.edit_ds_pree_duration.text())
        dsine_postedge_duration = float(self.edit_ds_poste_duration.text())

        traj_type = self.tabWidget_2.tabText(self.tabWidget_2.currentIndex())

        #Create and interpolate trajectory
        self.traj.define(edge_energy = E0, offsets = ([preedge_lo,preedge_hi,edge_hi,postedge_hi]),velocities = ([velocity_preedge, velocity_edge, velocity_postedge]),\
                        stitching = ([preedge_stitch_lo, preedge_stitch_hi, edge_stitch_lo, edge_stitch_hi, postedge_stitch_lo, postedge_stitch_hi]),\
                        servocycle = 16000, padding_lo = padding_preedge ,padding_hi=padding_postedge, sine_duration = sine_duration, 
                        dsine_preedge_duration = dsine_preedge_duration, dsine_postedge_duration = dsine_postedge_duration, trajectory_type = traj_type)
        self.traj.interpolate()

        #Plot single trajectory motion
        self.figure_single_trajectory.clf()
        ax = self.figure_single_trajectory.add_subplot(111)
        ax.hold(False)
        ax.plot(self.traj.time, self.traj.energy, 'r*')
        ax.hold(True)
        ax.plot(self.traj.time_grid, self.traj.energy_grid, 'b')
        ax.set_xlabel('Time /s')
        ax.set_ylabel('Energy /eV')
        ax2 = ax.twinx()
        ax2.hold(False)
        ax2.plot(self.traj.time_grid[0:-1], self.traj.energy_grid_der, 'r')
        self.canvas_single_trajectory.draw()

        # Tile trajectory
        self.figure_full_trajectory.clf()
        self.traj.tile(reps=self.spinBox_tiling_repetitions.value())

        # Convert to encoder counts
        self.traj.e2encoder()
        
        # Draw
        ax = self.figure_full_trajectory.add_subplot(111)
        ax.hold(False)
        ax.plot(self.traj.encoder_grid, 'b')
        ax.set_xlabel('Servo event / 1/16000 s')
        ax.set_ylabel('Encoder count')
        self.canvas_full_trajectory.draw()


    def save_trajectory(self):
        if(len(self.traj.energy_grid)):
            if(self.edit_trajectory_name.text() != '.txt'):
                if(os.path.isfile(self.trajectory_path + self.edit_trajectory_name.text())):
                    overwrite_answer = QtGui.QMessageBox.question(self, 'Message', 
                         'File exists. Would you like to overwrite it?', QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
                    if overwrite_answer == QtGui.QMessageBox.Yes:
                        np.savetxt(self.trajectory_path + self.edit_trajectory_name.text(), 
						self.traj.encoder_grid, fmt='%d')
                        self.get_traj_names()
                    else:
                        self.edit_trajectory_name.selectAll()
                        self.edit_trajectory_name.setFocus()
                else:
                    np.savetxt(self.trajectory_path + self.edit_trajectory_name.text(), 
					self.traj.encoder_grid, fmt='%d')
                    self.get_traj_names()
            else:
                print('\n.txt is not a valid name')

    def load_trajectory(self):
        self.traj_manager.load(orig_file_name = self.comboBox.currentText(), new_file_path = self.comboBox_2.currentText())

    def init_trajectory(self):
        self.traj_manager.init(int(self.comboBox_3.currentText()))

    def read_trajectory_info(self):
        self.traj_manager.read_info()

    def run_scan(self):
        if self.shutter_a.value == 1 or self.shutter_b.value == 1:
            ret = self.questionMessage('Shutter closed', 'Would you like to run the scan with the shutter closed?')    
            if not ret:
                print ('Aborted!')
                return False 

        self.comment = self.params2[0].text()
        if(self.comment):
            print('\nStarting scan...')

            # Get parameters from the widgets and organize them in a tuple (run_params)
            run_params = ()
            for i in range(len(self.params1)):
                if (self.param_types[i] == int):
                    run_params += (self.params2[i].value(),)
                elif (self.param_types[i] == float):
                    run_params += (self.params2[i].value(),)
                elif (self.param_types[i] == bool):
                    run_params += (bool(self.params2[i].checkState()),)
                else:
                    run_params += (self.params2[i].text(),)
            
            # Erase last graph
            ax = self.figure.add_subplot(111)
            ax.cla()
            self.canvas.draw()

            # Run the scan using the tuple created before
            self.current_uid, self.current_filepath, absorp = self.plan_funcs[self.run_type.currentIndex()](*run_params)

            if absorp == True:
                self.parser = xasdata.XASdataAbs()
                self.parser.loadInterpFile(self.current_filepath)
                self.parser.plot(ax)
            elif absorp == False:
                self.parser = xasdata.XASdataFlu()
                self.parser.loadInterpFile(self.current_filepath)
                xia_filename = self.db[self.current_uid]['start']['xia_filename']
                xia_filepath = 'smb://elistavitski-ni/epics/{}'.format(xia_filename)
                xia_destfilepath = '/GPFS/xf08id/xia_files/{}'.format(xia_filename)
                smbclient = xiaparser.smbclient(xia_filepath, xia_destfilepath)
                smbclient.copy()
                xia_parser = self.xia_parser
                xia_parser.parse(xia_filename, '/GPFS/xf08id/xia_files/')
                xia_parsed_filepath = self.current_filepath[0 : self.current_filepath.rfind('/') + 1]
                xia_parser.export_files(dest_filepath = xia_parsed_filepath, all_in_one = True)
            # Fix that later
                length = min(len(xia_parser.exporting_array1), len(parser.energy_interp))
                xia_parser.plot_roi(xia_filename, '/GPFS/xf08id/xia_files/', range(0, length), 1, 8, 10, ax, parser.energy_interp)
                xia_parser.plot_roi(xia_filename, '/GPFS/xf08id/xia_files/', range(0, length), 2, 8, 10, ax, parser.energy_interp)
                xia_parser.plot_roi(xia_filename, '/GPFS/xf08id/xia_files/', range(0, length), 3, 8, 10, ax, parser.energy_interp)
                xia_parser.plot_roi(xia_filename, '/GPFS/xf08id/xia_files/', range(0, length), 4, 8, 10, ax, parser.energy_interp)

            if absorp != '':
                ax.set_title(self.comment)

                self.log_path = self.current_filepath[0 : self.current_filepath.rfind('/') + 1] + 'log/'
                if(not os.path.exists(self.log_path)):
                    os.makedirs(self.log_path)

                self.snapshots_path = self.log_path + 'snapshots/'
                if(not os.path.exists(self.snapshots_path)):
                    os.makedirs(self.snapshots_path)

                self.file_path = 'snapshots/' + self.comment + '.png'
                fn = self.log_path + self.file_path
                repeat = 1
                while(os.path.isfile(fn)):
                    repeat += 1
                    self.file_path = 'snapshots/' + self.comment + '-' + str(repeat) + '.png'
                    fn = self.log_path + self.file_path
                self.figure.savefig(fn)

                self.canvas.draw()

        else:
            print('\nPlease, type a comment about the scan in the field "comment"\nTry again')


    def re_abort(self):
        self.RE.abort()


    def update_re_state(self):
        palette = self.label_11.palette()
        if(self.RE.state == 'idle'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(193, 140, 15))
        elif(self.RE.state == 'running'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(0, 165, 0))
        elif(self.RE.state == 'paused'):
            palette.setColor(self.label_11.foregroundRole(), QtGui.QColor(255, 0, 0))
        self.label_11.setPalette(palette)
        self.label_11.setText(self.RE.state)
        if self.RE.state != self.RE.last_state:
            self.RE.last_state = self.RE.state


    def run_gain_matching(self):
        channels = range(4)
            
        ax = self.figure_gain_matching.add_subplot(111)
        gain_adjust = [0.001, 0.001, 0.001, 0.001]
        diff = [0, 0, 0, 0]
        diff_old = [0, 0, 0, 0]

        # Run number of iterations defined in the text edit edit_gain_matching_iterations:
        for i in range(int(self.edit_gain_matching_iterations.text())):
            self.xia.collect_mode.put('MCA spectra')
            ttime.sleep(0.25)
            self.xia.mode.put('Real time')
            ttime.sleep(0.25)
            self.xia.real_time.put('1')
            self.xia.capt_start_stop.put(1)
            ttime.sleep(0.05)
            self.xia.erase_start.put(1)
            ttime.sleep(2)
            ax.cla()

            # For each channel:
            for j in channels:
                # If checkbox of current channel is checked:
                if getattr(self, "checkBox_gm_ch{}".format(j + 1)).checkState() > 0:
        
                    # Get current channel pre-amp gain:
                    curr_ch_gain = getattr(self.xia, "pre_amp_gain{}".format(j + 1))

                    coeff = self.xia_parser.gain_matching(self.xia, self.edit_center_gain_matching.text(), 
                                              self.edit_range_gain_matching.text(), channels[j] + 1, ax)
                    # coeff[0] = Intensity
                    # coeff[1] = Fitted mean
                    # coeff[2] = Sigma

                    diff[j] = float(self.edit_gain_matching_target.text()) - float(coeff[1]*1000)

                    if i != 0:
                        sign = (diff[j] * diff_old[j]) /  math.fabs(diff[j] * diff_old[j])
                        if int(sign) == -1:
                            gain_adjust[j] /= 2
                    print('Chan ' + str(j + 1) + ': ' + str(diff[j]) + '\n')

                    # Update current channel pre-amp gain:
                    curr_ch_gain.put(curr_ch_gain.value - diff[j] * gain_adjust[j])
                    diff_old[j] = diff[j]

                    self.canvas_gain_matching.draw()


    def questionMessage(self, title, question):    
        reply = QtGui.QMessageBox.question(self, title,
                question,
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        if reply == QtGui.QMessageBox.Yes:
            return True
        elif reply == QtGui.QMessageBox.No:
            return False
        else:
            return False

# Class to write terminal output to screen
class EmittingStream(QtCore.QObject):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer = sys.__stdout__.buffer
        self.close = sys.__stdout__.close
        self.closed = sys.__stdout__.closed
        self.detach = sys.__stdout__.detach
        self.encoding = sys.__stdout__.encoding
        self.errors = sys.__stdout__.errors
        self.fileno = sys.__stdout__.fileno
        self.flush = sys.__stdout__.flush
        self.isatty = sys.__stdout__.isatty
        self.line_buffering = sys.__stdout__.line_buffering
        self.mode = sys.__stdout__.mode
        self.name = sys.__stdout__.name
        self.newlines = sys.__stdout__.newlines
        self.read = sys.__stdout__.read
        self.readable = sys.__stdout__.readable
        self.readlines = sys.__stdout__.readlines
        self.seek = sys.__stdout__.seek
        self.seekable = sys.__stdout__.seekable
        #self.softspace = sys.__stdout__.softspace
        self.tell = sys.__stdout__.tell
        self.truncate = sys.__stdout__.truncate
        self.writable = sys.__stdout__.writable
        self.writelines = sys.__stdout__.writelines

    textWritten = QtCore.pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))
        # Comment next line if the output should be printed only in the GUI
        sys.__stdout__.write(text)

#    @property
#    def plan(self):
#        lp = LivePlot(self.plot_x,
#                      self.plot_y,
#                      fig=self.fig)

#        @subs_decorator([lp])
#        def scan_gui_plan():
#            return (yield from self.plan_func(self.dets, *self.get_args()))


#def tune_factory(motor):
#    from bluesky.plans import scan
#    from collections import ChainMap

#    def tune(md=None):
#        if md is None:
#            md = {}
#        md = ChainMap(md, {'plan_name': 'tuning {}'.format(motor)})
#        yield from scan(motor, -1, 1, 100, md=md)

#    return tune


