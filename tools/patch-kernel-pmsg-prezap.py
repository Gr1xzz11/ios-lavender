#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "kernel"
core, hdr = root / "fs/pstore/ram_core.c", root / "include/linux/pstore_ram.h"
cs, hs = core.read_text(), hdr.read_text()
if "lavender_capture_prezap" in cs:
    raise SystemExit("pre-zap hook already present")
cs = cs.replace('#include <linux/vmalloc.h>\n', '#include <linux/vmalloc.h>\n#include <linux/debugfs.h>\n#include <linux/crc32.h>\n#include <linux/mutex.h>\n', 1)
mark = '#define PERSISTENT_RAM_SIG (0x43474244) /* DBGC */\n'
hook = r'''
#define LAVENDER_PREZAP_MAX 16384
static u8 lavender_prezap[LAVENDER_PREZAP_MAX];
static struct debugfs_blob_wrapper lavender_prezap_blob = { .data = lavender_prezap, .size = 0 };
static DEFINE_MUTEX(lavender_prezap_lock);
static void lavender_capture_prezap(struct persistent_ram_zone *prz)
{
	struct persistent_ram_buffer *b = prz->buffer;
	size_t cap = prz->buffer_size, pos[4], off = 64;
	u32 sig, start, size, crc;
	unsigned int i;
	if (!b || cap < 12 || cap > 0x200000 || cap > SIZE_MAX - 12) return;
	sig = b->sig; start = atomic_read(&b->start); size = atomic_read(&b->size);
	memset(lavender_prezap, 0, sizeof(lavender_prezap));
	memcpy(lavender_prezap, &sig, 4); memcpy(lavender_prezap + 4, &start, 4);
	memcpy(lavender_prezap + 8, &size, 4); memcpy(lavender_prezap + 12, &cap, 4);
	if (start < cap && size <= cap) {
		pos[0] = 0; pos[1] = start & ~((size_t)4095); pos[2] = cap - 4096;
		pos[3] = (pos[1] + 4096) % cap;
		for (i = 0; i < 4; i++) {
			size_t first = min_t(size_t, 4096, cap - pos[i]);
			memcpy_fromio(lavender_prezap + off + i * 4096, b->data + pos[i], first);
			if (first < 4096) memcpy_fromio(lavender_prezap + off + i * 4096 + first, b->data, 4096 - first);
		}
		crc = crc32(0, lavender_prezap + 64, 4 * 4096);
		memcpy(lavender_prezap + 16, &crc, 4); lavender_prezap_blob.size = off + 4 * 4096;
	}
	mutex_lock(&lavender_prezap_lock); debugfs_create_blob("lavender_prezap", 0444, NULL, &lavender_prezap_blob); mutex_unlock(&lavender_prezap_lock);
}
'''
cs = cs.replace(mark, mark + hook, 1)
needle = '\tret = persistent_ram_init_ecc(prz, ecc_info);\n'
cs = cs.replace(needle, '\tlavender_capture_prezap(prz);\n\n' + needle, 1)
field = '\tchar *old_log;\n\tsize_t old_log_size;\n'
hs = hs.replace(field, field + '\tvoid *lavender_prezap;\n\tsize_t lavender_prezap_len;\n', 1)
core.write_text(cs); hdr.write_text(hs)
