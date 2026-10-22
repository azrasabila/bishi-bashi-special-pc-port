# Bishi Bashi Special: complete disc-code-bank mapping

## Goal and acceptance boundary

Replace the per-crash mapping of disc-loaded code with reproducible mappings for **every game-dispatch slot in Super and Hyper Bishi Bashi** on the validated user-owned European disc. Success means each slot has a validated disc source, a translated dispatcher entry, and a verified bank-activation rule. Bounded runs must get past the reported racing crash and a representative Hyper call. This is **mapping coverage**, not proof that all 94 slots play correctly, nor completion of the separate Burst the Balloon milestone.

Do not embed or commit disc bytes, extracted assets, or generated C#; do not add an emulator, BIOS, guessed callback bodies, or no-op stubs. Preserve the pinned RecompOne revision and fail visibly rather than silently dropping unresolved slots. Keep changes local to `main` unless the owner requests a push.

## Evidence and assumptions to verify

On the currently validated disc, BISHI1.EXE has 46 contiguous game-call pointers at RAM `0x80057470` and 47 consecutive `(relative sector, byte size)` bank records at EXE file offset `0x4A4E0`. BISHI2.EXE has 48 pointers at `0x8004BFE0` and 49 records at file offset `0x3D330`. The first record in each appears to be shared/startup code, so game slot *i* appears to load bank record *i + 1*. The pointers are not all distinct (45 unique in Super, 46 in Hyper); slots must not be deduplicated.

The inferred Super load base is `0x800C0000` and `CD_DATA1.BIN` starts at disc LBA 189. The observed Pins and Roach code loads match the predicted records and their live RAM bytes matched consecutive disc sectors. The latest racing crash, `0x800C13F0`, is Super slot 4 and predicts relative sector `0x408`, absolute LBA 1221; confirm its live bytes before claiming that mapping. The inferred Hyper load base is `0x80098000` and `CD_DATA2.BIN` starts at LBA 4942. All 48 pointers fit inside their corresponding predicted record sizes, but the Hyper pairing/base still require a live check (including the old `0x80098810` failure).

There are currently only two translated Super table-entry addresses and no translated Hyper table-entry addresses. A static entry is not proof that its bank is active at a call. One Super bank's sector-padded end exceeds the ISO file's declared byte length by 1,692 bytes; the game reads sectors, so truncating bank input to the ISO file size would skip that slot.

## Extraction and compilation

Extend the existing disc-backed `port/tools/recompile.py` path, rather than maintaining 94 hand-written overlay records. Read the two PS-X EXEs and the directory/pointer tables from the validated disc, retaining slot indices and aliases. For each slot, derive the source from the owning CD_DATA file's ISO LBA plus the record's relative sector, derive its length from the record, and seed RecompOne with that slot's exact call address. Use RecompOne's sector/LBA overlay source so the last padded Super sector is available. Keep generated config, bank metadata, function maps, and translations under ignored `.local/probe/`; track only the parser/integration code, tests, and a compact research report.

Validate the disc identity and the expected table shape before generation: executable header/load address, table offsets/counts, representative known records, aligned sizes, strictly increasing in-range relative sectors, physical-sector bounds, call-address alignment, and each slot's address within its candidate bank range. Do not infer functions from zero padding or assert that every byte in a bank is executable: the record can contain data. If RecompOne cannot emit a requested entry from a particular record, identify the slot and stop; do not substitute a different game's function at the same RAM address. Keep the few existing hand-validated bank entries only if they are needed as additional seeds or code/data boundaries, rather than duplicate overlay registrations.

## Activation and overlapping banks

The game's stage loads reuse the same RAM base with different code. Reuse RecompOne's existing LBA-triggered overlay registration and promote-on-write behavior, then check that a new bank deactivates stale dispatcher entries from the previous bank, **including when the incoming bank is smaller**. If the current overlap handling retains old functions, apply the smallest port-specific patch to the pinned runtime and add a regression check. Address aliases in different banks must resolve to the *active* bank, never whichever translated file happened to register last.

## Verification and failure policy

For **all 46 + 48 slots**, generate an ignored machine-readable audit with game, slot, pointer, relative sector, absolute LBA, declared/padded size, generated entry, and activation-test result. Check all source ranges and the requested generated dispatcher entries. Exercise bank-switch activation/invalidation with a small runnable test rather than inferring correctness from compilation. A missing entry, unexpected disc table/layout, ambiguous source, failed activation, or unresolved code boundary is a failing gate with the game and slot number; the report must not mark it mapped.

Run bounded Linux visual checks of the reported Super racing route, a Hyper route, and reachable previously observed Super routes; inspect loaded-bank logs and any next crash. Identify and check Burst the Balloon's route if the stage label is confirmed, but do not call it playable without input/timer/win/loss evidence. A generated or cross-compiled Windows build is not a Windows runtime test. Report untested gameplay, audio, gamepad input, Windows execution, and any blocked slots explicitly.

## Alternatives rejected and stop conditions

Adding one manual overlay per crash repeats the current failure for the other slots and obscures bank switches. Executing missing code in an emulator/JIT fallback violates the static-recompilation constraint. If the table-to-bank relationship or Hyper base fails live validation, stop expanding the catalog and record the conflicting evidence before revising the mapping; do not force the inferred index rule. This design extends the existing static-recompilation port, not the earlier one-minigame playability acceptance gate.
