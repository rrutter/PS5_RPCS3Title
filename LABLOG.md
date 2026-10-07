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
| 10 | Log: {: Trace} in config.yml | the CORRECT full-trace lever: logs::reset() at boot wipes pre-boot set_level calls, THEN the config Log section applies - my flag-file set_level never survived boot (run19/20: zero .T lines). RPCS3 archives document exactly this reset dance (PR 18445 zone) | testing run21 |

Note: lever 8 (Accurate SPU DMA) tested with 9 in run18 - sterile baseline + both = identical
freeze at the same zone. Debris theory dead. Timing theory dead. Run18 signature unchanged:
kernels idle 0x11a8, main_thread 0xa4e118, mutex_destroy EBUSY x3 right before.

Lab code commits (PS5_RPCS3@lab): b5badc57c fatal stack-walk; bbae4d9ba status line lists SPU threads.
Title: 9d299c7 link emits eboot.map.
Superseded by upstream: a72e85600 (null audio layout) == upstream 8014376f8 (independent, theirs kept).

Current enemy: combat-init freeze. Game parks main_thread @ guest 0xa4e118; all 5
CellSpursKernelN idle at SPU pc 0x11a8 (wait-for-work); FMOD mixer alive. A kick or
completion event between SPURS kernel and PPU side never lands.
