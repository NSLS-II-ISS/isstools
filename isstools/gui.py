# Temperature-conversion program using PyQt
import numpy as np
from PyQt4 import uic
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'ui/XLive.ui')

def my_plan(dets, some, other, param):
	...


def auto_redraw_factory(fnc):

    def stale_callback(fig, stale):
        if fnc is not None:
            fnc(fig, stale)
        if stale and fig.canvas:
            fig.canvas.draw_idle()

    return stale_callback


class ScanGui(*uic.loadUiType(ui_path)):
    def __init__(self, plan_func, parent=None):
        super().__init__(parent)
        self.plan_func = plan_func
        self.setupUi(self)
        self.fig = fig = self.figure_content()
        self.addCanvas(fig)
        self.run_start.clicked.connect(self.test)

    def addCanvas(self, fig):
        self.canvas = FigureCanvas(fig)

        self.toolbar = NavigationToolbar(self.canvas,
                                         self.tab_2, coordinates=True)
        self.toolbar.setMaximumHeight(18)
        self.plots.addWidget(self.toolbar)
        self.plots.addWidget(self.canvas)
        self.canvas.draw()

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

    def test(self):
        self.plan_func()


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


