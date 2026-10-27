/*
 * Read-only lavender bring-up marker.  The UART base/range and UARTDM register
 * offsets are confirmed by the extracted DTS plus the Qualcomm UARTDM Linux
 * driver. We only read status and perform bounded writes to TX FIFO; no clock,
 * pinctrl, GIC, timer, or display register is touched here.
 */
#include <stdint.h>

#define UART_BASE 0x0c170000UL
#define UART_SR   0x08UL
#define UART_TF   0x70UL
#define UART_SR_TX_READY (1U << 2)

__attribute__((used, section(".diag_marker")))
static const char diag_marker[] = "LAVENDER-DIAG:entry";

static inline void uart_putc(char c)
{
	for (unsigned tries = 0; tries < 100000; tries++) {
		if (*(volatile uint32_t *)(UART_BASE + UART_SR) & UART_SR_TX_READY) {
			*(volatile uint32_t *)(UART_BASE + UART_TF) = (uint32_t)(uint8_t)c;
			return;
		}
	}
}

static void uart_str(const char *s)
{
	while (*s)
		uart_putc(*s++);
}

static void uart_hex(uint64_t value)
{
	static const char hex[] = "0123456789abcdef";
	for (int shift = 60; shift >= 0; shift -= 4)
		uart_putc(hex[(value >> shift) & 0xf]);
}

static void uart_label_hex(const char *label, uint64_t value)
{
	uart_str(label);
	uart_hex(value);
	uart_str("\r\n");
}

void diag_main(uint64_t arg0, uint64_t arg1, uint64_t arg2)
{
	uart_str("LAVENDER-DIAG:entry\r\n");
	uart_label_hex("ARG0=0x", arg0);
	uart_label_hex("ARG1=0x", arg1);
	uart_label_hex("ARG2=0x", arg2);
	uint64_t mpidr;
	__asm__ volatile("mrs %0, mpidr_el1" : "=r"(mpidr));
	uart_label_hex("MPIDR=0x", mpidr);
	uart_str("\r\nLAVENDER-DIAG:stack-bss\r\n");
	for (;;)
		__asm__ volatile("wfe");
}
