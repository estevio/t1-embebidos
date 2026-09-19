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

from app import Ui_MainWindow

class LivePlot(FigureCanvasQTAgg):
    """
    Una clase que representa un gráfico de la GUI

    Atributos:
        time_pts: colección de puntos que representa el tiempo
        data_pts: colección de puntos que representa el valor de las mediciones
        init_time: tiempo de inicialización del gráfico
        drawing_timer: timer para graficar el siguiente punto
    """

    # TODO: agregar posibilidad de graficar enteros

    def __init__(self, max_points: int = 100, fps: int = 30):
        """
        Inicializa un objeto LivePlot

        Parámetros:
            max_points (int): cantidad máxima de puntos por graficar (default: 100)
            fps (int): frecuencia de actualización del gráfico (default: 30)
        """
        super().__init__()

        self.axes = self.figure.subplots()
        self.time_pts = collections.deque(maxlen = max_points)
        self.data_pts = collections.deque(maxlen = max_points)
        (self.line, ) = self.axes.plot(self.time_pts, self.data_pts, 'b-')
        self.init_time = time.time()

        # TODO: revisar si esto es necesario
        self.drawing_timer = self.new_timer(1000 // fps)
        self.drawing_timer.add_callback(self.redraw)
        self.drawing_timer.start()

    def redraw(self):
        """
        Actualiza el gráfico
        """
        self.line.set_data(self.time_pts, self.data_pts)
        self.axes.relim()
        self.axes.autoscale_view()
        self.draw_idle()

    @pyqtSlot(float)
    def add_point(self, point: float):
        """
        Añade un punto por dibujar al gráfico

        Parámetros:
            point (float): el punto a graficar
        """
        self.time_pts.append(time.time() - self.init_time)
        self.data_pts.append(point)

# posibles mensajes:
    # "EJE,[ID],[pt]\r\n" ID = X, Y, X; pt = float de 2 decimales
    # "AMB,[Temp],[Humid]\r\n" Temp = float de 1 decima; Humid = entero en decimal
    # marker = [msg]
def read_uart():
    """
    Lee un mensaje enviado desde la ESP32.

    Por ahora es simplemente una simulación.

    Return:
        str: un mensaje en el formato del protocolo UART especificado abajo

    Formato del mensaje:
    [Marker][Len][Tipo],[Dato1],[Dato2]

    Marker (str): "[msg]", indica el inicio de un mensaje
    Len (short): indica el largo del mensaje
    Tipo (str): "EJE", para el accelerómentro
        Dato1 (str): "X", "Y" o "Z", indica el eje al que pertenece el dato
        Dato2 (float): punto a gráficar, representa una medición
    Tipo (str): "AMB", para las variables ambientales
        Dato1 (float): punto a gráficar, representa una medición de temperatura
        Dato2 (float): punto a gráficar, representa una medición de humedad
    """

    marker = "[msg]"
    tipos = ["EJE", "AMB"]
    ejes = "XYZ"
    tipo = random.choice(tipos)
    if tipo == "EJE":
        msg = f"{tipo},{random.choice(ejes)},{round(random.random(), 2)}"
    else:
        msg = f"{tipo},{round(random.random()*15 + 15, 1)},{random.randint(20, 40)}"
    return f"{marker}{len(msg) + len("\r\n")}{msg}\r\n".encode()

def uart_decoder(msg: bytes):
    """
    decodifica un mensaje enviado desde la ESP

    Return:
        (str, str, str): 
            (tipo: "EJE" o "AMB", 
            dato1: eje "X", "Y" o "Z" o medición de temperatura, 
            dato2: medición de posición o medición de humedad)
    """
    marker = b"[msg]"
    beg = msg.find(marker)
    msg = msg[beg + len(marker):]
    msg = msg[2:]
    msg = msg.decode()
    x, y, z = msg.split(",")
    # TODO: considerar tamaño del mensaje o indicador de fin del mensaje
    return (x, y, z)
    
def send_uart(tipo: str, val: str, eje: str = "-"):
    """
    Envía un mensaje en el protocolo UART especificado abajo

    posibles configuraciones:
    - conectar/desconectar ???
    - inicializar esp32 ?? (se refiere a compilar?? D:)

    [Marker][Len][Tipo],[Eje],[Valor]

    Marker: "[gui]"

    Len: largo del mensaje

    Tipo: el atributo a ajustar
        PRT: cambiar puerto (?)
            Valor: nombre del puerto
        BRT: cambiar baud rate
            Valor: entero que representa el nuevo valor para el Baud Rate
        FRC: cambiar la frecuencia de muestreo
            Eje: "X", "Y", "Z"
                Valor: 50, 100, 200, 500 o 1000 (Hz)
            Eje: "A"
                Valor: 30 o 60 (s)
        AMP: cambiar la amplitud máxima
            Eje: "X", "Y", "Z"
                Valor: 4, 8 o 16 (g)
        FUN: cambiar la función a graficar
            Eje: "X", "Y", "Z"
                Valor: 
                    "SMP": Armónica Simple
                    "MOD": Modulada en Amplitud
                    "MUL": Multicomponente o Compleja

    Si eje no está especificado, su valor es "-" y es descartable
    """
    marker = "[gui]"
    tipos = ["PRT", "BRT", "FRC", "AMP", "FUN"]
    ejes = ["X", "Y", "Z", "A", "-"]
    if tipo not in tipos:
        print(f"seleccionar uno de los siguientes tipos: {tipos}")
        return
    if eje not in ejes:
        print(f"seleccionar alguno de los siguientes ejes: {ejes}")
    val = val.split(" ")[0]
    msg = f"{tipo},{eje},{val}"
    return (marker + str(len(msg)) + msg)
    

class DataReceiver(QObject):
    """
    clase que se encarga de recibir las señales de la GUI y 
    envía los mensajes adecuados a la ESP32 y viseversa

    Atributos:
        data_received_x: recibe los datos para el eje x del acelerómetro
        data_received_y: recibe los datos para el eje y del acelerómetro
        data_received_z: recibe los datos para el eje z del acelerómetro
        data_received_t: recibe los datos para el gráfico de temperatura de las variables ambientales
        data_received_h: recibe los datos para el gráfico de humedad de las variables ambientales
        command_queue: cola que almacena las funciones a ejecutar

    """
    data_received_x = pyqtSignal(float)
    data_received_y = pyqtSignal(float)
    data_received_z = pyqtSignal(float)
    data_received_t = pyqtSignal(float)
    data_received_h = pyqtSignal(float)

    def __init__(self):
        """
        inicializa un objeto DataReceiver
        """
        super().__init__()
        self.interval = 100 # TODO: borrar cuando ya no se trate de una simulación
        self.intervals = [30, 100, 100, 100]
        self.command_queue = queue.Queue()
        self.port_name = ""
        self.baud_rate = 115200
        self.connected = False
        self.esp_init = False
        self.marker = "[msg]"
        self.header_len = len(self.marker) + 2
        self.ser = None

    def receiver_loop(self):
        """
        ejecuta el ciclo de recepción y envío de mensajes entre la GUI y el ESP32
        """
        while True:
            while not self.command_queue.empty():
                command = self.command_queue.get_nowait()
                command()

            # implementacion real
            """
            if connected == False:
                continue

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
                msg = struct.unpack(f"<{char_num}b", data)
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
            """

            #simulación
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

    @pyqtSlot()
    def set_port_name(self, chosen_port):
        """
        encola un comando que cambia el nombre del puerto según la selección de la GUI
        si la selección corresponde a "Seleccione un puerto" el nombre del puerto es un 
        string vacío

        Parámetros:
            chosen_port (str): el nombre del puerto elegido
        """
        def none_command():
            self.port_name = ""
        print(f"port_name = {chosen_port}")
        if chosen_port == "Seleccione un puerto":
            print("no hay puertos seleccionados")
            self.command_queue.put(none_command)
            return
        else:
            print(f"puerto {chosen_port} seleccionado exitosamente")
            def command():
                self.port_name = chosen_port
            self.command_queue.put(command)

    @pyqtSlot()
    def connect(self, gui: Ui_MainWindow):
        """
        Encola un comando que se conecta al puerto con el baud rate especificados por la GUI.
        Si la conexión está activa, se impide cambiar el puerto y el baud rate

        Parámetros:
            gui (Ui_MainWindow): la instancia de la interfaz gráfica en la cual se modificarán
            y (des)habilitarán los componentes relacionados a la configuración del puerto
        """
        # TODO: agregar mensaje de error por incapacidad de conectarse
        # TODO: incapacitar inicializar ESP32?? (si se hace, agregar al docstring)
        if self.connected == True:
            def command():
                try:
                    print("desconectando")
                    self.ser.close()
                    self.connected = False
                    gui.pushButton_conect.setText("Conectar")
                    gui.comboBox_puerto.setEnabled(True)
                    gui.spinBox_baud_rate.setEnabled(True)
                    print("desconectado")
                except:
                    print("problemas al cerrar la conexión")
            self.command_queue.put(command)
        elif self.port_name == "":
            print("debe seleccionar un puerto")
            self.connected = False
            gui.pushButton_conect.setText("Conectar")
            gui.comboBox_puerto.setEnabled(True)
            gui.spinBox_baud_rate.setEnabled(True)
        else:
            def command():
                try:
                    print("conectando")
                    self.ser = serial.Serial(port=self.port_name, baudrate=self.baud_rate)
                    self.connected = True
                    gui.pushButton_conect.setText("Desconectar")
                    gui.comboBox_puerto.setDisabled(True)
                    gui.spinBox_baud_rate.setDisabled(True)
                    print("conectado")
                except Exception as e:
                    self.connected = False
                    gui.pushButton_conect.setText("Conectar")
                    gui.comboBox_puerto.setEnabled(True)
                    gui.spinBox_baud_rate.setEnabled(True)
                    print(f"problemas al conectar: {e}")
            self.command_queue.put(command)

    def init_esp(self):
        """
        Inicializa el ESP32
        """
        # TODO: todavía no entiendo que significa esto
        def command():
            self.esp_init = True
            print("inicializando esp")
        self.command_queue.put(command)

    @pyqtSlot()
    def set_baud_rate(self, rate: int):
        if (rate != None):
            print(f"baud_rate nuevo: {rate}")
            def command():
                self.baud_rate = rate
            self.command_queue.put(command)

    @pyqtSlot()
    def set_function(self, f_name, eje, gui: Ui_MainWindow):
        pi = "π"
        simple = f"{eje}(t) = A sin(2{pi}ft)"
        modulada = f"{eje}(t) = A cos(2{pi}f₁t) sin(2{pi}f₂t)"
        multicomponente = f"{eje}(t) = A [sin(2{pi}ft) + cos(4{pi}ft)]"
        labels = {"X": gui.label_funcion_x, 
                  "Y": gui.label_funcion_y, 
                  "Z": gui.label_funcion_z}
        if f_name == "Armónica Simple":
            labels[eje].setText(simple)
            print(f"cambiando función en eje {eje} a armónica simple")
        elif f_name == "Modulada en Amplitud":
            labels[eje].setText(modulada)
            print(f"cambiando función en eje {eje} a modulada en amplitud")
        elif f_name == "Multicomponente":
            labels[eje].setText(multicomponente)
            print(f"cambiando función en eje {eje} a multicomponente")
        else:
            print("función inválida")
        def command():
            # TODO
            pass
        self.command_queue.put(command)

    @pyqtSlot()
    def set_amplitude(self, amp, eje):
        if amp == "4 g":
            print(f"cambiando amplitud en eje {eje} a 4g")
        elif amp == "8 g":
            print(f"cambiando amplitud en eje {eje} a 8g")
        elif amp == "16 g":
            print(f"cambiando amplitud en eje {eje} a 16g")
        else:
            print("amplitud inválida")
        def command():
            # TODO
            pass
        self.command_queue.put(command)

    @pyqtSlot()
    def set_frec_muestreo(self, frec, graf):
        if graf == "AMB":
            def command():
                pass
                # TODO: implementar con send_uart
            print(f"cambiando frecuencia para variables ambientales a {frec}")
        elif frec == "50 Hz":
            print(f"cambiando frecuencia en eje {graf} a 50 Hz")
        elif frec == "100 Hz":
            print(f"cambiando frecuencia en eje {graf} a 100 Hz")
        elif frec == "200 Hz":
            print(f"cambiando frecuencia en eje {graf} a 200 Hz")
        elif frec == "500 Hz":
            print(f"cambiando frecuencia en eje {graf} a 500 Hz")
        elif frec == "1000 Hz":
            print(f"cambiando frecuencia en eje {graf} a 1000 Hz")
        else:
            print("frecuencia inválida")
        def command():
            # TODO
            pass
        self.command_queue.put(command)
        
def setDefaults(gui: Ui_MainWindow):
    frec_boxes = [gui.comboBox_frec_x, gui.comboBox_frec_y, gui.comboBox_frec_z]
    for b in frec_boxes:
        b.setCurrentIndex(b.findText("100 Hz"))
    gui.radioButton_30s.setChecked(True)
    gui.spinBox_baud_rate.setMaximum(999999)
    gui.spinBox_baud_rate.setValue(115200)
    pi = "π"
    gui.label_funcion_x.setText(f"X(t) = A sin(2{pi}ft)")
    gui.label_funcion_y.setText(f"Y(t) = A sin(2{pi}ft)")
    gui.label_funcion_z.setText(f"Z(t) = A sin(2{pi}ft)")

    """
    gui.spinBox_f1_x.setMaximum(99999)
    gui.spinBox_f1_y.setMaximum(99999)
    gui.spinBox_f1_z.setMaximum(99999)
    gui.spinBox_f2_x.setMaximum(99999)
    gui.spinBox_f2_y.setMaximum(99999)
    gui.spinBox_f2_z.setMaximum(99999)

    gui.label_f2_x.hide()
    gui.spinBox_f2_x.hide()
    gui.label_f2_y.hide()
    gui.spinBox_f2_y.hide()
    gui.label_f2_z.hide()
    gui.spinBox_f2_z.hide()
    """

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
    receiver.data_received_t.connect(lambda p: gui.label_medi_temp.setText(f"Última medición: {p}"))
    receiver.data_received_h.connect(plot_h.add_point)
    receiver.data_received_h.connect(lambda p: gui.label_medi_humid.setText(f"Última medición: {round(p)}"))

    # configuración
    gui.comboBox_puerto.currentTextChanged.connect(lambda texto: receiver.set_port_name(texto))
    gui.spinBox_baud_rate.valueChanged.connect(lambda rate: receiver.set_baud_rate(rate))
    gui.pushButton_conect.pressed.connect(partial(receiver.connect, gui))
    gui.pushButton_init_esp.pressed.connect(receiver.init_esp)

    # variables ambientales
    gui.radioButton_30s.pressed.connect(partial(receiver.set_frec_muestreo, 30, "AMB"))
    gui.radioButton_60s.pressed.connect(partial(receiver.set_frec_muestreo, 60, "AMB"))

    # acelerómetro
    gui.comboBox_fun_x.currentTextChanged.connect(lambda texto: receiver.set_function(texto, "X", gui))
    gui.comboBox_amp_x.currentTextChanged.connect(lambda texto: receiver.set_amplitude(texto, "X"))
    gui.comboBox_frec_x.currentTextChanged.connect(lambda texto: receiver.set_frec_muestreo(texto, "X"))
    
    gui.comboBox_fun_y.currentTextChanged.connect(lambda texto: receiver.set_function(texto, "Y", gui))
    gui.comboBox_amp_y.currentTextChanged.connect(lambda texto: receiver.set_amplitude(texto, "Y"))
    gui.comboBox_frec_y.currentTextChanged.connect(lambda texto: receiver.set_frec_muestreo(texto, "Y"))
    
    gui.comboBox_fun_z.currentTextChanged.connect(lambda texto: receiver.set_function(texto, "Z", gui))
    gui.comboBox_amp_z.currentTextChanged.connect(lambda texto: receiver.set_amplitude(texto, "Z"))
    gui.comboBox_frec_z.currentTextChanged.connect(lambda texto: receiver.set_frec_muestreo(texto, "Z"))

    thread.start()
    window.show()
    app.exec()