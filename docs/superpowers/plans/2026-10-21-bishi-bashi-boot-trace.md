# Bishi Bashi Boot Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal Linux host for the already-generated RecompOne code and record one bounded boot attempt, without claiming playable gameplay.

**Architecture:** The user's disc remains ignored and is passed explicitly to a tiny .NET host. The generated C# and RecompOne checkout remain ignored local build inputs. A bounded Xvfb run provides one boot-path observation; unknown module loading and unsupported calls become evidence for the next plan, not speculative patches.

**Tech Stack:** .NET 10.0.402 in `.local/dotnet/`; pinned RecompOne `4259b76fa923d1e607a6b3379ef908cb5d5b9354`; Python 3 `unittest`; Xvfb and `timeout` on this Linux host.

**Spec:** `docs/superpowers/specs/2026-10-21-bishi-bashi-static-recompilation-design.md`

## Global Constraints

- The ultimate target is Windows and Linux native programs; this plan validates only an initial Linux boot attempt, **not** a finished executable or Burst the Balloon gameplay.
- No copyrighted disc data or generated translated C# is committed. Do not push changes without the user's separate request.
- The input must be the validated `Bishi Bashi Special.cue` and companion BIN (SHA-256 `76c717d7ca2a99b4a66e692889f277fef8db80761849c11c15c85d7f30436872`).
- REA has no connected native provider for PS-X EXE; don't label RecompOne findings as REA Evidence.
- Stop at the first unverified raw code load, absent entry, or SDK/runtime failure; record exact address, file and call path rather than guessing a patch.

## Review Focus

- Missing disc argument must not initialize runtime and hang waiting for media (Task 1).
- Wrong file extension or missing CUE must fail visibly before runtime initialization (Task 1).
- Stale/untracked generated files must not be mistaken for reproducible build inputs (Task 1).
- A timed-out process must be distinguished from an exception and a successful boot (Task 2).
- A visible title/menu alone must not be recorded as Burst the Balloon working (Task 2).

---

## File responsibilities

- Create `port/BishiBashi.csproj`: small host referencing pinned local RecompOne runtime and ignored generated C#.
- Create `port/Program.cs`: validate one CLI disc argument and invoke `Recompiled.Entry.Run`.
- Create `tests/test_port_cli.py`: exercise missing/wrong/missing-file paths on the built binary without launching the runtime.
- Modify `.gitignore`: ignore host binaries/intermediate output (`bin/`, `obj/`) and all local build inputs already under `.local/`.
- Modify `docs/research/disc-probe.md`: record exact build and bounded boot observation, with unresolved paths.

### Task 1: Build an explicit-disc host

**Files:** Create `port/BishiBashi.csproj`, `port/Program.cs`, `tests/test_port_cli.py`; modify `.gitignore`.

**Interfaces:** `port/BishiBashi.csproj` compiles generated files from `../.local/probe/generated/*.cs` and references `../.local/RecompOne/RecompOne.Runtime/RecompOne.Runtime.csproj`; `port/Program.cs` accepts exactly one existing `.cue` or `.chd` path and calls `Entry.Run(new PSMemory(), path)`, returning nonzero for invalid input.

- [ ] **Step 1: RED — create `tests/test_port_cli.py`.** This checks argument validation *before* runtime initialization:

```python
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOTNET = ROOT / '.local/dotnet/dotnet'
APP = ROOT / 'port/bin/Release/net10.0/BishiBashi.dll'


class PortCliTest(unittest.TestCase):
    def test_invalid_inputs_fail_without_waiting_for_disc(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = Path(tmp) / 'existing.txt'
            text.write_text('not a disc')
            for args in ([], [str(Path(tmp) / 'missing.cue')], [str(text)]):
                with self.subTest(args=args):
                    result = subprocess.run([str(DOTNET), str(APP), *args], capture_output=True,
                                            text=True, timeout=5,
                                            env={**os.environ, 'DOTNET_ROOT': str(DOTNET.parent)})
                    self.assertEqual(result.returncode, 2)
                    self.assertIn('Usage: BishiBashi', result.stderr)
```

