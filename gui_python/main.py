import sys
import time
import queue
import serial
import struct
import threading
import collections

import random

from functools import partial

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

from PyQt6.QtSerialPort import QSerialPortInfo, QSerialPort


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
    # marker = [msg]
def read_uart():
    marker = "[msg]"
    tipos = ["EJE", "AMB"]
    ejes = "XYZ"
    tipo = random.choice(tipos)
    if tipo == "EJE":
        msg = f"{tipo},{random.choice(ejes)},{round(random.random(), 2)}"
    else:
        msg = f"{tipo},{round(random.random(), 1)},{random.randint(20, 40)}"
    return f"{marker}{len(msg) + len("\r\n")}{msg}\r\n".encode()

def uart_decoder(msg: bytes):
    marker = b"[msg]"
    beg = msg.find(marker)
    msg = msg[beg + len(marker):]
    msg = msg[2:]
    msg = msg.decode()
    x, y, z = msg.split(",")
    # TODO: considerar tamaño del mensaje o indicador de fin del mensaje
    return (x, y, z)
    
def send_uart(var: str, val: str):
    msg = f"{var},{val}"
    pass

# recibe los datos de la UART y envía respuestas
class DataReceiver(QObject):
    data_received_x = pyqtSignal(float)
    data_received_y = pyqtSignal(float)
    data_received_z = pyqtSignal(float)
    data_received_t = pyqtSignal(float)
    data_received_h = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.interval = 100
        self.command_queue = queue.Queue()
        self.msg_queue = queue.Queue()
        self.available_ports = QSerialPortInfo.availablePorts()
        self.port_info = None
        self.port = None
        self.baud_rate = 115200
        self.connected = False
        self.esp_init = False

    def receiver_loop(self):
        while True:
            while not self.command_queue.empty():
                command = self.command_queue.get_nowait()
                command()

            #while not self.msg_queue.empty():
            #    msg = self.msg_queue.get_nowait()
            
            msg = read_uart()
            tipo, x, y = uart_decoder(msg)
            if tipo == "EJE":
                if x == "X":
                    self.data_received_x.emit(float(y))
                elif x == "Y":
                    self.data_received_y.emit(float(y))
                else:
                    self.data_received_z.emit(float(y))
            else:
                self.data_received_t.emit(float(x))
                self.data_received_h.emit(float(y))
            time.sleep(self.interval / 1000)

    def read_uart_real(self):
        marker = b"[msg]"
        header_len = len(marker) + 2
        
        if self.port_name == None:
            print("puerto no existe")
            return

        with serial.Serial(self.port_name, baudrate=self.baud_rate, timeout=0.1) as com:
            buf = bytearray()

            while True:
                chunk = com.read(4096)

                if not chunk:
                    continue

                buf += chunk

                while True:
                    start = buf.find(marker)

                    if start < 0:
                        cut = max(0, len(buf)-len(marker))
                        print(buf[:cut].decode(errors="replace"), end="")
                        del buf[:cut]
                        break

                    if start > 0:
                        print(buf[:start].decode(errors="replace"), end="")
                        del buf[:start]

                    if len(buf) < header_len:
                        break

                    # format: little endian (<), unsigned short (H)
                    char_num, = struct.unpack_from("<H", buf, len(marker))
                    data_len = char_num * 4

                    if len(buf < header_len + data_len):
                        break

                    data = buf[header_len:header_len + data_len]
                    del buf[:header_len + data_len]

                    # format: little endian, char_num cantidad de caracteres unsigned char (b)
                    values = struct.unpack(f"<{char_num}b", data)
                    print(f"DATA POINT RECIVED: {list(values)}")

    @pyqtSlot()
    def set_port_info(self, port_name):
        def none_command():
            self.port_info = None
        print(f"port_name = {port_name}")
        if port_name == "Seleccione un puerto":
            print("no hay puertos seleccionados")
            self.command_queue.put(none_command)
            return
        selected = None
        for p in self.available_ports:
            if p.portName() == port_name:
                selected = p
        if selected == None:
            print(f"puerto {port_name} no encontrado")
            self.command_queue.put(none_command)
        else:
            # TODO: agregar conexion uart
            print(f"puerto {port_name} seleccionado exitosamente")
            def command():
                self.port_info = selected
            self.command_queue.put(command)

    @pyqtSlot()
    def connect(self, gui: Ui_MainWindow):
        if self.connected == True:
            def command():
                self.connected = False
            gui.pushButton_conect.setText("Conectar") # TODO: problemas de sincronizacion?
        else:
            if self.port_info == None:
                print("no existen puertos seleccionados")
                def command():
                    self.connected = False
            else:
                def command():
                    self.port = QSerialPort(self.port)
                    self.connected = True
                    # TODO: settear baud rate
                    # TODO: hacer la conexión real
                gui.pushButton_conect.setText("Desconectar")
        self.command_queue.put(command)

    def init_esp(self):
        def command():
            self.esp_init = True
            print("inicializando esp")
        self.command_queue.put(command)

    @pyqtSlot()
    def set_amb_interval(self, val: int):
        def command():
            self.amb_interval = val
        print(f"intervalo de muestreo ambientales: {val}")
        self.command_queue.put(command)

    @pyqtSlot()
    def set_baud_rate(self, rate: int):
        if (rate != None):
            print(f"baud_rate nuevo: {rate}")
            def command():
                self.baud_rate = rate
            self.command_queue.put(command)
        
def setDefaults(gui: Ui_MainWindow):
    frec_boxes = [gui.comboBox_frec_x, gui.comboBox_frec_y, gui.comboBox_frec_z]
    for b in frec_boxes:
        b.setCurrentIndex(b.findText("100 Hz"))
    gui.radioButton_30s.setChecked(True)
    gui.spinBox_baud_rate.setMaximum(999999)
    gui.spinBox_baud_rate.setValue(115200)

    ports = QSerialPortInfo.availablePorts()
    gui.comboBox_puerto.addItem("Seleccione un puerto")
    if ports != None:
        for p in ports:
            gui.comboBox_puerto.addItem(p.portName())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QMainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(window)
    setDefaults(gui)

    plot_x = LivePlot()
    gui.plot_x.addWidget(plot_x)

    plot_y = LivePlot()
    gui.plot_y.addWidget(plot_y)

    plot_z = LivePlot()
    gui.plot_z.addWidget(plot_z)

    plot_t = LivePlot()
    gui.plot_temp.addWidget(plot_t)

    # TODO: cambiar a tipo int
    plot_h = LivePlot()
    gui.plot_humid.addWidget(plot_h)

    receiver = DataReceiver()
    thread = threading.Thread(target=receiver.receiver_loop, daemon=True)
    receiver.data_received_x.connect(plot_x.add_point)
    receiver.data_received_y.connect(plot_y.add_point)
    receiver.data_received_z.connect(plot_z.add_point)
    receiver.data_received_t.connect(plot_t.add_point)
    receiver.data_received_h.connect(plot_h.add_point)

    # configuración
    gui.comboBox_puerto.currentTextChanged[str].connect(lambda texto: receiver.set_port_info(texto))
    gui.spinBox_baud_rate.valueChanged.connect(lambda rate: receiver.set_baud_rate(rate))
    gui.pushButton_conect.pressed.connect(partial(receiver.connect, gui))
    gui.pushButton_init_esp.pressed.connect(receiver.init_esp)

    # variables ambientales
    gui.radioButton_30s.pressed.connect(partial(receiver.set_amb_interval, 30))
    gui.radioButton_60s.pressed.connect(partial(receiver.set_amb_interval, 60))

    thread.start()
    window.show()
    app.exec()