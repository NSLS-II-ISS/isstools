# Temperature-conversion program using PyQt
import numpy as np
from PyQt4 import uic, QtGui
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import pkg_resources

from filestore.fs import FileStore
from databroker import Broker
from metadatastore.mds import MDS
mds = MDS({'host':'xf08id-ca1.cs.nsls2.local', 
	   'database': 'datastore', 'port': 27017, 'timezone': 'US/Eastern'}, auth=False)
db = Broker(mds, FileStore({'host':'xf08id-ca1.cs.nsls2.local', 'port': 27017, 'database':'filestore'}))

from isstools.trajectory.trajectory  import trajectory
from isstools.trajectory.trajectory import trajectory_manager
from isstools.xasmodule import xasmodule
import os
from os import listdir
from os.path import isfile, join

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
    def __init__(self, plan_func, RE, hhm, parent=None):
        super().__init__(parent)
        self.plan_func = plan_func
        self.setupUi(self)
        #self.fig = fig = self.figure_content()
        self.addCanvas()
        self.run_start.clicked.connect(self.run_scan)
        self.push_build_trajectory.clicked.connect(self.build_trajectory)
        self.push_save_trajectory.clicked.connect(self.save_trajectory)
        self.label_6.setText('{}'.format(RE.md['year']))
        self.label_7.setText('{}'.format(RE.md['cycle']))
        self.label_8.setText('{}'.format(RE.md['PROPOSAL']))
        self.label_9.setText('{}'.format(RE.md['SAF']))
        self.label_10.setText('{}'.format(RE.md['PI']))

        self.traj = trajectory()
        self.traj_manager = trajectory_manager(hhm)
        self.trajectory_path = '/GPFS/xf08id/trajectory/'
        self.get_traj_names()
        self.comboBox_2.addItems(['1', '2', '3', '4', '5', '6', '7', '8', '9'])
        self.comboBox_3.addItems(['1', '2', '3', '4', '5', '6', '7', '8', '9'])
        self.comboBox_3.setCurrentIndex(self.traj_manager.current_lut() - 1)
        self.push_load_trajectory.clicked.connect(self.load_trajectory)
        self.push_init_trajectory.clicked.connect(self.init_trajectory)

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

        self.figure_full_trajectory= Figure()
        self.figure_full_trajectory.set_facecolor(color='0.89')
        self.canvas_full_trajectory = FigureCanvas(self.figure_full_trajectory)
        self.plot_full_trajectory.addWidget(self.canvas_full_trajectory)
        self.plot_full_trajectory.addWidget(self.canvas_full_trajectory)
        self.canvas_full_trajectory.draw()

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

    def build_trajectory(self):
        E0 = int(self.edit_E0.text())
        preedge_lo = int(self.edit_preedge_lo.text())
        preedge_hi = int(self.edit_preedge_hi.text())
        edge_hi = int(self.edit_edge_hi.text())
        postedge_hi = int(self.edit_postedge_hi.text())

        velocity_preedge = int (self.edit_velocity_preedge.text())
        velocity_edge = int(self.edit_velocity_edge.text())
        velocity_postedge = int(self.edit_velocity_postedge.text())

        preedge_stitch_lo = int(self.edit_preedge_stitch_lo.text())
        preedge_stitch_hi = int(self.edit_preedge_stitch_hi.text())
        edge_stitch_lo =  int(self.edit_edge_stitch_lo.text())
        edge_stitch_hi = int(self.edit_edge_stitch_hi.text())
        postedge_stitch_lo = int(self.edit_postedge_stitch_lo.text())
        postedge_stitch_hi = int(self.edit_postedge_stitch_hi.text())

        padding_preedge = int(self.edit_padding_preedge.text())
        padding_postedge = int(self.edit_padding_postedge.text())

        #Create and interpolate trajectory
        self.traj.define(edge_energy = E0, offsets = ([preedge_lo,preedge_hi,edge_hi,postedge_hi]),velocities = ([velocity_preedge, velocity_edge, velocity_postedge]),\
                        stitching = ([preedge_stitch_lo, preedge_stitch_hi, edge_stitch_lo, edge_stitch_hi, postedge_stitch_lo, postedge_stitch_hi]),\
                        servocycle = 16000, padding_lo = padding_preedge ,padding_hi=padding_postedge)
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
        self.traj.tile(reps=5)

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

    def run_scan(self):
        self.comment = self.run_comment.text()
        if(self.comment):
            print('\nStarting scan...')
            self.current_uid, self.current_filepath = self.plan_func(self.comment)
            print('current_uid:', self.current_uid)
            print('current_path:', self.current_filepath)

            xas_abs = xasmodule.XASdataAbs()
            xas_abs.load(self.current_filepath)

            ax = self.figure.add_subplot(111)
            xas_abs.plot(ax)

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
            print('\nPlease, type a comment about the scan in the field "Run name"\nTry again')

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