The test must fail initially because the host assembly does not exist.
- [ ] **Step 2: Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_port_cli.py -v`; expect failure because the host assembly does not exist.**
- [ ] **Step 3: GREEN — create this minimal project and entry point:**

```xml
<!-- port/BishiBashi.csproj -->
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <AssemblyName>BishiBashi</AssemblyName>
  </PropertyGroup>
  <ItemGroup>
    <ProjectReference Include="../.local/RecompOne/RecompOne.Runtime/RecompOne.Runtime.csproj" />
    <Compile Include="../.local/probe/generated/*.cs" Link="Generated/%(Filename)%(Extension)" />
  </ItemGroup>
</Project>
```

```csharp
// port/Program.cs
using Recompiled;
using RecompOne.Runtime.Memory;

if (args.Length != 1 || !File.Exists(args[0]) ||
    (Path.GetExtension(args[0]).ToLowerInvariant() is not (".cue" or ".chd")))
{
    Console.Error.WriteLine("Usage: BishiBashi <existing .cue or .chd disc image>");
    return 2;
}

Entry.Run(new PSMemory(), Path.GetFullPath(args[0]));
return 0;
```

Append `bin/` and `obj/` to `.gitignore`. Before building, check all five expected files exist in `.local/probe/generated/` (`Entry.cs`, `main.cs`, `bishi1.cs`, `bishi2.cs`, `Stubs.cs`); if any is absent, rerun the pinned recompiler using the already recorded config rather than building against stale output. With the local SDK on PATH, run `dotnet build port/BishiBashi.csproj -c Release --nologo`. If generated C# and runtime APIs do not compile together, record exact compiler errors; repair only demonstrable name/API mismatches, in the smallest patch, after a failing check.
- [ ] **Step 4: Run the CLI test and then the full suite:** `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`. Expect CLI argument failures to be quick and deterministic, and existing disc preflight tests to remain green.
- [ ] **Step 5: Verify staged files explicitly, then commit host, tests, and ignore rules; never add `.local/`, the BIN or CUE.**

### Task 2: Attempt a bounded boot and report what actually happens

**Files:** Modify `docs/research/disc-probe.md` only; raw logs stay under `.local/probe/`.

**Interfaces:** Input: Task 1 host and the validated CUE. Output: boot log, exit/timeout status, and a report that distinguishes proven entry from observed visuals, unresolved calls and unknowns.

- [ ] **Step 1: Run a bounded headless smoke under Xvfb and retain the actual exit status:**

```bash
DOTNET_ROOT="$PWD/.local/dotnet" PATH="$PWD/.local/dotnet:$PATH" \
  timeout 15s xvfb-run -a .local/dotnet/dotnet port/bin/Release/net10.0/BishiBashi.dll \
  "$PWD/Bishi Bashi Special.cue" > .local/probe/boot.log 2>&1
printf 'boot exit=%s\n' "$?"
```

Exit 124 means timeout (possibly normal for an interactive program), zero means process exited, another code means an error. None proves the title rendered: obtain a screenshot or runtime capture before claiming visible boot. No synthetic inputs are in this plan.
- [ ] **Step 2: Read `.local/probe/boot.log` and any runtime-created diagnostic file.** Record the earliest observable transition or failure with exact address, file, error, and whether the window was captured. If the runtime launches normally but provides no bounded capture or reaches no menu in 15 seconds, say only that launch was observed; do not infer gameplay.
- [ ] **Step 3: Update `docs/research/disc-probe.md` with the command, exit code, capture/log facts, and next concrete investigation.** If missing `CD_DATA*.BIN` modules or unmapped calls block boot, next work is recovering their actual load mappings, not adding a guessed base address. Re-run full CLI/preflight tests and `git diff --check`, then commit the report only (no binary/log data).

## Completion and handoff

This plan ends with a tested host and an honest bounded boot report, whether the runtime reaches the menu or not. Only after observing the loader/code path should a subsequent plan target Burst the Balloon or Windows publication. A successful RecompOne translation is not a runnable or verified game.
