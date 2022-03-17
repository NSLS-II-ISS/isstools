import time
import random

from qtpy.QtCore import Signal, QByteArray, QPoint, QRect, QSize, QTimer, Qt, QObject, QUrl
from qtpy.QtGui import QBrush, QColor, QFont, QImage, QPainter
from qtpy.QtWidgets import QWidget
from isstools.dialogs.BasicDialogs import message_box, question_message_box

from qtpy.QtNetwork import QNetworkRequest, QNetworkAccessManager

class Downloader(QObject):
    imageReady = Signal(QByteArray)

    def __init__(self, parent=None):
        super(Downloader, self).__init__(parent)
        self.manager = QNetworkAccessManager()
        self.url = 'http://localhost:9998/jpg/image.jpg'
        self.request = QNetworkRequest()
        self.request.setUrl(QUrl(self.url))
        self.buffer = QByteArray()
        self.reply = None

    def setUrl(self, url):
        self.url = url
        self.request.setUrl(QUrl(self.url))

    def downloadData(self):
        """ Only request a new image if this is the first/last completed. """
        if self.reply is None:
            self.reply = self.manager.get(self.request)
            self.reply.finished.connect(self.finished)

    def finished(self):
        """ Read the buffer, emit a signal with the new image in it. """
        self.buffer = self.reply.readAll()
        self.imageReady.emit(self.buffer)
        self.reply.deleteLater()
        self.reply = None


class Microscope(QWidget):
    roiClicked = Signal(int, int)

    def __init__(self, parent=None, mark_direction = 1):
        #mark_direction = 0 for horizontal, 1 for vertical
        super(Microscope, self).__init__(parent)

        self.setMinimumWidth(300)
        self.setMinimumHeight(300)
        self.image = QImage('image.jpg')

        self.clicks = []
        self.center = QPoint(
            self.image.size().width() / 2, self.image.size().height() / 2
        )
        self.mark_direction = mark_direction
        self.mark_location = None
        self.mark_location_set = False
        self.color = False
        self.fps = 5
        self.scaleBar = False

        self.url = 'http://localhost:9998/jpg/image.jpg'

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateImage)

        self.downloader = Downloader(self)
        self.downloader.imageReady.connect(self.updateImageData)

    def updatedImageSize(self):
        if self.image.size() != self.minimumSize():
            self.setMinimumSize(self.image.size())
            self.center = QPoint(
                self.image.size().width() / 2, self.image.size().height() / 2
            )

    def acquire(self, start=True):
        self.downloader.setUrl(self.url)
        if start:
            self.timer.start(1000.0 / self.fps)
        else:
            self.timer.stop()

    def paintEvent(self, event):
        tic = time.perf_counter()
        painter = QPainter(self)
        rect = event.rect()
        #self.image = self.image.scaledToWidth(780)
        painter.drawImage(rect, self.image, rect)

        painter.setPen(QColor.fromRgb(0, 255, 0))
        if self.mark_location:
            #print(f' Mark location {self.mark_location.x()} -  {self.mark_location.y()}')
            if self.mark_direction == 1:
                painter.drawLine(self.mark_location.x(),self.center.y()-200, self.mark_location.x(), self.center.y()+200)
            elif self.mark_direction == 0:
                painter.drawLine(self.center.x()-200, self.mark_location.y(), self.center.x() + 200, self.mark_location.y())

        #Draw the center mark
        painter.setPen(QColor.fromRgb(255, 0, 0))
        painter.drawLine(
             self.center.x() - 20, self.center.y(), self.center.x() + 20, self.center.y()
        )
        painter.drawLine(
             self.center.x(), self.center.y() - 20, self.center.x(), self.center.y() + 20
        )
 
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.mark_location_set:
                ret = question_message_box(self, 'Warning', 'Do you want to redefine beam location mark')
                if not ret:
                    return

            pos = event.pos()
            self.roiClicked.emit(pos.x(), pos.y())
            self.mark_location = pos

            self.mark_location_set = True
        elif event.button() == Qt.LeftButton:
            pos = event.pos()
            self.zoom_location_start = pos
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()

            self.zoom_location_end = pos



    # def mouseMoveEvent(self, event):
    #     self.end = event.pos()
    #     self.update()

    def sizeHint(self):
        return QSize(400, 400)

    def updateImage(self):
        """ Request an updated image asynchronously. """
        self.downloader.downloadData()

    def updateImageData(self, image):
        """ Triggered when the new image is ready, update the view. """
        self.image.loadFromData(image, 'JPG')
        self.image = self.image.scaledToWidth(750)

        self.updatedImageSize()
        self.update()

    def readFromDict(self, settings):
        """ Read the settings from a Python dict. """
        if settings.has_key('url'):
            self.url = settings['url']
        if settings.has_key('fps'):
            self.fps = settings['fps']
        if settings.has_key('xDivs'):
            self.xDivs = settings['xDivs']
        if settings.has_key('yDivs'):
            self.yDivs = settings['yDivs']
        if settings.has_key('color'):
            self.color = settings['color']

    def writeToDict(self):
        """ Write the widget's settings to a Python dict. """
        settings = {
            'url': self.url,
            'fps': self.fps,
            'xDivs': self.xDivs,
            'yDivs': self.yDivs,
            'color': self.color
        }
        return settings

    def readSettings(self, settings):
        """ Read the settings for this microscope instance. """
        self.url = settings.value('url', 'http://localhost:9998/jpg/image.jpg')
        self.fps = settings.value('fps', 5, type=int)
        self.xDivs = settings.value('xDivs', 5, type=int)
        self.yDivs = settings.value('yDivs', 5, type=int)
        self.color = settings.value('color', False, type=bool)

    def writeSettings(self, settings):
        """ Write the settings for this microscope instance. """
        settings.setValue('url', self.url)
        settings.setValue('fps', self.fps)
        settings.setValue('xDivs', self.xDivs)
        settings.setValue('yDivs', self.yDivs)
        settings.setValue('color', self.color)
