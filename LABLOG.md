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

## run32 instrument: SPU DMA spy (spurs-dma-trace.txt + SPU:Trace) - reads into the SPURS struct logged with offset+bytes; verdict pending.

## run32 RESULT: THE DISEASE MOVED - allocation WORKS (w1 rc5 ct 5>0>5, idle 0); kernels WOKE (pcs 0x1d0xx dispatch region, off the 0x11a8 idle loop) but jobs never complete. Invisible enemies = SPU-skinned models never computed. Next: spy watches do_list_transfer (job-ELF loading door); SPU:Trace removed (flooded log to cap).

## THE VARIANCE DISCOVERY (runs 32/33 + field report)

Story: identical builds die at three different depths. Run32: kernels woke, workload
allocated all 5 SPUs, froze mid-job. Run33: kernels never woke, no allocation, earlier
freeze. Field run: enemies rendered AND Saiyan achieved before freezing. => the SPURS
kick/wake is a RACE the console sometimes wins. Races have levers; variance demands
repetition, so each lever gets 2-3 flights for signal.

Technical:
- run32 freeze-state: kernels at 0x1d0xx (dispatch region), w1 rc 5+0 ct 5>0>5, idle 0
- run33 freeze-state: kernels at 0x11a8 (idle loop), w1 never allocated (ct 0)
- Series A: SPU Wake-Up Delay 400us (was 200). Series B next: Driver Wake-Up Delay.
  Series C: Max SPURS Threads 6->4. Two to three runs each before judgment.

## Protocol correction: the observer effect

Story: at full trace we ran ~1 frame per 5s — the logging overhead warps the exact
timing race we are measuring. Lever series now run LIGHT: status-line instruments
only (they cost ~nothing), trace channels OFF. Heavy trace comes back only when a
specific story needs telling.

Technical:
- config Log section reset to {} for the series (flight A1 froze never-woke variant
  under full trace; that timing may be unrepresentative)
- status printer + SPURS dump + mailbox counters stay on (passive reads only)

## 🏆 THE WALL BROKEN (Series A, flight 2) — v0.1-lab

Story: Saiyan achieved, and the dreaded transition PASSED — the next FMV played, the
main menu came up, and Chapter 1 went FIGHT-COMPLETE, FMV, FIGHT-COMPLETE, chapter
done. Two full fights at ~15fps on the interpreter. The only standing wall: the
Night Attack crossbow section needs SIXAXIS tilt and the frontend does not wire the
DualSense gyros through.

Technical:
- what landed it: variance + cumulative levers + light instrumentation (the race wins
  sometimes now); single-cause attribution is honestly impossible - the honest record
- standing config: interpreter both, MSAA off, audio Null, boot music off,
  Accurate SPU Reservations off, Accurate Cache Line Stores on, PPU Threads 1,
  SPU Wake-Up Delay 400us, Accurate SPU DMA on
- next blocker: gyro/tilt data path (ps5 pad sample -> cellPad motion bytes)

## The gyro pipeline (lab) - Night Attack unblocked

Story: the frontend reported the sixaxis sensors at rest forever; the crossbow bolt
never steered. The console's 120-byte pad sample carried the IMU all along (accel at
0x1c, gyro at 0x28, floats). Now wired end to end; the pad declares sensor mode.

Technical:
- platform.c reads the sample IMU floats; the shared pad struct carries them
- ps5_pad_handler maps them to the 4 sixaxis sensors (dualsense handler formula)
- field test 1: worked, but left/right inverted; yaw-flip: no change (wrong channel)
- field test 2: flip accel_x AND roll (gyro_z); pad-trace.txt telemetry logs the raw
  IMU at 1 Hz so a tilt names any wrong axis empirically

## 🏹 v0.2-lab — the SIXAXIS milestone

Story: tilt steers the bolt. Night Attack is playable. The crossbow tracks with the
hands - verified on console by the pilot himself. And because the next war is
performance, the on-screen FPS counter is now armed: RPCS3's Performance Overlay
renders through the RSX overlay system (which upstream just wired for the console).

Technical:
- gyro mapping: accel x/y/z via dualsense formula; G sensor = -gyro_z (roll rate),
  field-tested and confirmed; the pad declares CELL_PAD_CAPABILITY_SENSOR_MODE
- config: Performance Overlay Enabled + framerate/frametime graphs on
- honesty note: fps reads via flips; the overlay renders via RSX overlays (if the
  overlay fails to draw on this build, the trace already logs flips/5s as fallback)

## ASMJIT flight series (run36-37)

Story: the ASMJIT flag turns menus from 5-10fps to a LOCKED 60fps - the SPU JIT
road works on-console. But a deterministic deadlock appears at the menu->game
load transition: main_thread parks in sys_mutex_lock at 0xd242ac forever while
the SPURS kernels sit at their asmjit wait point (0x26bc) and workload 0 shows
ALL tasks completed (rc 0+7). The SPU work finishes; the completion signal to
the PPU side never lands. Identical state both runs = not a race, a broken
handshake. Levers A/B (wake-up delays 0) armed by the fork's own config
normalization; C (PPU Threads 2) made no difference. Next cell: PPU Threads 1.

Technical:
- symptom: deterministic freeze, flips frozen, heap stable, zero fatals
- evidence: mb w0/c0, sig 0000/0000, w0{s2 rc 0+7 ct 0>0>5} - work done, no wake
- reported upstream as a comment on issue #1

## 🏆 v0.3-lab — the merge, the music, and the heartbeat on tape

