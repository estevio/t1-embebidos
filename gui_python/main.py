import sys
import time
import queue
import serial
import struct
import threading
import collections
import os
import subprocess
import platform

import random

from functools import partial

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

from PyQt6.QtSerialPort import QSerialPortInfo


from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtWidgets import QApplication, QMainWindow

from app import Ui_MainWindow

# modificar segun instalación
# Windows: "C:/Espressif/frameworks/esp-idf-vX.X/"
# Linux/Mac: "~/esp/esp-idf/"
# magda: C:/Espressif/frameworks/esp-idf-v5.5.5/
IDF_PATH = os.path.expanduser("C:/Espressif/frameworks/esp-idf-v5.5.5/") 

class LivePlot(FigureCanvasQTAgg):
    """
    Una clase que representa un gráfico de la GUI

    Atributos:
        time_pts: colección de puntos que representa el tiempo
        data_pts: colección de puntos que representa el valor de las mediciones
        init_time: tiempo de inicialización del gráfico
        drawing_timer: timer para graficar el siguiente punto
    """

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

    @pyqtSlot(int)
    def add_point_int(self, point: int):
        """
        Añade un punto por dibujar al gráfico

        Parámetros:
            point (int): el punto a graficar
        """
        self.time_pts.append(time.time() - self.init_time)
        self.data_pts.append(point)

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
    return f"{marker}{str(len(msg))}{msg}".encode()

def uart_decoder(msg):
    """
    decodifica un mensaje enviado desde la ESP

    Return:
        (str, str, str): 
            (tipo: "EJE" o "AMB", 
            dato1: eje "X", "Y" o "Z" o medición de temperatura, 
            dato2: medición de posición o medición de humedad)
    """
    print(msg + "\n")
    marker = b"[msg]"
    beg = msg.find(marker)
    msg = msg[beg + len(marker):]
    msg = msg[2:]
    msg = msg.decode(errors="ignore")
    print(msg + "\n")
    msg, chk = msg.split("*")
    msg_len, x, y, z = msg.split(",")
    # TODO: considerar tamaño del mensaje o indicador de fin del mensaje
    msg = f"{x},{y},{z}".encode()
    if (calcular_checksum(msg) == chk):
        return (x, y, z)
    # TODO: manejo de error
    

def calcular_checksum(mensaje: bytes):
    chk = 0
    for caracter in mensaje:
        chk ^= ord(caracter)
    return chk
    
    
