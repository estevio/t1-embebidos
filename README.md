# t1-embebidos

El objetivo de este proyecto es diseñar una interfáz gráfica para adquisición y control de datos en tiempo real para tarjetas ESP32 conectada via comunicación UART (USB-Serial) a un computador que ejecutrá una aplicación en Python con PyQt.

## Descripción

Este proyecto se divide en 2 componentes principales, la aplicación receptora/controladora en Python y la simulación de sensores en el ESP32.

### Estructura del proyecto

```
t1-embebidos/
├── esp32_firmware/             # simulación de sensores
│   ├── main/
│   │   ├── CMakeLists.txt
│   │   └── main.c              # lógica de la simulación
│   ├── CMakeLists.txt
│   └── sdkconfig
├── gui_python/                 # aplicación controladora
│   ├── app.py                  # clase de la UI
│   └── main.py                 # lógica de la aplicación
└── README.md                   # estas aquí :D
```

### Protocolo UART

El protocolo UART que se utiliza funciona empaquetando estructuras en bytes. Las estructuras varían dependiendo del componente que envía el mensaje, pero en general siguen el siguiente formato:

```
{marker}{mensaje}{checksum}
```

El marker puede tomar 2 valores, en hexagesimal `0xAA 0xBB`para mensajes que se envían desde la ESP y `0xCC 0xDD` para mensajes que se envían desde la interfaz gráfica.

Checksum se caclula iterando por los caracteres del mensaje y aplicar la operación binaria `XOR` sobre la representación binaria de los caracteres (partiendo con 0).

Desde el lado de la ESP, los mensajes se envían empaquetando estructuras que contienen el marker, el tipo ("X", "Y", "Z", "T" o "H") y el valor a graficar.

Por el otro lado, los mensajes de la GUI se realizan codificando según ascii el tipo de mensaje, que puede tomar alguno de los siguientes valores: "FRC" (modificar la frecuencia de muestreo), "AMP" (modificar la amplitud máxima) y "FUN" (la función a simular), el eje al que afecta, "X", "Y", "Z" o "A" (para las variables ambientales) y el valor con el cual configurar.

### ESP32

Este código para ESP32 simula sensores y se comunica en tiempo real mediante un puerto serie (UART), dividiendo el trabajo en cuatro funciones principales:

Acelerómetro: Simula movimientos en los ejes X, Y y Z calculando matemáticamente diferentes tipos de ondas.

Sensor Ambiental: Inventa y envía datos de temperatura y humedad cada cierto tiempo.

Envío de datos: Empaqueta la información generada con códigos de seguridad para asegurar que la computadora los reciba sin errores.

Control en vivo: Escucha comandos externos para ajustar al instante cómo se comportan las simulaciones (por ejemplo, cambiando la velocidad de lectura o el tamaño de las ondas).

### GUI

Para la realización de la interfaz gráfica, se separó el dibujo de los gráficos del manejo de datos y señales. El manejo de datos y señales se realiza por la misma estructura, `DataReceiver`, que entra en un loop en el cual ejecuta una serie de comandos (almacenados en una cola fifo) que dependerán de la acción solicitada, por ejemplo, cambiar la frecuencia máxima. En este caso, la acción a realizar, además de actualizar las variables locales, será enviar el mensaje por medio del protocolo.

La segunda parte del loop maneja la recepción de datos, leyendo desde el puerto serial, decodificando el mensaje, calculando el checksum y, si este es consistente, se lanza una señal de recepción de datos para gráficar en el gráfico adecuado.

Para poder configurar el baud rate desde la GUI, se decidió modificar el archivo `sdkconfig.defaults`.

## Instalación

Este proyecto requiere los siguientes requisitos:

[//]: <> (versión de C + Espressif)

- Espressif v5.5.5
- Python 3.14
- PyQt6
- pyserial, matplotlib

<br/>

Para instalar las dependencias de python, ejecutar el siguiente comando dentro del directorio t1-embebidos:

```
pip install -r requirements.txt
```

## Ejecución

Para ejecutar este proyecto, ejecutar el siguiente comando dentro del directorio t1-embebidos:

```
python gui_python/main.py
```
