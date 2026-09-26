#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <driver/uart.h>

#define UART_PORT_NUM 0
#define BUF_SIZE (1024)
#define PI 3.14159265358979323846

typedef struct __attribute__((packed)) {
    uint8_t header[2]; // Bytes mágicos de sincronización: 0xAA 0xBB
    char tipo;         // 'X', 'Y', 'Z' (Ejes) o 'T', 'H' (Ambiente)
    float valor;       // El dato numérico de 4 bytes
    uint8_t checksum;  // XOR del tipo y el valor
} PaqueteBinario;

typedef struct __attribute__((packed)) {
    uint8_t header[2]; // 0xCC, 0xDD
    char tipo[3];      // "FRC", "AMP", "FUN"
    char eje;          // 'X', 'Y', 'Z', 'A'
    int32_t valor;     // 4 bytes con el valor numérico
    uint8_t checksum;  // XOR
} PaqueteComando;

typedef struct {
    int intervalo_segundos; // 30 o 60
} SensorAmbiental;

typedef struct {
    char id;
    int funcion_actual; //1,2 o 3
    int amplitud; // 4, 8 o 16
    int freq_muestreo; // 50, 100, 200, 500 o 1000
    int f1;
    int f2;
    uint64_t muestra; // Contador absoluto de muestras
}   EjeAcelerometro;

SensorAmbiental sensor_clima = {30}; // CAMBIAR A 30
EjeAcelerometro ejeX = {'X', 1, 4, 10, 5.0, 3.0, 0};
EjeAcelerometro ejeY = {'Y', 1, 4, 500, 5.0, 3.0, 0};
EjeAcelerometro ejeZ = {'Z', 1, 4, 1000, 5.0, 3.0, 0};

