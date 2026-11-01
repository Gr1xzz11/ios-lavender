/* Lavender PSCI reset diagnostic entry.
 * The stock DTB declares PSCI 1.0 with the SMC conduit.  This variant does
 * not touch UART, framebuffer, GIC, timer MMIO, watchdog or PMIC registers.
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
	bl	lavender_reset_main
3:	wfe
	b	3b
