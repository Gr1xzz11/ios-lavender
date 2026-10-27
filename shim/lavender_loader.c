#include <stdint.h>
#include "fdt.h"
#include "lavender_console.h"
#include "lavender_loader.h"

#define BOOT_LINE_LENGTH 608
#define PAGE_16K 0x4000ULL
#define RAM_BASE 0x80000000ULL
#define RAM_END 0x85600000ULL

struct payload_seg {
	uint64_t vmaddr, vmsize, file_off, file_size;
};
struct payload {
	char magic[8];
	uint32_t version, nsegs;
	uint64_t virt_base, entry_va, adt_off, adt_size, kernel_end;
	uint64_t phys_base, mem_size;
	char cmdline[BOOT_LINE_LENGTH];
	struct payload_seg segs[];
};
struct boot_video {
	uint64_t v_baseAddr, v_display, v_rowBytes, v_width, v_height, v_depth;
};
struct boot_args {
	uint16_t Revision, Version;
	uint64_t virtBase, physBase, memSize, topOfKernelData;
	struct boot_video Video;
	uint32_t machineType;
	uint64_t deviceTreeP;
	uint32_t deviceTreeLength;
	char CommandLine[BOOT_LINE_LENGTH];
	uint64_t bootFlags, memSizeActual;
};

_Static_assert(__builtin_offsetof(struct payload, segs) == 0x2a8, "payload layout");
_Static_assert(sizeof(struct boot_args) == 736, "boot_args layout");

static int add_overflow(uint64_t a, uint64_t b, uint64_t *out)
{
	*out = a + b;
	return *out < a;
}

static int range_ok(uint64_t start, uint64_t size)
{
	uint64_t end;
	if (add_overflow(start, size, &end) || start < RAM_BASE || end > RAM_END)
		return 0;
	return 1;
}

static void copy64(uintptr_t dst, uintptr_t src, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	volatile const uint64_t *s = (volatile const uint64_t *)src;
	for (uint64_t i = 0; i < (n + 7) / 8; i++)
		d[i] = s[i];
}

static void zero64(uintptr_t dst, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	for (uint64_t i = 0; i < n / 8; i++)
		d[i] = 0;
}

typedef void (*xnu_entry_t)(uint64_t boot_args_pa);

static int magic_ok(const char *magic)
{
	static const char expected[] = "SWEETXNU";
	for (int i = 0; i < 8; i++)
		if (magic[i] != expected[i])
			return 0;
	return 1;
}

const char *lavender_loader_boot(uintptr_t dtb)
{
uint64_t dtb_size, rd_start, rd_end, payload_end;
if (!fdt_blob_size(dtb, &dtb_size) ||
    !fdt_chosen_u64(dtb, "linux,initrd-start", &rd_start) ||
	    !fdt_chosen_u64(dtb, "linux,initrd-end", &rd_end))
		return "no live initrd/DTB";
	if (dtb_size > UINT64_MAX - dtb ||
	    (dtb < RAM_END && dtb + dtb_size > RAM_BASE))
		return "DTB overlaps XNU managed RAM";
	if (rd_end <= rd_start || (rd_start & 7))
		return "bad initrd range";
	if (dtb < rd_end && rd_start < dtb + dtb_size)
		return "DTB overlaps ramdisk";

	const struct payload *p = (const struct payload *)rd_start;
	if (!magic_ok(p->magic) || p->version != 1 ||
	    p->nsegs == 0 || p->nsegs > 32 || p->adt_off < 0x2a8)
		return "bad XNU payload";
	if (p->adt_off < 0x2a8 + (uint64_t)p->nsegs * sizeof(struct payload_seg))
		return "payload segment table outside header";
	if (add_overflow(rd_start, p->adt_off, &payload_end) ||
	    add_overflow(payload_end, p->adt_size, &payload_end) || payload_end > rd_end)
		return "payload metadata outside ramdisk";
	if (p->phys_base != RAM_BASE || p->mem_size != RAM_END - RAM_BASE ||
	    p->virt_base == 0 || p->kernel_end <= p->virt_base)
		return "unexpected lavender memory contract";

	uint64_t pa_delta = p->phys_base - p->virt_base;
	for (uint32_t i = 0; i < p->nsegs; i++) {
		const struct payload_seg *s = &p->segs[i];
		uint64_t src_end, dst;
		if (s->file_size > s->vmsize ||
		    add_overflow(s->file_off, s->file_size, &src_end) ||
		    rd_start + src_end > rd_end ||
		    s->vmaddr < p->virt_base ||
		    add_overflow(s->vmaddr, pa_delta, &dst) ||
		    !range_ok(dst, s->vmsize))
			return "segment outside lavender RAM window";
	}

	uint64_t kernel_pa;
	if (add_overflow(p->kernel_end, pa_delta, &kernel_pa) ||
	    !range_ok(kernel_pa, p->adt_size + PAGE_16K))
		return "ADT/boot_args outside lavender RAM window";
	uint64_t ba_pa = (kernel_pa + p->adt_size + PAGE_16K - 1) & ~(PAGE_16K - 1);
	uint64_t top = ba_pa + PAGE_16K;
	if (top > RAM_END)
		return "topOfKernelData outside lavender RAM window";

	/* The loader must never copy from a ramdisk that lies in XNU-managed RAM. */
	if (rd_start < RAM_END && rd_end > RAM_BASE)
		return "ramdisk overlaps XNU managed RAM";

	for (uint32_t i = 0; i < p->nsegs; i++) {
		const struct payload_seg *s = &p->segs[i];
		uint64_t dst = s->vmaddr + pa_delta;
		copy64(dst, rd_start + s->file_off, s->file_size);
		if (s->vmsize > s->file_size)
			zero64(dst + ((s->file_size + 7) & ~7ULL),
			       s->vmsize - ((s->file_size + 7) & ~7ULL));
	}
	copy64(kernel_pa, rd_start + p->adt_off, p->adt_size);
	zero64(ba_pa, PAGE_16K);
	volatile struct boot_args *ba = (volatile struct boot_args *)ba_pa;
	ba->Revision = 2;
	ba->Version = 2;
	ba->virtBase = p->virt_base;
	ba->physBase = p->phys_base;
	ba->memSize = p->mem_size;
	ba->topOfKernelData = top;
	/* Lavender has no verified framebuffer handoff: leave Boot_Video zero. */
	ba->deviceTreeP = kernel_pa - pa_delta;
	ba->deviceTreeLength = (uint32_t)p->adt_size;
	for (int i = 0; i < BOOT_LINE_LENGTH; i++)
		ba->CommandLine[i] = p->cmdline[i];
	ba->memSizeActual = p->mem_size;

	uint64_t entry_pa = p->entry_va + pa_delta;
	lavender_uart_hex("XNU PA ", entry_pa);
	lavender_uart_hex("BOOTARGS ", ba_pa);
	/* MMU/cache remain off. XNU start_first_cpu owns its bootstrap mappings. */
	__asm__ volatile("dsb sy; ic iallu; dsb sy; isb" ::: "memory");
	((xnu_entry_t)(uintptr_t)entry_pa)(ba_pa);
	return "xnu returned";
}
