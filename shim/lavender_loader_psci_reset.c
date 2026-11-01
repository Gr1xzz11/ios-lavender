#include <stdint.h>
#include "lavender_console.h"
#include "lavender_loader.h"

#define PSCI_SYSTEM_RESET 0x84000009ULL

void lavender_loader_checkpoint(uint64_t stage)
{
	#if defined(LAVENDER_LOADER_STAGE1_RESET) || defined(LAVENDER_LOADER_STAGE2_RESET)
	(void)stage;
	#else
	lavender_uart_hex("LOADER-STAGE ", stage);
	#endif
}

static void short_delay(void)
{
	volatile uint64_t count = 4000000;
	while (count--)
		__asm__ volatile("nop" ::: "memory");
}

__attribute__((noreturn)) void lavender_loader_diag_reset(uint64_t entry_pa,
	uint64_t boot_args_pa)
{
	#if defined(LAVENDER_LOADER_STAGE1_RESET) || defined(LAVENDER_LOADER_STAGE2_RESET)
	(void)entry_pa;
	(void)boot_args_pa;
	#else
	lavender_uart_hex("READY-ENTRY ", entry_pa);
	lavender_uart_hex("READY-BOOTARGS ", boot_args_pa);
	#endif
	short_delay();
	register uint64_t x0 __asm__("x0") = PSCI_SYSTEM_RESET;
	register uint64_t x1 __asm__("x1") = 0;
	register uint64_t x2 __asm__("x2") = 0;
	register uint64_t x3 __asm__("x3") = 0;
	__asm__ volatile("smc #0"
		: "+r"(x0), "+r"(x1), "+r"(x2), "+r"(x3)
		:
		: "x4", "x5", "x6", "x7", "x8", "x9", "x10", "x11",
		  "x12", "x13", "x14", "x15", "x16", "x17", "memory");
	for (;;)
		__asm__ volatile("wfe");
}
