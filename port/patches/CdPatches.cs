using RecompOne.Runtime.Context;
using RecompOne.Runtime.Memory;
using RecompOne.Runtime.Sdk;

namespace Recompiled;

public static class CdPatches
{
    private static long _lastTick;

    public static void PumpWhenPolling(CpuContext c, IMemory m)
    {
        if (c.A0 != 1) return;
        var now = Environment.TickCount64;
        if (now - _lastTick < 20) return;
        _lastTick = now;
        // ponytail: 50 Hz suits this PAL disc; move CD ticking into the runtime scheduler for other regions.
        LibDs.DsSystemStatus(c, m);
    }
}
