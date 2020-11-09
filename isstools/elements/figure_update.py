from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor



def update_figure(axes, toolbar, canvas):
    for ax in axes:
        ax.clear()
        cursor = Cursor(ax, useblit=True, color='green', linewidth=0.75)
    toolbar.update()
    canvas.draw_idle()
    axes[-1].grid(alpha=0.4)


def update_figure_with_colorbar(axes, toolbar, canvas,figure):
    if len(figure.axes) >1:
        figure.axes[-1].remove()
    for ax in axes:
        ax.clear()
        cursor = Cursor(ax, useblit=True, color='green', linewidth=0.75)

    toolbar.update()
    canvas.draw_idle()
    axes[-1].grid(alpha=0.4)


def setup_figure(parent, layout):
    figure = Figure()
    figure.set_facecolor(color='#FcF9F6')
    canvas = FigureCanvas(figure)
    figure.ax = figure.add_subplot(111)
    toolbar = NavigationToolbar(canvas, parent, coordinates=True)
    layout.addWidget(toolbar)
    layout.addWidget(canvas)
    canvas.draw_idle()
    cursor = Cursor(figure.ax, useblit=True, color='green', linewidth=0.75)
    figure.ax.grid(alpha=0.4)
    figure.tight_layout()

    return figure, canvas,toolbar



