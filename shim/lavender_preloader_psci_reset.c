#include <stdint.h>
#include "fdt.h"
#include "lavender_console.h"

#define FDT_MAGIC 0xd00dfeedU
#define FDT_BEGIN_NODE 1U
#define FDT_END_NODE 2U
#define FDT_PROP 3U
#define FDT_NOP 4U
#define FDT_END 9U
#define PSCI_SYSTEM_RESET 0x84000009ULL
#define XNU_WINDOW_START 0x80000000ULL
#define XNU_WINDOW_END 0x85600000ULL

static uint32_t be32(uintptr_t p) { return __builtin_bswap32(*(volatile uint32_t *)p); }
static uintptr_t align4(uintptr_t p) { return (p + 3U) & ~(uintptr_t)3U; }

static int bounded_string(uintptr_t p, uintptr_t end)
{
	while (p < end) if (*(volatile const uint8_t *)p++ == 0) return 1;
	return 0;
}

static int fdt_structure_ok(uintptr_t fdt, uint64_t total)
{
	uint64_t so = be32(fdt + 8), xo = be32(fdt + 12);
	uint64_t xs = be32(fdt + 32), ss = be32(fdt + 36);
	if (total < 40 || so > total || xo > total || ss > total - so || xs > total - xo)
		return 0;
	uintptr_t p = fdt + so, end = p + ss, strings = fdt + xo, strings_end = strings + xs;
	int depth = 0, ended = 0;
	while (p < end) {
		if (end - p < 4) return 0;
		uint32_t token = be32(p); p += 4;
		switch (token) {
		case FDT_BEGIN_NODE:
			if (++depth > 64 || !bounded_string(p, end)) return 0;
			while (p < end && *(volatile const uint8_t *)p) p++;
			p = align4(p + 1); if (p > end) return 0; break;
		case FDT_END_NODE:
			if (depth-- <= 0) return 0; break;
		case FDT_PROP: {
			if (end - p < 8) return 0;
			uint32_t len = be32(p), nameoff = be32(p + 4); p += 8;
			if (nameoff >= xs || !bounded_string(strings + nameoff, strings_end) ||
			    len > (uint64_t)(end - p)) return 0;
			p = align4(p + len); if (p > end) return 0; break;
		}
		case FDT_NOP: break;
		case FDT_END: if (depth != 0) return 0; ended = 1; p = end; break;
		default: return 0;
		}
	}
	return ended && depth == 0;
}

static int checked_initrd(uintptr_t dtb, uint64_t dtb_size, uint64_t *start, uint64_t *end)
{
	if (!fdt_structure_ok(dtb, dtb_size) ||
	    !fdt_chosen_u64(dtb, "linux,initrd-start", start) ||
	    !fdt_chosen_u64(dtb, "linux,initrd-end", end)) return 0;
	if (*end <= *start || (*start & 7) != 0) return 0;
	uint64_t size = *end - *start;
	return UINT64_MAX - *start >= size;
}

#ifdef LAVENDER_PRELOADER_CLASSIFIER
static int range_intersects(uint64_t start, uint64_t size, uint64_t lo, uint64_t hi)
{
	uint64_t end;
	if (UINT64_MAX - start < size)
		return 1;
	end = start + size;
	return start < hi && lo < end;
}

static uint64_t read_cntfrq(void)
{
	uint64_t value;
	__asm__ volatile("mrs %0, cntfrq_el0" : "=r"(value));
	return value;
}

static uint64_t read_cntpct(void)
{
	uint64_t value;
	__asm__ volatile("mrs %0, cntpct_el0" : "=r"(value));
	return value;
}

static void overlap_delay(void)
{
	uint64_t frequency = read_cntfrq();
	if (frequency != 0 && frequency <= 1000000000ULL && frequency <= UINT64_MAX / 2) {
		uint64_t deadline = read_cntpct() + frequency * 2;
		while ((int64_t)(read_cntpct() - deadline) < 0)
			__asm__ volatile("yield" ::: "memory");
		return;
	}
	/* Bounded fallback only; duration is not used as a calibrated fact. */
	volatile uint64_t loops = 8000000;
	while (loops--)
		__asm__ volatile("nop" ::: "memory");
}
#endif

__attribute__((noreturn)) static void psci_reset(void)
{
	register uint64_t x0 __asm__("x0") = PSCI_SYSTEM_RESET;
	register uint64_t x1 __asm__("x1") = 0, x2 __asm__("x2") = 0, x3 __asm__("x3") = 0;
	__asm__ volatile("smc #0" : "+r"(x0), "+r"(x1), "+r"(x2), "+r"(x3) ::
		"x4", "x5", "x6", "x7", "x8", "x9", "x10", "x11", "x12", "x13", "x14", "x15", "x16", "x17", "memory");
	for (;;) __asm__ volatile("wfe");
}

void shim_lavender_preloader_main(uint64_t dtb)
{
	uint64_t dtb_size, rd_start, rd_end;
	if (!dtb || !fdt_blob_size((uintptr_t)dtb, &dtb_size) ||
	    dtb > UINTPTR_MAX - dtb_size ||
	    !checked_initrd((uintptr_t)dtb, dtb_size, &rd_start, &rd_end))
		goto error;
	#ifdef LAVENDER_PRELOADER_CLASSIFIER
	if (range_intersects(rd_start, rd_end - rd_start,
		XNU_WINDOW_START, XNU_WINDOW_END))
		overlap_delay();
	psci_reset();
	#else
	lavender_uart_hex("PRELOADER-VALID ", rd_end - rd_start);
	psci_reset();
	#endif
error:
	#ifndef LAVENDER_PRELOADER_CLASSIFIER
	lavender_uart_str("PRELOADER ERROR\r\n");
	#endif
	for (;;) __asm__ volatile("wfe");
}
