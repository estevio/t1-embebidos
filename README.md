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

[//]: <> (TODO!!!)

[//]: <> (quizás añadir explicación corta de la implementación de los componentes)

### ESP32

Este código para ESP32 simula sensores y se comunica en tiempo real mediante un puerto serie (UART), dividiendo el trabajo en cuatro funciones principales:

Acelerómetro: Simula movimientos en los ejes X, Y y Z calculando matemáticamente diferentes tipos de ondas.

Sensor Ambiental: Inventa y envía datos de temperatura y humedad cada cierto tiempo.

Envío de datos: Empaqueta la información generada con códigos de seguridad para asegurar que la computadora los reciba sin errores.

Control en vivo: Escucha comandos externos para ajustar al instante cómo se comportan las simulaciones (por ejemplo, cambiando la velocidad de lectura o el tamaño de las ondas).
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
