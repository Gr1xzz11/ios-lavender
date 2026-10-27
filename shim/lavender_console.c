#include "lavender_console.h"

/* No clock or pinctrl programming is attempted.  A gated UART yields no log. */
static void uart_putc(char c)
{
	volatile uint32_t *sr = (volatile uint32_t *)(UART_BASE + UART_SR);
	volatile uint32_t *tf = (volatile uint32_t *)(UART_BASE + UART_TF);
	if (*sr & UART_SR_TX_READY)
		*tf = (uint32_t)(uint8_t)c;
}

void lavender_uart_str(const char *s)
{
	while (*s)
		uart_putc(*s++);
}

void lavender_uart_hex(const char *label, uint64_t value)
{
	static const char hex[] = "0123456789abcdef";
	char buf[17];
	for (int i = 0; i < 16; i++)
		buf[i] = hex[(value >> (60 - i * 4)) & 0xf];
	buf[16] = 0;
	
	lavender_uart_str(label);
	lavender_uart_str(buf);
	lavender_uart_str("\r\n");
}
