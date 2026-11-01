#include <stdint.h>
#include "lavender_diag.h"
#include "fdt.h"
#include "lavender_console.h"
#include "lavender_loader.h"

#ifdef LAVENDER_PMSG_SHIM
void lavender_pmsg_append_text(const uint8_t *marker, uint32_t size);
#define PMSG_MARK(text) do { \
	static const uint8_t marker[] = LAVENDER_TAG(text); \
	lavender_pmsg_append_text(marker, sizeof(marker) - 1); \
} while (0)
#else
#define PMSG_MARK(text) do { } while (0)
#endif

#define BOOT_LINE_LENGTH 608
#define PAGE_16K 0x4000ULL
#define RAM_BASE 0x80000000ULL
#define RAM_END 0x85600000ULL

extern char _head[];
extern char _end[];

struct payload_seg {
	uint64_t vmaddr, vmsize, file_off, file_size;
};
struct source_range {
	uint64_t start, size;
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

static int round8(uint64_t value, uint64_t *out)
{
	if (value > UINT64_MAX - 7)
		return 1;
	*out = (value + 7) & ~7ULL;
	return 0;
}

static int range_ok(uint64_t start, uint64_t size)
{
	uint64_t end;
	if (add_overflow(start, size, &end) || start < RAM_BASE || end > RAM_END)
		return 0;
	return 1;
}

static int range_intersects(uint64_t a, uint64_t asize, uint64_t b, uint64_t bsize)
{
	uint64_t aend, bend;
	if (add_overflow(a, asize, &aend) || add_overflow(b, bsize, &bend))
		return 1;
	return a < bend && b < aend;
}

static int va_to_pa(uint64_t va, uint64_t virt_base, uint64_t phys_base,
			uint64_t *pa)
{
	uint64_t offset;
	if (va < virt_base)
		return 1;
	offset = va - virt_base;
	return add_overflow(phys_base, offset, pa);
}

static uintptr_t loader_runtime_start(void)
{
	uintptr_t start;
	__asm__ volatile("adr %0, _head" : "=r"(start));
	return start;
}

static void copy_overlap_safe(uintptr_t dst, uintptr_t src, uint64_t n)
{
	if (dst > src && dst - src < n) {
		for (uint64_t i = n; i >= 8; i -= 8)
			*(volatile uint64_t *)(dst + i - 8) =
				*(volatile const uint64_t *)(src + i - 8);
		for (uint64_t i = n & 7; i != 0; i--)
			*(volatile uint8_t *)(dst + i - 1) =
				*(volatile const uint8_t *)(src + i - 1);
		return;
	}
	for (uint64_t i = 0; i + 8 <= n; i += 8)
		*(volatile uint64_t *)(dst + i) =
			*(volatile const uint64_t *)(src + i);
	for (uint64_t i = n & ~7ULL; i < n; i++)
		*(volatile uint8_t *)(dst + i) =
			*(volatile const uint8_t *)(src + i);
}

static void zero64(uintptr_t dst, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	for (uint64_t i = 0; i < n / 8; i++)
		d[i] = 0;
}

typedef void (*xnu_entry_t)(uint64_t boot_args_pa);

__attribute__((weak)) void lavender_loader_checkpoint(uint64_t stage)
{
	(void)stage;
}

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
	struct payload_seg segs[32];
	struct source_range source_ranges[33];
	uint32_t segment_source_index[32];
	uint32_t source_count = 0;
	for (uint32_t i = 0; i < 32; i++)
		segment_source_index[i] = UINT32_MAX;
	uintptr_t loader_start = loader_runtime_start();
	uint64_t loader_size = (uint64_t)(_end - _head);
	if (!fdt_blob_size(dtb, &dtb_size) ||
	    !fdt_chosen_u64(dtb, "linux,initrd-start", &rd_start) ||
	    !fdt_chosen_u64(dtb, "linux,initrd-end", &rd_end))
		return "no live initrd/DTB";
	if (dtb_size > UINT64_MAX - dtb)
		return "DTB address overflow";
	if (rd_end <= rd_start || (rd_start & 7))
		return "bad initrd range";
	if (range_intersects(loader_start, loader_size, dtb, dtb_size))
		return "DTB overlaps loader";
	if (range_intersects(loader_start, loader_size, rd_start, rd_end - rd_start))
		return "ramdisk overlaps loader";
	if (dtb < rd_end && rd_start < dtb + dtb_size)
		return "DTB overlaps ramdisk";
#ifdef LAVENDER_PMSG_SHIM
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:DTB_OK");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
#endif
	lavender_loader_checkpoint(1);
#ifdef LAVENDER_LOADER_STAGE1_RESET
	lavender_loader_diag_reset(0, 0);
#endif

