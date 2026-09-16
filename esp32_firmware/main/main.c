#include <stdint.h>
#include <stdio.h>
#include <math.h>

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <driver/uart.h>

#define UART_PORT_NUM 0
#define BUF_SIZE (1024)
#define PI 3.14159265358979323846;

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
EjeAcelerometro ejeX = {'X', 1, 4, 100, 5.0, 0.0, 0};
EjeAcelerometro ejeY = {'Y', 1, 4, 100, 5.0, 0.0, 0};
EjeAcelerometro ejeZ = {'Z', 1, 4, 100, 5.0, 0.0, 0};

void init_uart() {
    uart_config_t uart_config = {
        .baud_rate = 115200,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    uart_driver_install(UART_PORT_NUM, BUF_SIZE * 2, 0, 0, NULL, 0);
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
        return (A / 2.0f) * (sin(2 * PI * eje->f1 * t) + cos(4 * PI * eje->f1 * t));
    }
}

void tarea_simular_eje(void *arg) {
    EjeAcelerometro *eje = (EjeAcelerometro *)arg;
    TickType_t xLastWakeTime = xTaskGetTickCount();
    char tx_buffer[64];

    while(1) {
        float valor_accel = calcular_aceleracion(eje);
        eje->muestra++;

        //printf("EJE_%c:%.2f\n", eje->id, valor_accel);
        int len = snprintf(tx_buffer, sizeof(tx_buffer), "EJE,%c,%.2f\r\n", eje->id, valor_accel);
        uart_write_bytes(UART_PORT_NUM, tx_buffer, len);

        TickType_t ticks_delay = pdMS_TO_TICKS(1000 / eje->freq_muestreo);
        if (ticks_delay == 0) ticks_delay = 1;

        vTaskDelayUntil(&xLastWakeTime, ticks_delay);
    }
}

void tarea_simular_ambiental(void *arg) {
    SensorAmbiental *sensor = (SensorAmbiental *)arg;
    char tx_buffer[64];

    while (1) {
        float temperatura = 15.0 + (rand() % 151) /10.0;
        int humedad = 20 + (rand() % 21);

        //printf("Ambiente: Temperatura: %.1f, Humedad: %d\n", temperatura, humedad);
        int len = snprintf(tx_buffer, sizeof(tx_buffer), "AMB,%.1f,%d\r\n", temperatura, humedad);
        uart_write_bytes(UART_PORT_NUM, tx_buffer, len);

        vTaskDelay(pdMS_TO_TICKS(sensor->intervalo_segundos * 1000));
    }
}

void tarea_recibir_comandos(void *arg){
    uint8_t *data = (uint8_t *) malloc(BUF_SIZE);
    while(1) {
        int len = uart_read_bytes(UART_PORT_NUM, data, BUF_SIZE - 1, pdMS_TO_TICKS(100));
        if (len > 0){
            data[len] = '\0';
            char eje_id, comando;
            int valor;

            if (sscanf((char *)data, "%c,%c,%d", &eje_id, &comando, &valor) == 3) {//algo para que cada cosa quede en un lugar)
                EjeAcelerometro *eje_objetivo = NULL;

                if (eje_id == 'x' || eje_id == 'X') eje_objetivo = &ejeX;
                else if (eje_id == 'y' || eje_id == 'Y') eje_objetivo = &ejeY;
                else if (eje_id == 'z' || eje_id == 'Z') eje_objetivo = &ejeZ;

                if (eje_objetivo != NULL) {
                    if (comando == 'a') {
                        eje_objetivo->amplitud = valor;
                    } else if (comando == 'f'){
                        eje_objetivo->freq_muestreo = valor;
                    } else if (comando == 'm') {
                        eje_objetivo->funcion_actual = valor;
                    }
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
    free(data);
}

void app_main(void) {
    init_uart();

    printf("Iniciando simulador de Acelerometro... \n");
    xTaskCreate(tarea_simular_eje, "Task_EjeX", 2048, (void*)&ejeX, 5, NULL);
    xTaskCreate(tarea_simular_eje, "Task_EjeY", 2048, (void*)&ejeY, 5, NULL);
    xTaskCreate(tarea_simular_eje, "Task_EjeZ", 2048, (void*)&ejeZ, 5, NULL);

    printf("Iniciando simulador Ambiental... \n");
    xTaskCreate(tarea_simular_ambiental, "Task_Ambiental", 2048, (void*)&sensor_clima, 3, NULL);
    
    printf("Iniciado recibir comandos... \n");
    xTaskCreate(tarea_recibir_comandos, "Task_RX", 4096, NULL, 4, NULL);
}