Story: merged KongaTime''s entire 40-commit day into the lab (their thread-priority
fix, executable-memory fix, SPU-LLVM collision work, file census, launcher - and
SOUND: the PS5''s own audio output; HS''s menu theme plays now). The field test
that followed: the interpreter build ran past the old freeze zone without a single
wedge. And the full-spectrum DMA spy finally captured the healthy SPURS heartbeat
we will diff every JIT run against: the kernels mark life via PUTLLC atomics on
the instance struct''s two cache lines, 82 times on the reference tape, idle 31
throughout. The bug is officially out of places to hide.

Technical:
- merge: PS5_RPCS3 origin/main @fe4968bd9 + title origin/main @1666d2f into lab
  (one conflict: status trace keeps our SPU/SPURS sections AND their open-files watch)
- audio: upstream 607da383e (console output) + a9a35e152 (audio thread priority)
  carried by the merge; CellAudio provider live with default device
- dma spy v2: notice-level (trace is filtered), self-healing 1s flag re-check,
  +/-4KB window, WRITE side + PUTLLUC + PUTLLC + list elements
- GOLD reference (gold-interp-dma/): healthy = PUTLLC x82 @5631a300/+0x80 from
  kernel PCs 0x011e4/0x01350/0x01f38, plus 512B workload reads at +2816; idle 31
- the JIT wedge signature to kill: idle stays 0 -> SPURS stops dispatching ->
  the game spins on an empty completed-jobs list at guest 0xd242ac

## Strategy session (pre-leg-B): the suspects re-ranked

Story: before burning a flight on the PUTLLC theory, we read both JITs'' atomic
emission - and ASMJIT doesn''t inline atomics AT ALL (it shares the interpreter''s
C++ path). Yet ASMJIT wedged identically to LLVM (which does inline). The atomics
are mostly acquitted without spending a console trip. New prime suspect: the
pump cadence - the interpreter''s loop does constant bookkeeping (MFC completion,
event processing, flag checks) between instructions; JIT''d code runs long native
stretches without it. If the kernel''s idle-settling needs that machinery pumped,
JIT starves it -> idle stays 0 -> SPURS stops dispatching -> the game spins.
Fits every symptom: JIT-family-wide, deterministic, immune to every config lever.

Technical:
- suspect ranking: (1) JIT-starves-the-pump, (2) escape-path boundary miss
  (kernels park at 0x26bc vs interpreter''s 0x11a8), (3) atomics (weakened)
- leg B tape discriminates all three: PUTLLC spam = reservations; heartbeat
  absent = kernel never reaches scheduling; heartbeat present + idle 0 = bad data
- standing rule added: check KongaTime''s repos at session start (they commit on
  this layer daily; the merge cycle is proven ~25 min)
- horizon honesty: SPU-JIT + PPU-interp is a midpoint; 30fps needs their PPU-LLVM
  (README today: the home menu runs on it). The interpreter build is the playable
  baseline meanwhile - stable, audio in, past the old freeze zone

## THE CONVICTION (leg B tape vs gold): the task that never ends

Story: the diff landed clean. Healthy interpreter: 82 PUTLLC atomics from all five
kernels across both SPURS struct lines, plus workload-info DMA reads. Wedged
SPU-LLVM: TWO atomics (kernel3 alone, +0x80 only), the spuIdling line (+0x00)
NEVER touched, zero reads. And the park address gave it away: 0x26bc is past the
2KB kernel image - the SPUs are stuck INSIDE a guest TASK (workload code at
0xA00+), not the kernel idle loop. The task spins on its MFC tag completion; the
machinery that completes DMA (do_mfc) is pumped by the interpreter loop, which a
tight JIT''d spin never visits. The task never finishes -> kernel never idles ->
SPURS stops dispatching -> the game''s completed-jobs list stays empty -> main
spins at 0xd242ac. Works slow, starves fast, deterministic, config-immune.

Technical:
- gold: PUTLLC x82 (PCs 0x011e4/0x01350/0x01f38), reads @+2816, idle 31
- llvm: PUTLLC x2 (kernel3, +0x80, 0:00:10), idle 0, park 0x26bc (task region)
- kernel images: 0x800 bytes at LS 0x0; workloads load at 0xA00+
- fix direction: find where the fork''s JIT lost the do_mfc pump (upstream PC
  RPCS3 survives tight tag-spins - the periodic escape/check_state must exist
  there; the fork''s SPUThread changes are the diff surface)

## The LSA-in-EAL mixup (the wedge, named at last)

Story: the ring of truth + the gold ring, diffed. Healthy kernels write
MFC_LSA=0x2d80 (a LOCAL-store buffer address) as a GETLLAR parameter - normal.
Under SPU-LLVM the executed GETLLAR carried eal=0x2d80: the local-store address
sitting in the EFFECTIVE-address slot. The atomic fires at an unmapped low page,
never completes, RdAtomicStat never answers, the kernel spins at 0x26bc, idle
never marks, SPURS stops dispatching, the game wedges at 0xd242ac. Deterministic,
JIT-wide, immune to every config lever - because it is a JIT parameter-staging
bug, not a semantic one.

Technical:
- gold ring: wrch 10 2d80 (MFC_LSA write) at pc 0x1860/0x192c; zero low-EA atomics
- wedged ring: mfc d0 2d80 (GETLLAR with eal=LSA) then silence; the +0x00 line
  (spuIdling) never touched under JIT
- doctrine update: WE fix what we find (self-reliance); upstream PRs only for
  fundamentally-theirs bugs, lean and human
- next: asmjit ring (shared bug or LLVM-specific), then read the JITs'' MFC
  fixed-register flush for the miswire
