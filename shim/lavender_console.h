#pragma once
#include <stdint.h>

#define UART_BASE 0x0c170000UL
#define UART_SR 0x08UL
#define UART_TF 0x70UL
#define UART_SR_TX_READY (1U << 2)

void lavender_uart_hex(const char *label, uint64_t value);
void lavender_uart_str(const char *s);