void init_uart() {
    uart_config_t uart_config = {
        .baud_rate = 115200,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    uart_driver_install(UART_PORT_NUM, BUF_SIZE * 2, BUF_SIZE * 2, 0, NULL, 0);
    uart_param_config(UART_PORT_NUM, &uart_config);
    uart_set_pin(UART_PORT_NUM, 1, 3, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
}

float calcular_aceleracion(EjeAcelerometro *eje) {
    float A = (float)eje->amplitud;
    float t = (float)eje->muestra / eje->freq_muestreo;
    
    if (eje->funcion_actual == 1) {
        return A * sin(2 * PI * eje->f1 * t);
    } else if (eje->funcion_actual == 2) {
        return A * cos(2 * PI * eje->f1 * t) * sin(2 * PI * eje->f2 * t);
    } else {
        return A * (sin(2 * PI * eje->f1 * t) + cos(4 * PI * eje->f1 * t));
    }
}

uint8_t calcular_checksum(const char* cadena) {
    uint8_t chk = 0;
    while (*cadena) {
        chk ^= (uint8_t)(*cadena++);
    }
    return chk;
}

void tarea_simular_eje(void *arg) {
    EjeAcelerometro *eje = (EjeAcelerometro *)arg;
    TickType_t xLastWakeTime = xTaskGetTickCount();
    char tx_buffer[64];

    while(1) {
        float valor_accel = calcular_aceleracion(eje);
        eje->muestra++;

        // 1. Armar el paquete
        PaqueteBinario pkt;
        pkt.header[0] = 0xAA;
        pkt.header[1] = 0xBB;
        pkt.tipo = eje->id; // 'X', 'Y' o 'Z'
        pkt.valor = valor_accel;
        
        // 2. Calculamos el checksum del payload
        uint8_t *datos_ptr = (uint8_t*)&pkt.tipo;
        uint8_t chk = 0;
        for (int i = 0; i < sizeof(char) + sizeof(float); i++) {
            chk ^= datos_ptr[i];
        }
        pkt.checksum = chk;

        // 3. Empaquetamos todo. %02X formatea el checksum en hexadecimal.
        // Al agregar *XX\r\n, sumamos 5 caracteres al largo del payload original.
        uart_write_bytes(UART_PORT_NUM, (const char*)&pkt, sizeof(PaqueteBinario));

        // 4. Tu delay normal
        TickType_t ticks_delay = pdMS_TO_TICKS(1000 / eje->freq_muestreo);
        vTaskDelay(ticks_delay == 0 ? 1 : ticks_delay);
    }
}

void tarea_simular_ambiental(void *arg) {
    SensorAmbiental *sensor = (SensorAmbiental *)arg;
    char tx_buffer[64];

    while (1) {
        float temperatura = 15.0 + (rand() % 151) /10.0;
        int humedad = 20 + (rand() % 21);

        // --- 1. ENVIAR PAQUETE DE TEMPERATURA ---
        PaqueteBinario pkt_temp;
        pkt_temp.header[0] = 0xAA;
        pkt_temp.header[1] = 0xBB;
        pkt_temp.tipo = 'T'; // 'T' para Temperatura
        pkt_temp.valor = temperatura;

        // Calcular checksum
        uint8_t *ptr_t = (uint8_t*)&pkt_temp.tipo;
        uint8_t chk_t = 0;
        for (int i = 0; i < sizeof(char) + sizeof(float); i++) {
            chk_t ^= ptr_t[i];
        }
        pkt_temp.checksum = chk_t;

        // Escribir en el UART
        uart_write_bytes(UART_PORT_NUM, (const char*)&pkt_temp, sizeof(PaqueteBinario));

        // Pequeña pausa de 50ms para separar el envío de T y H
        vTaskDelay(pdMS_TO_TICKS(50));

        // --- 2. ENVIAR PAQUETE DE HUMEDAD ---
        PaqueteBinario pkt_hum;
        pkt_hum.header[0] = 0xAA;
        pkt_hum.header[1] = 0xBB;
        pkt_hum.tipo = 'H'; // 'H' para Humedad
        pkt_hum.valor = humedad;

        // Calcular checksum
        uint8_t *ptr_h = (uint8_t*)&pkt_hum.tipo;
        uint8_t chk_h = 0;
        for (int i = 0; i < sizeof(char) + sizeof(float); i++) {
            chk_h ^= ptr_h[i];
        }
        pkt_hum.checksum = chk_h;

        // Escribir en el UART
        uart_write_bytes(UART_PORT_NUM, (const char*)&pkt_hum, sizeof(PaqueteBinario));

        // Esperar el intervalo configurado (30 o 60 segundos) antes de la siguiente lectura
        vTaskDelay(pdMS_TO_TICKS(sensor->intervalo_segundos * 1000));
    }
}

void tarea_recibir_comandos(void *arg){

    uint8_t buffer_rx[16];

    while(1) {
        int len = uart_read_bytes(UART_PORT_NUM, buffer_rx, sizeof(PaqueteComando), pdMS_TO_TICKS(100));

        if (len >= sizeof(PaqueteComando)) {
            // Verificar cabecera binaria 0xCC 0xDD
            if (buffer_rx[0] == 0xCC && buffer_rx[1] == 0xDD) {
                PaqueteComando *cmd = (PaqueteComando*)buffer_rx;

                // Calcular checksum de los campos internos (Tipo + Eje + Valor)

                uint8_t *ptr = (uint8_t*)&cmd->tipo;
                uint8_t chk_calc = 0;
                int tam_payload = sizeof(cmd->tipo) + sizeof(cmd->eje) + sizeof(cmd->valor);
                
                for (int i = 0; i < tam_payload; i++) {
                    chk_calc ^= ptr[i];
                }

                if (chk_calc == cmd->checksum) {
                    // Aplicar configuraciones al ESP32
                    if (cmd->eje == 'A' && memcmp(cmd->tipo, "FRC", 3) == 0) {
                        sensor_clima.intervalo_segundos = cmd->valor;
                    } else {
                        EjeAcelerometro *eje_objetivo = NULL;
                        if (cmd->eje == 'X' || cmd->eje == 'x') eje_objetivo = &ejeX;
                        else if (cmd->eje == 'Y' || cmd->eje == 'y') eje_objetivo = &ejeY;
                        else if (cmd->eje == 'Z' || cmd->eje == 'z') eje_objetivo = &ejeZ;

                        if (eje_objetivo != NULL) {
                            if (memcmp(cmd->tipo, "AMP", 3) == 0) {
                                eje_objetivo->amplitud = cmd->valor;
                            } else if (memcmp(cmd->tipo, "FRC", 3) == 0) {
                                eje_objetivo->freq_muestreo = cmd->valor;
                            } else if (memcmp(cmd->tipo, "FUN", 3) == 0) {
                                eje_objetivo->funcion_actual = cmd->valor;
                            }
                        }
                    }
                } else {
                    uart_write_bytes(UART_PORT_NUM, (const char*)&buffer_rx, sizeof(PaqueteComando));
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

void app_main(void) {
    init_uart();

    //printf("Iniciando simulador de Acelerometro... \n");
    xTaskCreate(tarea_simular_eje, "Task_EjeX", 4096, (void*)&ejeX, 2, NULL);
    xTaskCreate(tarea_simular_eje, "Task_EjeY", 4096, (void*)&ejeY, 2, NULL);
    xTaskCreate(tarea_simular_eje, "Task_EjeZ", 4096, (void*)&ejeZ, 2, NULL);

    //printf("Iniciando simulador Ambiental... \n");
    xTaskCreate(tarea_simular_ambiental, "Task_Ambiental", 4096, (void*)&sensor_clima, 1, NULL);
    
    //printf("Iniciado recibir comandos... \n");
    xTaskCreate(tarea_recibir_comandos, "Task_RX", 4096, NULL, 3, NULL);
}