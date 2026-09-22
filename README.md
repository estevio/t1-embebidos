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

## Instalación

Este proyecto requiere los siguientes requisitos:

[//]: <> (versión de C + Espressif)

- Python 3.8+
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
