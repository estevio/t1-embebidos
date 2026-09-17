import sys
import time
import queue
import random
import threading
import collections

from functools import partial

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

from PyQt6.QtSerialPort import QSerialPortInfo
from PyQt6.QtGui import QValidator


from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtWidgets import QApplication, QMainWindow

#from eje_accelerometro import Ui_WidgetEje
from app import Ui_MainWindow

class LivePlot(FigureCanvasQTAgg):
    def __init__(self, max_points: int = 100, fps: int = 30):
        super().__init__()

        self.axes = self.figure.subplots()
        self.time_pts = collections.deque(maxlen = max_points)
        self.data_pts = collections.deque(maxlen = max_points)
        (self.line, ) = self.axes.plot(self.time_pts, self.data_pts, 'b-')
        self.init_time = time.time()

        self.drawing_timer = self.new_timer(1000 // fps)
        self.drawing_timer.add_callback(self.redraw)
        self.drawing_timer.start()

    def redraw(self):
        self.line.set_data(self.time_pts, self.data_pts)
        self.axes.relim()
        self.axes.autoscale_view()
        self.draw_idle()

    @pyqtSlot(float)
    def add_point(self, point: float):
        self.time_pts.append(time.time() - self.init_time)
        self.data_pts.append(point)

# posibles mensajes:
# "EJE,[ID],[pt]\r\n" ID = X, Y, X; pt = float de 2 decimales
# "AMB,[Temp],[Humid]\r\n" Temp = float de 1 decima; Humid = entero en decimal
def read_uart():
    return random.random() * 5

# recibe los datos para un gráfico
class DataReceiver(QObject):
    data_received = pyqtSignal(float)

    def __init__(self, interval: int = 100):
        super().__init__()
        self.interval = interval
        self.command_queue = queue.Queue()
        # self.port = None
        self.baud_rate = 11520

    def receiver_loop(self):
        while True:
            while not self.command_queue.empty():
                command = self.command_queue.get_nowait()
                command()

            point = read_uart()
            self.data_received.emit(point)
            time.sleep(self.interval / 1000)

    @pyqtSlot()
    def set_amb_interval(self, val: int):
        def command():
            self.amb_interval = val
        self.command_queue.put(command)

    @pyqtSlot()
    def set_baud_rate(self, rate: int):
        if (rate != None):
            # print("changing baud rate!")
            def command():
                self.baud_rate = rate
            self.command_queue.put(command)
        

def setDefaults(controller: Ui_MainWindow):
    frec_boxes = [controller.comboBox_frec_x, controller.comboBox_frec_y, controller.comboBox_frec_z]
    for b in frec_boxes:
        b.setCurrentIndex(b.findText("100 Hz"))
    controller.radioButton_30s.setChecked(True)
    controller.spinBox_baud_rate.setMaximum(999999)
    controller.spinBox_baud_rate.setValue(11520)

    ports = QSerialPortInfo.availablePorts()
    if ports != None:
        for p in ports:
            controller.comboBox_puerto.addItem(p.portName())



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QMainWindow()
    controller = Ui_MainWindow()
    controller.setupUi(window)
    setDefaults(controller)

    plot_x = LivePlot()
    controller.plot_x.addWidget(plot_x)

    receiver = DataReceiver()
    thread = threading.Thread(target=receiver.receiver_loop, daemon=True)
    receiver.data_received.connect(plot_x.add_point)    

    controller.spinBox_baud_rate.valueChanged.connect(partial(receiver.set_baud_rate, 
                                                              controller.spinBox_baud_rate.value))
    controller.radioButton_30s.pressed.connect(partial(receiver.set_amb_interval, 1))
    controller.radioButton_60s.pressed.connect(partial(receiver.set_amb_interval, 5))

    thread.start()
    window.show()
    app.exec()