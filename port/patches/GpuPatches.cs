using RecompOne.Runtime.Context;
using RecompOne.Runtime.Memory;

namespace Recompiled;

public static class GpuPatches
{
    // BISHI1.EXE PutDrawEnv copies its 0x5C-byte argument to this GetDrawEnv cache.
    public static void CacheDrawEnv(CpuContext c, IMemory m)
    {
        for (uint i = 0; i < 0x5C; i++)
            m.WriteU8(0x800605A8u + i, m.ReadU8(c.A0 + i));
    }
}
