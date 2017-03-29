
import sys, os
import numpy as np
from PyQt4 import QtGui, uic
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import  FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar

gui_form = uic.loadUiType("Xview.ui")[0]  # Load the UI

class MyWindowClass(QtGui.QMainWindow, gui_form):
    def __init__(self, parent=None):
        self.WorkingFolder = [];
        QtGui.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.pushbutton_SelectFolder.clicked.connect(self.selectFolder)

    def addCanvas(self, fig):
        self.canvas = FigureCanvas(fig)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setMaximumHeight(25)
        self.layout_plotRaw.addWidget(self.toolbar)
        self.layout_plotRaw.addWidget(self.canvas)
        self.canvas.draw()

    def figure_content(self):
        fig1 = Figure()
        fig1.set_facecolor(color='0.89')
        ax1f1 = fig1.add_subplot(111)
        ax1f1.plot(np.random.rand(5))
        return fig1

    def selectFolder(self):
        self.CurrentFolder = QtGui.QFileDialog.getExistingDirectory(self, "Open a folder", "", QtGui.QFileDialog.ShowDirsOnly)
        self.label_CurrentFolder.setText(self.CurrentFolder[1:20] + '...' + self.CurrentFolder[-30:])
        self.label_CurrentFolder.setToolTip(self.CurrentFolder)
        self.getRawDataFileList()

    def getRawDataFileList(self):
        rawFiles = [f for f in os.listdir(self.CurrentFolder) if f.endswith('.ui')]
        self.list_RawFiles.addItems(rawFiles)


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    main = MyWindowClass()
    fig=main.figure_content()
    main.addCanvas(fig)
    main.show()

    sys.exit(app.exec_())