import time
import random
import numpy as np

from qtpy.QtCore import Signal, QByteArray, QPoint, QPointF, QRect, QSize, QTimer, Qt, QObject, QUrl
from qtpy.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPolygon
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


# class CustomQPoint(QPoint):
#
#     @property
#     def xy(self):
#         return self.x(), self.y()

class CustomQPolygon(QPolygon):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dragging_index = None
        self.dragging_whole = None
        self.whole_ref_point = None

    def distance_to_vertices(self, point : QPoint):

        if self.count() == 0:
            return None

        x, y = point.x(), point.y()

        dist = []
        for i in range(self.count()):
            point_i = self.at(i)
            x_i, y_i = point_i.x(), point_i.y()
            dist_i = np.sqrt((x - x_i) ** 2 + (y - y_i) ** 2)
            dist.append(dist_i)

        return np.array(dist)

    def closest_point_index(self, point : QPoint, margin=30):
        dist = self.distance_to_vertices(point)
        if dist is not None:
            idx = dist.argmin()
            val = dist.min()
            if val < margin:
                return idx

        return None

    def closest_point(self, point):
        index = self.closest_point_index(point)
        if index is not None:
            return self.at(index)
        return None

    def close_to_center(self, point):
        x = point.x()
        y = point.y()

        rect = self.boundingRect()
        cen = rect.center()
        x_cen = cen.x()
        y_cen = cen.y()
        rx = rect.width() / 4
        ry = rect.height() / 4

        dist = np.sqrt(((x - x_cen) / rx)**2 + ((y - y_cen) / ry)**2)

        return (dist < 1) or None

    def start_drag(self, point):
        if self.dragging_index is None:
            self.dragging_index = self.closest_point_index(point)
        if self.dragging_index is None:
            if self.dragging_whole is None:
                self.dragging_whole = self.close_to_center(point)
                self.whole_ref_point = point

    def drag(self, point):
        if self.dragging_index is not None:
            self.drag_point(point)
            return

        if self.dragging_whole is not None:
            self.drag_whole(point)
            return

    def drag_point(self, point):
        print(self.dragging_index)
        self.setPoint(self.dragging_index, point)

    def drag_whole(self, point):
        dx = point.x() - self.whole_ref_point.x()
        dy = point.y() - self.whole_ref_point.y()
        self.translate(dx, dy)
        self.whole_ref_point = point

    def stop_drag(self):
        self.dragging_index = None
        self.dragging_whole = None
        self.whole_ref_point = None

    def remove_point(self, point):
        remove_index = self.closest_point_index(point)
        print(remove_index)
        if remove_index is not None:
            self.remove(remove_index)

    @property
    def coordinate_list(self):
        output = []
        for i in range(self.count()):
            output.append([self.at(i).x(), self.at(i).y()])
        return output