def send_uart(ser: serial.Serial, tipo: str, val: str, eje: str = "-"):
    """
    Envía un mensaje en el protocolo UART especificado abajo

    Parámetros:
        tipo: "FRC", "AMP", "FUN"
        val: números o "SMP", "MOD" o "MUL"
        eje: "X", "Y", "Z", "A" (opcional)

    Formato del mensaje:
        [Marker][Len][Tipo],[Eje],[Valor]
    
    Marker: "[gui]"

    Len: largo del mensaje


    Tipo: el atributo a ajustar
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
    if not ser:
        print("conexion inexistente")
        return
    print(f"tipo:{tipo}:val:{val}:eje{eje}:\n")
    header = b'\xcc\xdd'
    tipos = ["PRT", "BRT", "FRC", "AMP", "FUN"]
    ejes = ["X", "Y", "Z", "A", "-"]
    if tipo not in tipos:
        print(f"seleccionar uno de los siguientes tipos: {tipos}")
        return
    if eje not in ejes:
        print(f"seleccionar alguno de los siguientes ejes: {ejes}")
    if tipo == "FUN":
        mapping = {"SMP": 1, "MOD": 2, "MUL": 3}
        val_numerico = mapping.get(val, 1)
    else:
        val_numerico = int(str(val).split(" ")[0])
    tipo_bytes = tipo.encode('ascii')[:3]
    eje_byte = eje.encode('ascii')[0]
    val_bytes = struct.pack('<i', val_numerico)
    payload = tipo_bytes + bytes([eje_byte]) + val_bytes
    chk = 0
    for b in payload:
        chk ^= b
    paquete_binario = header + payload + bytes([chk])
    ser.write(paquete_binario)
    

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
    data_received_h = pyqtSignal(int)

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
        print("loop starts now")
        PAQUETE_SIZE = 8
        #buf = bytearray()
        while True:
            time.sleep(1/1000)
            while not self.command_queue.empty():
                command = self.command_queue.get_nowait()
                command()

            # implementacion real
            
            if self.connected == False:
                continue

            try:
                # Esperamos a tener al menos un paquete completo en el buffer
                if self.ser.in_waiting >= PAQUETE_SIZE:
                    
                    # 1. Buscamos los bytes mágicos de sincronización
                    cabecera = self.ser.read(2)
                    
                    if cabecera == b'\xaa\xbb':
                        # 2. Si es nuestro paquete, leemos los 6 bytes restantes
                        payload_y_chk = self.ser.read(PAQUETE_SIZE - 2)
                        
                        if len(payload_y_chk) == 6:
                            # Desempaquetamos: 'c' (char de 1 byte), 'f' (float 4 bytes), 'B' (uint8 1 byte)
                            # El '<' indica Little Endian (el estándar del ESP32)
                            tipo_bytes, valor, chk_rx = struct.unpack('<cfB', payload_y_chk)
                            tipo = tipo_bytes.decode('ascii')
                            
                            # 3. Validar el checksum recalculándolo en Python
                            payload = payload_y_chk[:5] # Extraemos solo el tipo y el valor
                            chk_calculado = 0
                            for byte in payload:
                                chk_calculado ^= byte
                                
                            if chk_calculado == chk_rx:
                                # 4. Emitir las señales directamente
                                if tipo == 'X':
                                    self.data_received_x.emit(valor)
                                elif tipo == 'Y':
                                    self.data_received_y.emit(valor)
                                elif tipo == 'Z':
                                    self.data_received_z.emit(valor)
                                elif tipo == 'T':
                                    self.data_received_t.emit(valor)
                                elif tipo == 'H':
                                    self.data_received_h.emit(int(valor))
                    else:
                        # Si perdemos la sincronía (leímos a la mitad de un paquete),
                        # retrocedemos un byte para realinearnos en la próxima lectura
                        self.ser.read(1)
                        
            except Exception as e:
                # Ignoramos caídas de conexión abruptas y seguimos
                pass
            

            #simulación
            """
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
                self.data_received_h.emit(int(y))
            time.sleep(self.interval / 1000)
            """

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
        # TODO: incapacitar inicializar ESP32 (si se hace, agregar al docstring)
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
            gui.label_error_conexion.setText("Error de conexión: Seleccione un puerto.")
            gui.label_error_conexion.show()
        else:
            def command():
                try:
                    print("conectando")
                    self.ser = serial.Serial(port=self.port_name, baudrate=self.baud_rate)
                    self.connected = True
                    gui.pushButton_conect.setText("Desconectar")
                    gui.comboBox_puerto.setDisabled(True)
                    gui.spinBox_baud_rate.setDisabled(True)
                    gui.label_error_conexion.hide()
                    print("conectado")
                except Exception as e:
                    self.connected = False
                    gui.pushButton_conect.setText("Conectar")
                    gui.comboBox_puerto.setEnabled(True)
                    gui.spinBox_baud_rate.setEnabled(True)
                    print(f"problemas al conectar: {e}")
                    gui.label_error_conexion.setText("Error de conexión: Cambie el puerto.")
                    gui.label_error_conexion.show()
                    
            self.command_queue.put(command)

    def init_esp(self, dir_proyecto):
        """
        Lanza un thread para inicializar el ESP32
        """
        if self.port_name == "":
            gui.label_error_conexion.setText("Error de conexión: Seleccione un puerto.")
            gui.label_error_conexion.show()
        else:
            threading.Thread(target=self.proceso_init_esp, args=dir_proyecto, daemon=True).start()

    def proceso_init_esp(self, dir_proyecto):

        print("Compilando")
        comp_exitosa = self.comando_idf("build", dir_proyecto)

        if not comp_exitosa:
            print("Error de compilación")
            # TODO: imprimir mensaje en gui
            return

        print("Flasheando")
        flash_exitoso = self.comando_idf(f"-p {self.port_name} -b {self.baud_rate} flash", dir_proyecto)

        if not flash_exitoso:
            print("Error de flasheo")
            # TODO: imprimir mensaje en gui
            return

        print("Inicialización completada!")
        

    def comando_idf(self, comando, dir_proyecto):
        """
        Ejecuta comandos idf.py cargando el entorno del SDK.
        """

        es_windows = platform.system() == "Windows"

        # Reemplaza la ruta por tu archivo 'export.bat' de Espressif ??
        if es_windows:
            export_script = r"C:\Espressif\frameworks\esp-idf-v5.5.5\export.bat"
            comando_completo = f'"{export_script}" && idf.py {comando}'
        # En Linux/Mac necesitamos hacer un source del script export.sh
        else:
            export_script = os.path.join(IDF_PATH, "export.sh")
            comando_completo = f'call "{export_script}" && idf.py {comando}'

        entorno_limpio = os.environ.copy()
    
        # 2. Eliminamos las variables de Python que interfieren con el ESP-IDF
        entorno_limpio.pop("VIRTUAL_ENV", None)
        entorno_limpio.pop("PYTHONHOME", None)
        entorno_limpio.pop("PYTHONPATH", None)
        print(f"Ejecutando: idf.py {comando}")
        if es_windows:
            entorno_limpio["IDF_TOOLS_PATH"] = r"C:\Espressif"
        process = subprocess.Popen(
            comando_completo,
            shell = True,
            cwd = dir_proyecto,
            env=entorno_limpio,
            stdout = subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        salida_completa = ""
        if process.stdout:
            for linea in process.stdout:
                print(linea, end="") # TODO: mostrar en mensaje de error
                salida_completa += linea

        process.wait()
        return process.returncode == 0

    @pyqtSlot()
    def set_baud_rate(self, rate: int):
        """
        encola un comando que configura el valor del baud rate de la comunicacion con la ESP32

        Parámetros:
            rate (int): el nuevo baud rate
        """
        if (rate != None):
            print(f"baud_rate nuevo: {rate}")
            def command():
                self.baud_rate = rate
            self.command_queue.put(command)

    @pyqtSlot()
    def set_function(self, f_name, eje, gui: Ui_MainWindow):
        """
        cambia la etiqueta para la función de cada eje y
        encola un comando que envía una solicitud de cambio de la función en la ESP32

        Parámetros:
            f_name (str): el nombre de la función en la GUI
            eje (str): el eje a configurar
            gui (Ui_MainWindow): la GUI donde deberá cambiarse la etiqueta
        """
        pi = "π"
        simple = f"{eje}(t) = A sin(2{pi}ft)"
        modulada = f"{eje}(t) = A cos(2{pi}f₁t) sin(2{pi}f₂t)"
        multicomponente = f"{eje}(t) = A [sin(2{pi}ft) + cos(4{pi}ft)]"
        labels = {"X": gui.label_funcion_x, 
                  "Y": gui.label_funcion_y, 
                  "Z": gui.label_funcion_z}
        val = ""
        if f_name == "Armónica Simple":
            labels[eje].setText(simple)
            val = "SMP"
            print(f"cambiando función en eje {eje} a armónica simple")
        elif f_name == "Modulada en Amplitud":
            labels[eje].setText(modulada)
            val = "MOD"
            print(f"cambiando función en eje {eje} a modulada en amplitud")
        elif f_name == "Multicomponente":
            labels[eje].setText(multicomponente)
            val ="MUL"
            print(f"cambiando función en eje {eje} a multicomponente")
        else:
            print("función inválida")
            return
        def command():
            send_uart(self.ser, "FUN", val, eje)
        self.command_queue.put(command)

    @pyqtSlot()
    def set_amplitude(self, amp, eje, plot):
        """
        encola un comando que envía la solicitud de cambiar la amplitud máxima
        de un eje específico

        Parámetros:
            amp (str): la nueva amplitud máxima
            eje (str): el eje al cual cambiar la amplitud
        """
        val = amp.split(" ")[0]
        rng = int(val) + int(val)/4
        plot.axes.set_ylim(-1 * rng, rng)

        def command():
            send_uart(self.ser, "AMP", val, eje)
        self.command_queue.put(command)

    @pyqtSlot()
    def set_frec_muestreo(self, frec, graf):
        """
        encola una solicitud para cambiar la frecuencia de muestreo (acelerómetro)
        o bien el período entre muestras (variables ambientales) en el gráfico que corresponda

        Parámetros:
            frec (str): la nueva frecuencia o intervalo
            graf: el grafico al que se refiere ("AMB", "X", "Y" o "Z")
        """
        val = frec.split(" ")[0]
        ejes = {"X": 1, "Y": 2, "Z": 3}
        if graf == "AMB":
            # TODO: checkear que la funcion se ejecute solo de ser necesario
            def command():
                self.intervals[0] = val
                send_uart(self.ser, "FRC", val, "A")
            print(f"cambiando frecuencia para variables ambientales a {frec}")
        else:
            def command():
                self.intervals[ejes[graf]] = val
                send_uart(self.ser, "FRC", val, graf)
            print(f"cambiando frecuencia para el eje {graf} a {frec}")
        self.command_queue.put(command)
        
def setDefaults(gui: Ui_MainWindow):
    """
    se asegura que las opciones default se reflejen en la GUI
    
    Parámetros:
        gui (Ui_MainWindow): la interfaz que debe ser modificada
    """
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

    gui

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

    gui.label_error_conexion.hide()

    ports = QSerialPortInfo.availablePorts()
    gui.comboBox_puerto.addItem("Seleccione un puerto")
    if ports != None:
        for p in ports:
            gui.comboBox_puerto.addItem(p.portName())

if __name__ == "__main__":
    print("in main")
    app = QApplication(sys.argv)
    window = QMainWindow()
    gui = Ui_MainWindow()
    print("gui setup")
    gui.setupUi(window)
    print("gui setup done")
    setDefaults(gui)
    print("gui defaults done")

    plot_x = LivePlot()
    gui.plot_x.addWidget(plot_x)

    plot_y = LivePlot()
    gui.plot_y.addWidget(plot_y)

    plot_z = LivePlot()
    gui.plot_z.addWidget(plot_z)

    plot_t = LivePlot()
    gui.plot_temp.addWidget(plot_t)

    plot_h = LivePlot()
    gui.plot_humid.addWidget(plot_h)

    for p in [plot_x, plot_y, plot_z]:
        p.axes.set_ylim(-5, 5)

    receiver = DataReceiver()
    print("data reciever instant")
    thread = threading.Thread(target=receiver.receiver_loop, daemon=True)
    print("data receiver thread lauched")
    receiver.data_received_x.connect(plot_x.add_point)
    receiver.data_received_y.connect(plot_y.add_point)
    receiver.data_received_z.connect(plot_z.add_point)
    receiver.data_received_t.connect(plot_t.add_point)
    receiver.data_received_t.connect(lambda p: gui.label_medi_temp.setText(f"Última medición: {p}"))
    receiver.data_received_h.connect(plot_h.add_point_int)
    receiver.data_received_h.connect(lambda p: gui.label_medi_humid.setText(f"Última medición: {p}"))

    # configuración
    gui.comboBox_puerto.currentTextChanged.connect(lambda texto: receiver.set_port_name(texto))
    gui.spinBox_baud_rate.valueChanged.connect(lambda rate: receiver.set_baud_rate(rate))
    gui.pushButton_conect.pressed.connect(partial(receiver.connect, gui))
    gui.pushButton_init_esp.pressed.connect(partial(receiver.init_esp, ("esp32_firmware", )))

    # variables ambientales
    gui.radioButton_30s.pressed.connect(partial(receiver.set_frec_muestreo, "30 s", "AMB"))
    gui.radioButton_60s.pressed.connect(partial(receiver.set_frec_muestreo, "60 s", "AMB"))

    # acelerómetro
    gui.comboBox_fun_x.currentTextChanged.connect(lambda texto: receiver.set_function(texto, "X", gui))
    gui.comboBox_amp_x.currentTextChanged.connect(lambda texto: receiver.set_amplitude(texto, "X", plot_x))
    gui.comboBox_frec_x.currentTextChanged.connect(lambda texto: receiver.set_frec_muestreo(texto, "X"))
    
    gui.comboBox_fun_y.currentTextChanged.connect(lambda texto: receiver.set_function(texto, "Y", gui))
    gui.comboBox_amp_y.currentTextChanged.connect(lambda texto: receiver.set_amplitude(texto, "Y", plot_y))
    gui.comboBox_frec_y.currentTextChanged.connect(lambda texto: receiver.set_frec_muestreo(texto, "Y"))
    
    gui.comboBox_fun_z.currentTextChanged.connect(lambda texto: receiver.set_function(texto, "Z", gui))
    gui.comboBox_amp_z.currentTextChanged.connect(lambda texto: receiver.set_amplitude(texto, "Z", plot_z))
    gui.comboBox_frec_z.currentTextChanged.connect(lambda texto: receiver.set_frec_muestreo(texto, "Z"))

    thread.start()
    window.show()
    app.exec()