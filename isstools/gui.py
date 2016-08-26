# Temperature-conversion program using PyQt
import numpy as np
from PyQt4 import QtGui, uic
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'ui/XLive.ui')


def auto_redraw_factory(fnc):

    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback


class ScanGui(*uic.loadUiType(ui_path)):
    def __init__(self, motor, dets, parent=None):
        super().__init__(parent)
        self.motor = motor
        self.dets = dets
        self.setupUi(self)
        self.fig = fig = self.figure_content()
        self.addCanvas(fig)

    def addCanvas(self, fig):
        self.canvas = FigureCanvas(fig)

        self.toolbar = NavigationToolbar(self.canvas,
                                         self.tab_2, coordinates=True)
        self.toolbar.setMaximumHeight(18)
        self.plots.addWidget(self.toolbar)
        self.plots.addWidget(self.canvas)
        self.canvas.draw()

    def figure_content(self):
        fig1 = Figure()
        fig1.set_facecolor(color='0.89')
        fig1.stale_callback = auto_redraw_factory(fig1.stale_callback)
        ax1f1 = fig1.add_subplot(111)
        ax1f1.plot(np.random.rand(5))
        self.ax = ax1f1
        return fig1

    @property
    def plan(self):
        from bluesky.plans import subs_decorator, scan
        from bluesky.callbacks import LiveTable, LivePlot
        from bluesky.utils import first_key_heuristic

        lp = LivePlot(first_key_heuristic(self.dets[0]),
                      first_key_heuristic(self.motor),
                      fig=self.fig)

        @subs_decorator([LiveTable([self.motor] + self.dets), lp])
        def scan_gui_plan():
            yield from scan(self.dets,
                            self.motor, self.start.value(), self.stop.value(),
                            self.steps.value(),
                            md={'created_by': 'GUI'})

        return scan_gui_plan()
