/* A bounded, no-MMIO execution marker for the lavender boot-chain test. */
#include <stdint.h>

#define PSCI_SYSTEM_RESET 0x84000009ULL

__attribute__((used, section(".diag_marker")))
static const char lavender_reset_marker[] = "LAVENDER-DIAG:psci-reset";

static void short_delay(void)
{
	/* Deliberately instruction-counted: no timer or peripheral access. */
	volatile uint64_t count = 4000000;
	while (count--)
		__asm__ volatile("nop" ::: "memory");
}

static __attribute__((noreturn)) void psci_system_reset(void)
{
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

void lavender_reset_main(uint64_t arg0, uint64_t arg1, uint64_t arg2)
{
	(void)arg0;
	(void)arg1;
	(void)arg2;
	short_delay();
	psci_system_reset();
}