class Microscope(QWidget):
    roiClicked = Signal(int, int)
    polygonDrawingSignal = Signal(QPoint)

    def __init__(self, parent=None, mark_direction = 1):
        #mark_direction = 0 for horizontal, 1 for vertical
        super(Microscope, self).__init__(parent)
        self.parent_gui = parent
        self.setMinimumWidth(300)
        self.setMinimumHeight(300)
        self.image = QImage('image.jpg')

        self.clicks = []
        self.center = QPoint(
            self.image.size().width() / 2, self.image.size().height() / 2
        )
        self.mark_direction = mark_direction
        self.mark_location = QPoint(self.parent_gui.settings.value('beam_position_x', defaultValue=600, type=float),
                                    self.parent_gui.settings.value('beam_position_y', defaultValue=450, type=float))
        self.mark_location_set = True
        self.color = False
        self.fps = 5
        self.scaleBar = False


        self.url = 'http://localhost:9998/jpg/image.jpg'

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateImage)

        self.downloader = Downloader(self)
        self.downloader.imageReady.connect(self.updateImageData)

        self.calibration_polygon = CustomQPolygon()

        self.A_xy2px = None
        self.A_xy2py = None
        self.beam_position = 0



    @property
    def mode(self):
        return self.parent().parent().interaction_mode

    @property
    def draw_calibration_isChecked(self):
        return self.parent().parent().checkBox_draw_calibration.isChecked()

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
        # tic = time.perf_counter()
        painter = QPainter(self)
        rect = event.rect()
        # self.image = self.image.scaledToWidth(200)
        painter.drawImage(rect, self.image, rect, flags=Qt.ThresholdDither)

        painter.setPen(QColor.fromRgb(0, 255, 0))
        if self.mark_location:
            #print(f' Mark location {self.mark_location.x()} -  {self.mark_location.y()}')
            if self.mark_direction == 1:
                painter.drawLine(self.mark_location.x(),self.center.y()-200, self.mark_location.x(), self.center.y()+200)
            elif self.mark_direction == 0:
                painter.drawLine(self.center.x()-200, self.mark_location.y(), self.center.x() + 200, self.mark_location.y())

        painter.drawPolygon(self.calibration_polygon)

        # #Draw the center mark
        painter.setPen(QColor.fromRgb(255, 0, 0))
        painter.drawLine(
             self.center.x() - 20, self.center.y(), self.center.x() + 20, self.center.y()
        )
        painter.drawLine(
             self.center.x(), self.center.y() - 20, self.center.x(), self.center.y() + 20
        )

        # draw calibration
        if (self.A_xy2px is not None) and (self.A_xy2py is not None):
            if self.draw_calibration_isChecked:

                painter.setPen(QColor.fromRgb(0, 0, 255))

                dx = self.A_xy2px @ [1, 0]
                dy = self.A_xy2py @ [1, 0]

                for y in range(0, 1000, 100):
                    painter.drawLine(1000, y, 1000+dx*150, y+dy*150)

                dx = self.A_xy2px @ [0, 1]
                dy = self.A_xy2py @ [0, 1]

                for x in range(0, 1000, 100):
                    painter.drawLine(x, 1000, x + dx * 150, 1000 + dy * 150)


    def mousePressEvent(self, event):

        pos = event.pos()
        # print(pos, type(pos))

        if event.button() == Qt.RightButton:

            if self.mode == 'calibration':
                self.polygonDrawingSignal.emit(pos)
                self.calibration_polygon.append(pos)

            elif self.mode == 'default':
                self.mark_beam_location(pos)

        elif event.button() == Qt.LeftButton:
            if self.mode == 'calibration':
                self.calibration_polygon.start_drag(pos)


    def mark_beam_location(self, pos):
        if self.mark_location_set:
            ret = question_message_box(self, 'Warning', 'Do you want to redefine beam location mark')
            if not ret:
                return
        self.roiClicked.emit(pos.x(), pos.y())
        self.mark_location = pos
        self.mark_location_set = True

        if self.mark_direction == 1:
            self.parent_gui.settings.setValue('beam_position_x', self.mark_location.x())
        elif self.mark_direction == 0:
            self.parent_gui.settings.setValue('beam_position_y', self.mark_location.y())

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self.mode == 'calibration':
            self.calibration_polygon.drag(pos)



    def mouseReleaseEvent(self, event):
        pos = event.pos()
        if event.button() == Qt.LeftButton:
            if self.mode == 'calibration':
                self.calibration_polygon.stop_drag()


    def mouseDoubleClickEvent(self, event):
        print(event, event.button())
        pos = event.pos()
        if event.button() == Qt.LeftButton:
            if self.mode == 'calibration':
                self.calibration_polygon.remove_point(pos)


    def sizeHint(self):
        return QSize(400, 400)

    def updateImage(self):
        """ Request an updated image asynchronously. """
        self.downloader.downloadData()

    def updateImageData(self, image):
        """ Triggered when the new image is ready, update the view. """
        self.image.loadFromData(image, 'JPG')
        self.image = self.image.scaledToWidth(600)


        # for i in range(self.image.size().width()):
        #     for j in range(self.image.size().height()):
        #         _c = self.image.pixelColor(i, j).value()
        #         if _c > 50:
        #             self.image.setPixelColor(i, j, QColor(50))


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
