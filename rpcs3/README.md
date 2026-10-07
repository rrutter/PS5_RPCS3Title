# RPCS3 on the PS5

This title's program is [RPCS3](https://rpcs3.net/), the PlayStation 3 emulator, from my
fork [PS5_RPCS3](https://github.com/KongaTime/PS5_RPCS3). RPCS3's developers make the
emulator; the fork adds what the console needs (`__PROSPERO__` and `PS5` in its sources
and CMake), and its frontend for the console is in `rpcs3/ps5/` there.

**Not working yet.** It builds into a packaged title (`dist/PPSA99200/`, a 60 MB
`eboot.bin`) that starts on the console: on my PS5 RPCS3 initialised the emulator
and stopped cleanly (PS5_RPCS3 0138ef4), and installed Sony's PS3 system software
4.93 from `PS3UPDAT.PUP`, 23 packages in 7.5 s (8a47032). It plays nothing yet: no
PS3 code has run, nothing is drawn.
What is proven, and what is not, is in the commit messages of both repositories.

**Licence.** RPCS3 is GPL-2.0-only and the PS5 platform layer it links is
GPL-3.0-or-later: the two cannot be combined in one program that is shared. Build it
for your own console from source; do not share the builds. No games, firmware or keys
are or will be provided: install the PS3 system software from Sony's own
`PS3UPDAT.PUP`, and use dumps of games you own.

## How the pieces fit

| Piece | Where | What |
| --- | --- | --- |
| RPCS3's emulator core and the PS5 frontend | PS5_RPCS3, beside this repository | `rpcs3_emu`, `rpcs3_ps5` and their libraries |
| `rpcs3/build-rpcs3.sh` | here | cross-builds the fork into `build/rpcs3/` (clang 19 or later) |
| `rpcs3/build-ffmpeg.sh` | here | FFmpeg 8.1.1 for the console (RPCS3's video and audio decoding) |
| `rpcs3/build-libiconv.sh` | here | GNU libiconv 1.18 for the console (`cellL10n`'s text encodings) |
| `rpcs3/build-llvm.sh` | here | LLVM 22.1 (the commit RPCS3 pins) for the console, X86 only, for the PPU and SPU recompilers; its changes in `rpcs3/llvm-patches/` |
| `rpcs3/code-copy.py` | here | `rpcs3-code.bin`, a readable copy of the title's code for RPCS3's fault handler (the console maps code execute-only) |
| `rpcs3/clang-scan-deps-ps5` | here | C++20 module scanning with the console compiler's flags (OpenAL Soft) |
| `rpcs3/rpcs3.cmake` | here | joins `title_main.cpp` to the title and RPCS3's archives to its link |
| `rpcs3/title_main.cpp` | here | the program: reads the controllers, starts RPCS3 |

RPCS3's Vulkan calls go through the foundation's volk to the RADV the title links. Its
files live in `/app0/rpcs3/` (the configuration, `dev_hdd0`), its caches and log in
`/app0/rpcs3/cache/` (`RPCS3.log`). Its warnings and errors reach klog, and each step
of the start, with those warnings and errors, goes to `/app0/rpcs3-trace.txt`, which
FTP can read without klog.

The controllers: players 1 to 4 are the console's controllers. OPTIONS is START, the
touch pad's click is SELECT; the PS button stays the console's.

## Building

With the stack beside this repository (`ps5/tools/bootstrap.sh`), with
`../PS5_PayloadSDK` my fork ([KongaTime/PS5_PayloadSDK](https://github.com/KongaTime/PS5_PayloadSDK):
the SDK pin, `1de8b37`, adds `pathconf` and `sbrk`), and PS5_RPCS3 cloned as `../PS5_RPCS3` with
its submodules (OpenCV's is not needed; LLVM's at depth 1 is enough):

```bash
rpcs3/build-rpcs3.sh rpcs3_ps5 Fusion     # FFmpeg, libiconv and LLVM first (LLVM: hours), then RPCS3
PS5_CLANG=clang-20 ps5/tools/build.sh     # the title, linked with RPCS3, in dist/PPSA99200/
```

Then copy `dist/PPSA99200/` to the console's `/data/homebrew/` (`ps5/tools/deploy.sh`).

`PS5_CLANG` names the clang whose compiler-rt the link takes: the same version the SDK
compiles with (the newest `llvm-config` it finds), or the link stops on a missing
`libclang_rt.builtins-x86_64.a`.

## Running

The PS3 system software first: put Sony's `PS3UPDAT.PUP` (the PS3 update from
PlayStation's own site) in the title's folder, `/data/homebrew/PPSA99200/`, and launch:
RPCS3 installs it into `rpcs3/dev_flash/`, once. Then, with nothing named to boot,
a launch boots the PS3's home menu.

`/app0/rpcs3-boot.txt` (the title's folder on the console) names what to boot, on its
first line: an ELF, or a game's folder (booted through its `EBOOT.BIN`; a disc's
`PKGDIR` packages install at its first boot). Without it the PS3 home menu boots.

Measured on my console (PS5_RPCS3 0cc0383, both recompilers): the Ratchet & Clank
Collection (BCUS98282, a disc folder) booted, ran its menu and its video at full
speed, and started Ratchet & Clank 1 through exitspawn; the game ran at 60 fps,
New Game, saving from the pause menu and loading from the main menu worked
through RPCS3's native save data list. With PS5_RPCS3 607da38 it had sound,
through the console's own output (libSceAudioOut). Each game's first boot
compiles for several minutes with the screen still.

## Not done

- LLVM's first compile is slow, and compiling as code first runs leaves the
  screen still: on my console (PS5_RPCS3 5864031, both recompilers, one compile
  thread) the PS3 home menu drew from 40 s, stood still from 100 s to 270 s while
  24 modules compiled, then ran at 60 fps (3597 RSX flips a minute) for the 40
  minutes it was left. `/app0/rpcs3-interpreter.txt` goes back to the
  interpreters (`ppu` or `spu` alone for one), `/app0/rpcs3-llvm-threads.txt`
  bounds the compile threads, `/app0/rpcs3-llvm-logs.txt` keeps each PPU
  module's IR beside it.
- Installing PSN packages, a game list.
- The console's 16 KiB pages against RPCS3's 4 KiB memory protection, and its
  thread-local storage (emulated on the console: every access is a call).
