# THE QUEST — Heavenly Sword, NATIVE on a jailbroken PS5 (no interpreter)

> **The goal:** Heavenly Sword launches into GAMEPLAY on the PS5 with the SPU **recompiler** (LLVM/asmjit), not the interpreter. Native speed. No Linux. No hypervisor. Our 9.60 box can't take ps5-linux, so this is the only road — and we're the only ones on it (we hold the only forks of both KongaTime repos; nobody else is doing this).

---

## The machine (how to build + test, so none of this dies)

- **Build host:** WSL2 Ubuntu 24.04 (`wsl -d Ubuntu -- bash -lc "..."` from Windows). Build root `~/ps5-rpcs3/`. `rechain.sh` = rebuild RPCS3 core + title (~20 min). Logs `~/ps5-rpcs3/s{N}-*.log`.
- **Our forks (branch `lab`, remote `mine`; origin = KongaTime, READ-ONLY):** `github.com/rrutter/PS5_RPCS3` + `github.com/rrutter/PS5_RPCS3Title`. Commit as Russ <arius_storm@yahoo.com>. GitHub pushes intermittently 500/timeout — retry, they land.
- **Deploy:** copy `dist/PPSA99200/{eboot.bin,rpcs3-code.bin}` → `G:\homebrew\PPSA99200\` (delete-then-copy + sha256 readback verify — exFAT/FTP corrupt silently). Title lives on the USB (G: doctrine — nothing installs internally).
- **The flight card:** G: → PS5 → launch PPSA99200 → HS → new game → FMV → the transition. Freeze = wait 60s → power off → G: home → read `rpcs3-trace.txt` + `rpcs3/cache/RPCS3.log` on the USB.
- **Runtime arming:** L3+R3 toggles the mega ring (the flood) live — arm only at the transition (the boot watchdog `*** Timeout Call` fires if the flood runs during boot/load).
- **The lab's instruments** (all in the fork, flag-gated in `/app0/`): status line (PPU/SPU threads + SPURS struct dump), wedge/kpark analyzers (register+LS dumps on park), the mega ring (every channel/MFC/atomic op), block trails, the LS lifter (`spu-ls-dump.bin`), the hitch watch, pad IMU telemetry.
- **PC-side:** `spu_disasm.py` (PS3emu/) disassembles SPU LS dumps against the fork's own `SPUOpcodes.h`.

---

## THE DISEASE (the whole point)

**Under any SPU recompiler, the SPURS1 kernel never completes a scheduling cycle.** Boots → menus → FMV (all fine, fast — the menu at 60fps is FMOD alone, no SPURS) → the first heavy SPURS need (the level load-in / the Super Saiyan moment) → **hard freeze**. The interpreter plays straight through (slowly).

### The anatomy (all hardware-proven on console)

- HS uses **SPURS1** (the 16-workload kernel, `flags 00`). KongaTime's entire test suite (R&C Collection, GTA IV, X-Men) is **SPURS2** — which *works* under their JIT. We're the first to ever run SPURS1 on this port.
- The wedge state (deterministic): 5 SPURS kernels park (at `0x818` entry / `0x13xx` poll / `0x26bc` retry — varies by build), mailboxes empty, `spuIdling` stays 0, `main_thread` spins on an empty completed-jobs list (`0xcae100`/`0xd242ac`). The struct fills correctly (workloads RUNNABLE, ready counts set) while nobody dispatches.
- The kernel's healthy cycle (from the interpreter): poll → dispatch → **return to the kernel image** → repeat. Under JIT the return/dispatch never happens.
- **The gap:** the kernel's scheduling core (subscribe + ready-count read + idle-mark + event-wait) lives at LS **`0xcc8–0x1230`** — and it is **never in the JITs' built-function list** (the build log jumps `0xcc8 → 0x1230`) and never entered at runtime. The interrupt/computed-entry path the analysis can't link.
- We disassembled the kernel out of live console memory (`spu-ls-dump.bin` + `spu_disasm.py`) and read the scheduler: the poll loop at `0x12f0–0x1358` = GETLLAR(+0x80 lock line) → extract a state byte (ROTQBYI/SHUFB) → PUTLLC claim (r12=0xb4) → `BRNZ $r102, 0x12f0` retry. The event-wait at `0x11a8` = `RDCH ch0` → `WRCH ch2` (EventAck) → `HBRR`.

### Acquitted by evidence (do NOT re-chase these)

| Theory | Verdict | Proof |
|---|---|---|
| MFC param caching (LSA→EAL mixup) | **REAL but fixed** (the bypass) | ring: `mfc d0 2d80 2d80` → clean after bypass |
| GETLLAR same-line fast-cache staleness | ❌ acquitted | `nogetllarcache` probe, identical wedge |
| PUTLLC16 fusion | ❌ acquitted | reservations=true (fusion off) wedges same |
| LS load hoisting (the clanker's theory) | ❌ acquitted | `spu-volatile-ls` probe, identical wedge |
| Every config lever (wake delays, reservations, DMA accuracy, block size, thread counts) | ❌ all dead | the full matrix, flown |
| Thread priorities | ❌ acquitted | merged their fix, same wedge |
| Memory coherence (double-map) | ❌ acquitted | dual-view status reads agree |
| The split (kernels interpret, tasks JIT) | ❌ backfired twice | the fork's SPURS init is too delicate to gate; reverted |

### Standing suspects (the last floor)

- The JITs' **shared analysis/runtime** never links the scheduling core (the gap). Both engines identically → not an optimizer bug (asmjit has none) → it's the shared analysis or the runtime's block/escape cadence.
- The kernel's poll loop never sees a reason to enter the gap: it polls `wklState` (+0x80) and the ready-count read (+0x00) lives in the gap it never reaches. Chicken-and-egg in the control flow.

---

## What we FIXED along the way (the keepers)

- **The console's clock:** `get_tsc_freq()` returned **0** on Orbis (no Linux sysfs; the APU isn't branded "Ryzen" so the fallback bailed). Every TSC-calibrated wait/timing path ran blind. **Fix landed** (let the console reach the CLOCK_MONOTONIC calibration) — banner now shows `TSC: 1.596GHz`. (commit `80ed26699`)
- **SIXAXIS/gyro:** full pipeline (title `platform.c` reads the 120B sample's IMU floats → frontend feeds `m_sensors`) — Night Attack tilt-aim verified on hardware (roll = `-gyro_z`, accel x flipped).
- **NullAudioBackend** layout-at-open fix; the fatal stack-walk forensics; the param-staging bypass for JIT MFC.
- Merged KongaTime's Oct-8 batch (frame gen, SPU poll counters, pause menu, sound via `607da383e`).

## The upstream channel

- KongaTime's issues are disabled on PS5_RPCS3 but **open on PS5_RPCS3Title** — **Issue #1** is our thread (the freeze anatomy + field reports, AI-assistance disclosed). The lean SPURS1 report is filed there (the full anatomy above, in two paragraphs).
- KongaTime runs Claude agents hardware-in-the-loop, committing daily on the SPU/SPURS layer (their overnight before last: GETLLAR poll counters — they're chasing the same ghost on GTA IV).
- **Doctrine:** we don't wait on them; we fix what we find. The report is a courtesy/force-multiplier. If it's fundamentally theirs, a PR goes up lean + human + zero AI-isms.

## The next concrete moves (in order)

1. **Session-start rule:** `git fetch origin main` in both WSL repos, read the new commits, merge if they touched SPU/SPURS/threading (25-min cycle).
2. **Read the JIT's emitted x86 for the kernel's poll loop** — stop inferring, see the generated code. Needs the fork's SPU-LLVM IR/object dump path figured out (XOM wrinkle: the console's code is execute-only, so dump at *compile* time to the cache dir, like the fork's `rpcs3-llvm-logs.txt` does for PPU). The diverging instruction gets *named*.
3. If a fix lands (ours): verify on hardware, then the lean PR. If theirs lands first: merge + retest (25-min cycle).

## The saga's shape (for the record)

Boots ✅ → fw installs ✅ → menus/FMV at 60fps ✅ → audio works ✅ → gyro aims ✅ → fights play on the interpreter ✅ → **the wedge: SPURS1 + JIT = no dispatch** ← the last wall.

We're 10+ rounds in and the bug is cornered in one LS region and one missing edge. It doesn't know it's beat yet.
