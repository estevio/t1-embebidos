idf_component_register(
    SRCS "main.c"
    PRIV_REQUIRES spi_flash nvs_flash
    REQUIRES esp_driver_uart
    INCLUDE_DIRS "."
)
