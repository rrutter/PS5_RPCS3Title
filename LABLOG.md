# LABLOG — rrutter lab branch, RPCS3-on-PS5 (Heavenly Sword mission)

Base hardware: PS5 Phat, fw 9.60, kstuff-style JB; game from USB (G:), title PPSA99200.
Baseline config deltas from RPCS3 defaults, in the order they were earned:

| # | Lever | Value | Reason (run evidence) | Result |
|---|-------|-------|-----------------------|--------|
| 1 | rpcs3-interpreter.txt (file) | present | PPU-LLVM mis-executes on console (upstream known); interpreter = the working path | XMB + games boot |
| 2 | Play music during boot sequence | false | run4: overlay_audio fatal on SND0.AT3, null audio device | past it |
| 3 | Audio Renderer | Null | no audio device on console | (superseded by lab a72e85600 / upstream 8014376f8) |
| 4 | MSAA | Disabled | run6: VRAM-wall crash at eye-zoom (wiki-documented HS PiP class) | GAMEPLAY reached |
| 5 | Accurate SPU Reservations | false | run10: RDCH -> reservation_notifier mutex throw (EDEADLK on console mutexes) | gameplay sustained |
| 6 | PPU Threads | 1 | shrink TLS-emulation race surface | fatal -> freeze (same zone) |
| 7 | SPU Wake-Up Delay | 200us | run15/16: all SPURS kernels idle at pc 0x11a8 while game waits (lost wakeup theory) | NO CHANGE (run16 identical) |
| 8 | Accurate SPU DMA | true | run16: kernels never see work - job-list DMA may be dropped/raced on the fast path | testing run17 |
| 9 | Nuke BCUS98132 cache+dev_hdd0 install (rpcs3/cache/cache/BCUS98132, dev_hdd0/game/BCUS98132, dev_hdd1) | forums.rpcs3.net thread-206225: identical black-screen-at-transition fixed by wiping game-titled cache/hdd folders; our crashes since run8 wrote into caches mid-death | testing run18 |
| 10 | Log: {"": Trace} in config.yml | INERT: empty-string key exact-matches NO channel (set_level's exact-match branch no-ops). run21 proved it: zero .T lines | dead end |
| 11 | Log: {".*": Trace} | WORKED (run22: 2.47M .T lines) but SELF-DEFEATING: the 256MiB log capped at 0:00:22 - PPU schedule/syscall spam drowned everything; the freeze never got logged | dead end |
| 12 | Log: {cellSpurs, sys_spu, sys_event, sys_event_flag: Trace} | surgical: only the SPURS kick/completion + event channels; volume sane, cap never hit | testing run23 |
| 13 | Accurate Cache Line Stores | true | run19+traced: kernels never act while jobs queue - SPURS hands job descriptors over 128B cache-line writes; sloppy line stores can lose the pickup write | NO CHANGE (run24: identical freeze, kernels 0x11a8, 61029 ReadyCountStore polls) |
| 14 | +sys_lwmutex/sys_lwcond/sys_mutex/sys_cond at Trace (config only) | the SPURS handler wakeup rides lwcond_signal; freeze zone keeps spitting mutex EBUSY/ESRCH - catch the lock-layer story at the scene | run26 = full grid: 11 channels at trace + mailbox counters + SPURS live state |

UPSTREAM REPORT FILED: KongaTime/PS5_RPCS3Title issue #1 (full anatomy + wall chain).

Note: lever 8 (Accurate SPU DMA) tested with 9 in run18 - sterile baseline + both = identical
freeze at the same zone. Debris theory dead. Timing theory dead. Run18 signature unchanged:
kernels idle 0x11a8, main_thread 0xa4e118, mutex_destroy EBUSY x3 right before.

Lab code commits (PS5_RPCS3@lab): b5badc57c fatal stack-walk; bbae4d9ba status line lists SPU threads.
Title: 9d299c7 link emits eboot.map.
Superseded by upstream: a72e85600 (null audio layout) == upstream 8014376f8 (independent, theirs kept).

Current enemy: combat-init freeze. Game parks main_thread @ guest 0xa4e118; all 5
CellSpursKernelN idle at SPU pc 0x11a8 (wait-for-work); FMOD mixer alive. A kick or
completion event between SPURS kernel and PPU side never lands.

## The instrumented autopsy chain (runs 24-31, lab builds)
- run24 (lever 13): no change. 61029 ReadyCountStore polls; kernels mb w0/c0 always.
- Coherence test (live SPURS page, padding xB8): mirror/base/read32 all agree (BE twin
  efbeadde = correct) - WRITES LAND. light_op path innocent.
- Decay watch: xB8 sentinel persisted 68 pulses - no page-level stomp (caveat: xB8 sits
  past the kernels 0x00-0xB4 hot region).
- Full surgical trace: ZERO SPU-thread-originated events ever; write_spu_mb never called.
- PROVEN FREEZE ANATOMY: workloads RUNNABLE, game requests 5 SPUs, contention never rises,
  kernels park at 0x11a8 (NOT the upstream-tested 0x11e4 task-wait - image/layout differs),
  game spins on ReadyCountStore forever.
- OPEN: SPU-side DMA-in coherence (kernel reads of the struct) - the untested mile.
