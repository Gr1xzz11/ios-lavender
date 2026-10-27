ENTRY(_head)
SECTIONS
{
	. = 0;
	.text : { *(.text.head) *(.text*) }
	.rodata : { *(.rodata*) }
	.data : { *(.data*) }
	. = ALIGN(16);
	_bss_start = .;
	.bss : { *(.bss*) *(COMMON) }
	. = ALIGN(16);
	_bss_end = .;
	/* Early shim stack only; XNU gets its own linked stacks. */
	. += 0x8000;
	. = ALIGN(16);
	_stack_top = .;
	_end = ALIGN(., 4096);
	/DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
