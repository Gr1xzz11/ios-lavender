#include <stdint.h>
#include "lavender_console.h"
#include "lavender_loader.h"

#if !defined(LAVENDER_LOADER_STAGE1_RESET) && !defined(LAVENDER_LOADER_STAGE2_RESET)
static __attribute__((noreturn)) void error_halt(void)
{
	/* Physical key recovery remains available; never report reset success. */
	for (;;)
		__asm__ volatile("wfe");
}
#endif

void shim_lavender_main(uint64_t dtb)
{
	#if defined(LAVENDER_LOADER_STAGE1_RESET) || defined(LAVENDER_LOADER_STAGE2_RESET)
	lavender_loader_boot((uintptr_t)dtb);
	#else
	const char *error;
	lavender_uart_str("LAVENDER LOADER-PSCI-RESET\r\n");
	lavender_uart_hex("DTB ", dtb);
	error = lavender_loader_boot((uintptr_t)dtb);
	lavender_uart_str("LOAD ERROR: ");
	lavender_uart_str(error);
	lavender_uart_str("\r\n");
	error_halt();
	#endif
}
