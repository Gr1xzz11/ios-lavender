#include <stdint.h>
void shim_lavender_preloader_main(uint64_t dtb);
void shim_lavender_main(uint64_t dtb) { shim_lavender_preloader_main(dtb); }
