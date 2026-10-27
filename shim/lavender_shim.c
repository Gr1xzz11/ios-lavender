#include <stdint.h>
#include "lavender_console.h"
#include "lavender_loader.h"

void shim_lavender_main(uint64_t dtb)
{
	const char *error;
	lavender_uart_str("LAVENDER XNU SHIM\r\n");
	lavender_uart_hex("DTB ", dtb);
	error = lavender_loader_boot((uintptr_t)dtb);
	lavender_uart_str("LOAD ERROR: ");
	lavender_uart_str(error);
	lavender_uart_str("\r\n");
	for (;;)
		__asm__ volatile("wfe");
}
