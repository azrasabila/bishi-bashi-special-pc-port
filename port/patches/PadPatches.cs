using RecompOne.Runtime.Context;
using RecompOne.Runtime.Memory;

namespace Recompiled;

public static class PadPatches
{
    public static void InitDirect(CpuContext c, IMemory m) => RecompOne.Runtime.Sdk.LibPad.PadInitDirect(c, m);
}
