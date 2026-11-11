# PLAN

G2 M4: Unity front-end for the Rust kernel (owner's request 2026-11-11, "one thing at a time"). Branch
`feat/g2-m4-unity` off `3733cd1`. Two small PRs: A (Rust C ABI, verified in CI) then B (Unity project, local only).
Unity version: 6000.5.6f1 (owner's choice 2026-11-11).

## Checklist
1. [x] Scope and plan (this file); editor version chosen
2. [ ] A: `engine-rs/src/ffi.rs` C ABI: handle, load from bytes, free, step, sizes, hash, render, last error
3. [ ] A: light computed at load (as Python); render ported from `render.py`, compared with Python on the golden save
4. [ ] A: `tests/ffi.rs` (golden hashes through the ABI, bad input, null handle, short buffer, poisoned handle)
5. [ ] A: docs (G2_PLAN, ARCHITECTURE, CHANGELOG, TEST.md), PR
6. [ ] B: `unity/` project (6000.5), P/Invoke wrapper, world texture, play/pause/speed, DLL + save copied by script
7. [ ] B: EditMode test in batchmode: golden hashes through P/Invoke; on-screen check by the owner
8. [ ] B: docs (USER_MANUAL, DEVELOPER_GUIDE, G2_PLAN, CHANGELOG), PR

## A: C ABI (decisions)
- Only what G2_PLAN allows: save loading, `step`, read-only views. Never `World::from_parts` or field writes.
- Load takes bytes + length (C# reads the file): no path encoding across the boundary; size cap as `load_world`.
- Every entry point is wrapped in `catch_unwind` and checks null pointers and buffer lengths. A panic inside
  `step` poisons the handle (the world may be half-updated): later calls on it fail with an error.
- Errors: functions return a status code; `ws_last_error` copies the message of the last failure on this thread.
- `ws_abi_version()` lets the front-end refuse a stale DLL.
- Light: the Rust loader computes the light at load like `persistence.py` (`update_light` at `now = step_count`).
  Light is not in the state hash, so `hashes.csv` stays unchanged.
- Render: `render.py` in Rust, RGBA8, row 0 = surface (the front-end flips rows). Python computes in float32
  and truncates; Rust mirrors the float32 order of operations, and the test allows a difference of at most 1
  per channel (rounding of float32 expression order is not guaranteed equal), reporting the share of exact pixels.

## B: Unity project (decisions)
- `unity/` in this repository (ADR-0008). `Library/`, `Temp/`, `Obj/`, `Logs/`, `UserSettings/`, `*.csproj`,
  `*.sln` git-ignored; `.meta` files committed.
- The native DLL and a sample save are copied into the project by a script (git-ignored), never committed.
- The kernel cannot create a world yet (generation is M5): Unity loads a v8 save.
- Not in CI (Unity needs a licence); stated in the docs.
