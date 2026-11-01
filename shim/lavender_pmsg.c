#include <stdint.h>
#include "lavender_diag.h"

#define PMSG_BASE 0xA0200000ULL
#define PMSG_SIG 0x43474244U
#define PMSG_HEADER_SIZE 12U
#define PMSG_CAPACITY 0x1FFFF4U

static inline uint32_t pmsg_read32(uintptr_t address)
{
	return *(volatile const uint32_t *)address;
}

static inline void pmsg_write8(uintptr_t address, uint8_t value)
{
	*(volatile uint8_t *)address = value;
}

static inline void pmsg_barrier(void)
{
	__asm__ volatile("dsb sy" ::: "memory");
}

static inline void pmsg_clean_cache_line(uintptr_t address)
{
	/* Clean, rather than invalidate, so a cacheable alias cannot discard a
	 * dirty line belonging to this update. */
	__asm__ volatile("dc cvac, %0" :: "r"(address) : "memory");
}

static void pmsg_clean_range(uintptr_t start, uint64_t size)
{
	uintptr_t first = start & ~63ULL;
	uintptr_t last = (start + size + 63ULL) & ~63ULL;
	for (uintptr_t address = first; address < last; address += 64)
		pmsg_clean_cache_line(address);
	pmsg_barrier();
}

static void pmsg_clean_ring_range(uint32_t position, uint32_t size)
{
	uint32_t first = PMSG_CAPACITY - position;
	if (first > size)
		first = size;
	pmsg_clean_range(PMSG_BASE + PMSG_HEADER_SIZE + position, first);
	if (size > first)
		pmsg_clean_range(PMSG_BASE + PMSG_HEADER_SIZE, size - first);
}

static void pmsg_write_ring(uint32_t position, const uint8_t *data, uint32_t size)
{
	for (uint32_t i = 0; i < size; i++)
		pmsg_write8(PMSG_BASE + PMSG_HEADER_SIZE +
				((position + i) % PMSG_CAPACITY), data[i]);
}

/* Append exactly one marker using persistent_ram_buffer's [start,size] model. */
void lavender_pmsg_append_text(const uint8_t *marker, uint32_t marker_size)
{
	volatile uint32_t *header = (volatile uint32_t *)PMSG_BASE;
	uint32_t signature = pmsg_read32(PMSG_BASE);
	uint32_t start = pmsg_read32(PMSG_BASE + 4);
	uint32_t size = pmsg_read32(PMSG_BASE + 8);
	uint32_t position;
	uint32_t new_start;
	uint32_t new_size;

	if (signature != PMSG_SIG || start >= PMSG_CAPACITY ||
	    size > PMSG_CAPACITY || marker_size > PMSG_CAPACITY)
		return;

	/* persistent_ram_write() treats start as the next write position. */
	position = start;
	new_start = (start + marker_size) % PMSG_CAPACITY;
	new_size = size + marker_size;
	if (new_size > PMSG_CAPACITY)
		new_size = PMSG_CAPACITY;

	pmsg_write_ring(position, marker, marker_size);
	pmsg_clean_ring_range(position, marker_size);

	/* Publish data before start/size, as persistent_ram_write does. */
	header[1] = new_start;
	header[2] = new_size;
	pmsg_clean_range(PMSG_BASE + 4, 8);
}

void lavender_pmsg_append_marker(void)
{
	static const uint8_t marker[] = LAVENDER_TAG("LAVENDER:SHIM");
	lavender_pmsg_append_text(marker, sizeof(marker) - 1);
}