	const struct payload *p = (const struct payload *)rd_start;
	if (!magic_ok(p->magic) || p->version != 1 ||
	    p->nsegs == 0 || p->nsegs > 32 || p->adt_off < 0x2a8)
		return "bad XNU payload";
	if (p->adt_off < 0x2a8 + (uint64_t)p->nsegs * sizeof(struct payload_seg))
		return "payload segment table outside header";
	if (add_overflow(rd_start, p->adt_off, &payload_end) ||
	    add_overflow(payload_end, p->adt_size, &payload_end) || payload_end > rd_end)
		return "payload metadata outside ramdisk";
#ifdef LAVENDER_PMSG_SHIM
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:PAYLOAD_OK");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
#endif
	uint64_t adt_off = p->adt_off;
	uint64_t adt_size = p->adt_size;
	uint64_t virt_base = p->virt_base;
	uint64_t phys_base = p->phys_base;
	uint64_t mem_size = p->mem_size;
	uint64_t kernel_end = p->kernel_end;
	uint64_t entry_va = p->entry_va;
	uint32_t nsegs = p->nsegs;
	char cmdline[BOOT_LINE_LENGTH];
	for (int i = 0; i < BOOT_LINE_LENGTH; i++)
		cmdline[i] = p->cmdline[i];
	for (uint32_t i = 0; i < nsegs; i++)
		segs[i] = p->segs[i];
	lavender_loader_checkpoint(2);
	if (phys_base != RAM_BASE || mem_size != RAM_END - RAM_BASE ||
	    virt_base == 0 || kernel_end <= virt_base)
		return "unexpected lavender memory contract";
#ifdef LAVENDER_PMSG_SHIM
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:CONTRACT_OK");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
#endif

