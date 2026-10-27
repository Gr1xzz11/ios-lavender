/*
 * Lavender diagnostic entry.  ABL enters an Android arm64 Image at EL1 with
 * MMU and caches disabled and x0 containing its live FDT pointer.  This file
 * deliberately has no exception vector, MMU setup, IRQ setup, PSCI call, or
 * framebuffer access: a serial marker is the only observable side effect.
 */
	.section .text.head, "ax"
	.globl _head
_head:
	b	_start
	.long	0
	.quad	0
	.quad	_end
	.quad	0xa
	.quad	0
	.quad	0
	.quad	0
	.ascii	"ARM\x64"
	.long	0

	.text
	.globl _start
_start:
	msr	daifset, #0xf
	/* Preserve all conventional boot arguments before using x1/x2 below. */
	mov	x19, x0
	mov	x20, x1
	mov	x21, x2
	adr	x1, _stack_top
	mov	sp, x1
	adr	x1, _bss_start
	adr	x2, _bss_end
1:
	cmp	x1, x2
	b.hs	2f
	str	xzr, [x1], #8
	b	1b

2:
	mov	x0, x19
	mov	x1, x20
	mov	x2, x21
	bl	diag_main
3:
	wfe
	b	3b
