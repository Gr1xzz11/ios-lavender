#pragma once
#include <stdint.h>

const char *lavender_loader_boot(uintptr_t dtb);
void lavender_loader_checkpoint(uint64_t stage);
#if defined(LAVENDER_LOADER_PSCI_RESET) || defined(LAVENDER_LOADER_STAGE1_RESET) || defined(LAVENDER_LOADER_STAGE2_RESET)
void lavender_loader_diag_reset(uint64_t entry_pa, uint64_t boot_args_pa);
#endif