	PMSG_MARK("LAVENDER:SEGMENTS_BEGIN");
	for (uint32_t i = 0; i < nsegs; i++) {
		if (i == 0) PMSG_MARK("LAVENDER:SEG0_CHECK_BEGIN");
		if (i == 1) PMSG_MARK("LAVENDER:SEG1_CHECK_BEGIN");
		if (i == 2) PMSG_MARK("LAVENDER:SEG2_CHECK_BEGIN");
		if (i == 3) PMSG_MARK("LAVENDER:SEG3_CHECK_BEGIN");
		if (i == 4) PMSG_MARK("LAVENDER:SEG4_CHECK_BEGIN");
		if (i == 5) PMSG_MARK("LAVENDER:SEG5_CHECK_BEGIN");
		if (i == 6) PMSG_MARK("LAVENDER:SEG6_CHECK_BEGIN");
		if (i == 7) PMSG_MARK("LAVENDER:SEG7_CHECK_BEGIN");
		if (i == 8) PMSG_MARK("LAVENDER:SEG8_CHECK_BEGIN");
		if (i == 9) PMSG_MARK("LAVENDER:SEG9_CHECK_BEGIN");
		const struct payload_seg *s = &segs[i];
		uint64_t src_start, src_end, src_size, dst;
		if (s->file_size > s->vmsize) {
			PMSG_MARK("LAVENDER:SEG_FAIL_FILESIZE");
			return "segment file larger than VM size";
		}
		if (add_overflow(rd_start, s->file_off, &src_start)) {
			PMSG_MARK("LAVENDER:SEG_FAIL_SRC_ADD");
			return "segment source address overflow";
		}
		if (round8(s->file_size, &src_size)) {
			PMSG_MARK("LAVENDER:SEG_FAIL_ROUND");
			return "segment source size overflow";
		}
		if (add_overflow(src_start, src_size, &src_end) || src_end > rd_end) {
			PMSG_MARK("LAVENDER:SEG_FAIL_SRC_RANGE");
			return "segment source outside initrd";
		}
		if (s->vmaddr < virt_base) {
			PMSG_MARK("LAVENDER:SEG_FAIL_VM");
			return "segment VM below kernel base";
		}
		if (va_to_pa(s->vmaddr, virt_base, phys_base, &dst)) {
			PMSG_MARK("LAVENDER:SEG_FAIL_DST_ADD");
			return "segment destination overflow";
		}
		if (!range_ok(dst, s->vmsize)) {
			PMSG_MARK("LAVENDER:SEG_FAIL_DST_RANGE");
			return "segment destination outside RAM";
		}
		if (range_intersects(loader_start, loader_size, dst, s->vmsize)) {
			PMSG_MARK("LAVENDER:SEG_FAIL_LOADER");
			return "segment destination overlaps loader";
		}
		if (src_size != 0) {
			segment_source_index[i] = source_count;
			if (i == 0) PMSG_MARK("LAVENDER:SEG0_PRE_OK");
			source_ranges[source_count++] = (struct source_range){src_start, src_size};
		}
		if (i == 0) PMSG_MARK("LAVENDER:SEG0_OK");
		if (i == 1) PMSG_MARK("LAVENDER:SEG1_OK");
		if (i == 2) PMSG_MARK("LAVENDER:SEG2_OK");
		if (i == 3) PMSG_MARK("LAVENDER:SEG3_OK");
		if (i == 4) PMSG_MARK("LAVENDER:SEG4_OK");
		if (i == 5) PMSG_MARK("LAVENDER:SEG5_OK");
		if (i == 6) PMSG_MARK("LAVENDER:SEG6_OK");
		if (i == 7) PMSG_MARK("LAVENDER:SEG7_OK");
		if (i == 8) PMSG_MARK("LAVENDER:SEG8_OK");
		if (i == 9) PMSG_MARK("LAVENDER:SEG9_OK");
	}
	if (adt_size != 0) {
		uint64_t src_start, src_size, src_end;
		if (add_overflow(rd_start, adt_off, &src_start) ||
		    round8(adt_size, &src_size) ||
		    add_overflow(src_start, src_size, &src_end) || src_end > rd_end) {
			return "ADT source address overflow";
		}
		source_ranges[source_count++] = (struct source_range){src_start, src_size};
	}
	PMSG_MARK("LAVENDER:SOURCES_OK");
	/* Every destination must preserve every source range still read below. */
	PMSG_MARK("LAVENDER:OVERLAP_BEGIN");
	for (uint32_t i = 0; i < nsegs; i++) {
		const struct payload_seg *s = &segs[i];
		uint64_t dst;
		if (va_to_pa(s->vmaddr, virt_base, phys_base, &dst))
			return "segment destination conversion overflow";
		for (uint32_t j = 0; j < i; j++)
			if (segment_source_index[j] != UINT32_MAX &&
			    range_intersects(dst, s->vmsize,
			                    source_ranges[segment_source_index[j]].start,
			                    source_ranges[segment_source_index[j]].size))
				return "segment overwrites earlier unread initrd source";
		for (uint32_t j = 0; j < i; j++) {
			const struct payload_seg *previous = &segs[j];
			uint64_t previous_dst;
			if (va_to_pa(previous->vmaddr, virt_base, phys_base,
			             &previous_dst))
				return "previous destination conversion overflow";
			if (range_intersects(dst, s->vmsize, previous_dst, previous->vmsize))
				return "Mach-O destinations overlap";
		}
	}
	PMSG_MARK("LAVENDER:OVERLAP_OK");
#ifdef LAVENDER_PMSG_SHIM
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:SEGMENTS_OK");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
#endif
	lavender_loader_checkpoint(3);
#ifdef LAVENDER_LOADER_STAGE2_RESET
	lavender_loader_diag_reset(0, 0);
#endif

