/*
 * Delayed diagnostic code installed at the beginning of XNU __start.
 *
 * This uses only the architected physical counter and PSCI SMC.  It has no
 * stack, MMIO, UART, framebuffer, or RAM marker dependency.  A bad/constant
 * timer fails closed in WFE; a trap caused by firmware trapping the EL0 timer
 * registers remains a platform-level failure that this tiny entry cannot
 * catch without installing exception vectors.
 */
.section .text, "ax"
.align 2
.globl lavender_xnu_timer_entry
.type lavender_xnu_timer_entry, %function
lavender_xnu_timer_entry:
    mrs     x9, CurrentEL
    ubfx    x9, x9, #2, #2
    cmp     x9, #1
    b.ne    timer_fail
    mrs     x1, CNTFRQ_EL0
    movz    x4, #0x4240
    movk    x4, #0xf, lsl #16
    cmp     x1, x4
    b.lo    timer_fail
    movz    x5, #0xca00
    movk    x5, #0x3b9a, lsl #16
    cmp     x1, x5
    b.hi    timer_fail

    /* CNTFRQ_EL0 must be stable, not an accidental transient read. */
    mrs     x2, CNTFRQ_EL0
    cmp     x1, x2
    b.ne    timer_fail

    /* Verify that the selected physical counter advances. */
    mrs     x2, CNTPCT_EL0
    mov     x4, #4096
1:  subs    x4, x4, #1
    b.ne    1b
    mrs     x3, CNTPCT_EL0
    cmp     x3, x2
    b.lo    timer_fail
    b.eq    timer_fail

    /* The frequency bound makes this multiplication overflow-safe. */
    mov     x6, #10
    mul     x6, x1, x6
2:  mrs     x7, CNTPCT_EL0
    sub     x8, x7, x2
    cmp     x8, x6
    b.lo    2b

    /* PSCI_SYSTEM_RESET, SMCCC 32-bit convention, via the confirmed SMC. */
    mov     w0, #9
    movk    w0, #0x8400, lsl #16
    smc     #0
3:  wfe
    b       3b

timer_fail:
4:  wfe
    b       4b
.size lavender_xnu_timer_entry, .-lavender_xnu_timer_entry
