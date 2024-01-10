import pkg_resources
from PyQt5 import uic


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_tutorial.ui')

'''
STEP 1
class TutorialGui(*uic.loadUiType(ui_path)):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.pushButton_run.clicked.connect(self.run)


    def run(self):
        print('Hello world!')
        pass
'''

'''
STEP 2
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor


class TutorialGui(*uic.loadUiType(ui_path)):

    def __init__(self,
                 RE=None,
                 db=None,
                 plans=None,
                 
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.RE = RE
        self.db = db
        self.plans = plans  
        self.pushButton_run.clicked.connect(self.run)

        #setting up the figure
        figure = Figure()
        figure.set_facecolor(color='#FcF9F6')
        canvas = FigureCanvas(figure)
        figure.ax = figure.add_subplot(111)
        toolbar = NavigationToolbar(canvas, self, coordinates=True)
        self.layout_spectrum.addWidget(toolbar)
        self.layout_spectrum.addWidget(canvas)
        canvas.draw_idle()
        cursor = Cursor(figure.ax, useblit=True, color='green', linewidth=0.75)
        figure.ax.grid(alpha=0.4)




    def run(self):
        print('Hello world!')
        pass
'''

# STEP 3
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor

from xas.process import get_processed_df_from_uid


class TutorialGui(*uic.loadUiType(ui_path)):

    def __init__(self,
                 RE=None,
                 db=None,
                 plans=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.RE = RE
        self.db = db
        self.plans = plans
        self.pushButton_run.clicked.connect(self.run)
        self.pushButton_show.clicked.connect(self.show_data)

        #setting up the figure
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.figure.ax = self.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self, coordinates=True)
        self.layout_spectrum.addWidget(self.toolbar)
        self.layout_spectrum.addWidget(self.canvas)
        self.canvas.draw_idle()
        self.cursor = Cursor(self.figure.ax, useblit=True, color='green', linewidth=0.75)
        self.figure.ax.grid(alpha=0.4)

    def run(self):
        self.RE(self.plans[0](name = 'test',trajectory_filename='2fd68c04-0e60.txt',element='Se',e0=12658))

        pass

    def show_data(self):
        # uid= 'e0289523-d4dd-4c2b-952b-eba2b4118cab'
        raw_dataset = get_processed_df_from_uid(-1, self.db)
        data = raw_dataset[1]
        self.figure.ax.plot(data['energy'], data['iff']/data['i0'])
        self.canvas.draw_idle()