	uint64_t kernel_pa;
	uint64_t metadata_size;
	if (va_to_pa(kernel_end, virt_base, phys_base, &kernel_pa) ||
	    add_overflow(adt_size, PAGE_16K, &metadata_size) ||
	    !range_ok(kernel_pa, metadata_size))
		return "ADT/boot_args outside lavender RAM window";
	uint64_t ba_unaligned;
	if (add_overflow(kernel_pa, adt_size + PAGE_16K - 1, &ba_unaligned))
		return "boot_args address overflow";
	uint64_t ba_pa = ba_unaligned & ~(PAGE_16K - 1);
	uint64_t top;
	if (add_overflow(ba_pa, PAGE_16K, &top) || top > RAM_END)
		return "topOfKernelData outside lavender RAM window";
	if (range_intersects(loader_start, loader_size, kernel_pa, adt_size) ||
	    range_intersects(loader_start, loader_size, ba_pa, PAGE_16K))
		return "metadata destination overlaps source or loader";
	for (uint32_t i = 0; i < source_count; i++)
		if (range_intersects(kernel_pa, adt_size, source_ranges[i].start, source_ranges[i].size) ||
		    range_intersects(ba_pa, PAGE_16K, source_ranges[i].start, source_ranges[i].size))
			return "metadata destination overwrites unread initrd source";
	for (uint32_t i = 0; i < nsegs; i++) {
		const struct payload_seg *s = &segs[i];
		uint64_t dst;
		if (va_to_pa(s->vmaddr, virt_base, phys_base, &dst))
			return "metadata destination segment conversion overflow";
		if (range_intersects(kernel_pa, adt_size, dst, s->vmsize) ||
		    range_intersects(ba_pa, PAGE_16K, dst, s->vmsize))
			return "metadata destination overlaps segment";
	}
#ifdef LAVENDER_PMSG_SHIM
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:MEM_OK");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
#endif
	lavender_loader_checkpoint(4);
	/* Consume the ADT before segment zero-fill can overwrite its source tail. */
	copy_overlap_safe(kernel_pa, rd_start + adt_off, adt_size);

#ifdef LAVENDER_PMSG_SHIM
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:COPY");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
#endif
	for (uint32_t i = nsegs; i-- > 0;) {
		const struct payload_seg *s = &segs[i];
		uint64_t dst;
		if (va_to_pa(s->vmaddr, virt_base, phys_base, &dst))
			return "copy destination conversion overflow";
		if (i == nsegs - 1)
			PMSG_MARK("LAVENDER:COPY_FIRST_BEFORE");
		if (i == 0)
			PMSG_MARK("LAVENDER:SEG0_COPY_BEGIN");
		copy_overlap_safe(dst, rd_start + s->file_off, s->file_size);
		if (i == 0)
			PMSG_MARK("LAVENDER:SEG0_COPY_DONE");
		if (i == nsegs - 1)
			PMSG_MARK("LAVENDER:COPY_FIRST_AFTER");
		if (s->vmsize > s->file_size)
			zero64(dst + ((s->file_size + 7) & ~7ULL),
			       s->vmsize - ((s->file_size + 7) & ~7ULL));
	}
	zero64(ba_pa, PAGE_16K);
	volatile struct boot_args *ba = (volatile struct boot_args *)ba_pa;
	ba->Revision = 2;
	ba->Version = 2;
	ba->virtBase = virt_base;
	ba->physBase = phys_base;
	ba->memSize = mem_size;
	ba->topOfKernelData = top;
	/* Lavender has no verified framebuffer handoff: leave Boot_Video zero. */
	ba->deviceTreeP = kernel_pa;
	ba->deviceTreeLength = (uint32_t)adt_size;
	for (int i = 0; i < BOOT_LINE_LENGTH; i++)
		ba->CommandLine[i] = cmdline[i];
	ba->memSizeActual = mem_size;
#ifdef LAVENDER_PMSG_SHIM
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:BOOTARGS");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
#endif
	lavender_loader_checkpoint(5);

	uint64_t entry_pa;
	if (va_to_pa(entry_va, virt_base, phys_base, &entry_pa))
		return "entry address conversion overflow";
#ifndef LAVENDER_LOADER_NO_UART
	lavender_uart_hex("XNU PA ", entry_pa);
	lavender_uart_hex("BOOTARGS ", ba_pa);
#endif
	lavender_loader_checkpoint(6);
	/* MMU/cache remain off. XNU start_first_cpu owns its bootstrap mappings. */
	__asm__ volatile("dsb sy; ic iallu; dsb sy; isb" ::: "memory");
#ifdef LAVENDER_PMSG_SHIM
	{
		static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:LOADER");
		lavender_pmsg_append_text(marker, sizeof(marker) - 1);
	}
#endif
#ifdef LAVENDER_LOADER_PSCI_RESET
	lavender_loader_diag_reset(entry_pa, ba_pa);
#else
	((xnu_entry_t)(uintptr_t)entry_pa)(ba_pa);
#endif
	return "xnu returned";
}
