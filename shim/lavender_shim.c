#include <stdint.h>
#include "lavender_diag.h"
#include "lavender_console.h"
#include "lavender_loader.h"

#ifdef LAVENDER_PMSG_SHIM
void lavender_pmsg_append_marker(void);
void lavender_pmsg_append_text(const uint8_t *marker, uint32_t size);
#endif

void shim_lavender_main(uint64_t dtb)
{
#ifdef LAVENDER_PMSG_SHIM
	lavender_pmsg_append_marker();
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:CALL_LOADER");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
#ifdef LAVENDER_HANDOFF_PROBE
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:HANDOFF_PROBE");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
	for (;;)
		__asm__ volatile("wfe");
#endif
#endif
#ifndef LAVENDER_LOADER_NO_UART
	const char *error;
	lavender_uart_str("LAVENDER XNU SHIM\r\n");
	lavender_uart_hex("DTB ", dtb);
	error = lavender_loader_boot((uintptr_t)dtb);
	lavender_uart_str("LOAD ERROR: ");
	lavender_uart_str(error);
	lavender_uart_str("\r\n");
#else
	(void)lavender_loader_boot((uintptr_t)dtb);
#endif
	for (;;)
		__asm__ volatile("wfe");
}
