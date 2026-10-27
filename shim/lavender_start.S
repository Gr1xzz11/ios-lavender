/* Lavender XNU Image entry.
 * ABL handoff is intentionally preserved: EL1, MMU/caches off, x0 = live DTB
 * is only a current hypothesis and is logged/validated by the loader.
 * XNU's start_first_cpu owns MMU/bootstrap-table setup after this shim.
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
	mov	x19, x0
	msr	spsel, #1
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
	bl	shim_lavender_main
3:
	wfe
	b	3b
