using RecompOne.Runtime.Context;
using RecompOne.Runtime.Dispatch;
using RecompOne.Runtime.Memory;

if (args is not ["fake"])
    throw new ArgumentException("usage: BankSwitchCheck fake");

var big = new Fake("big", 200, 0x800C0000u, 0x5000u, 0x800C4000u);
var small = new Fake("small", 201, 0x800C0000u, 0x3000u, 0x800C0100u);
Dispatcher.Reset();
Dispatcher.Register("big", big);
Dispatcher.Register("small", small);
Dispatcher.Load("big");
Dispatcher.LoadByLba(small.LbaStart);
Dispatcher.NotifyWrite(0x000C0000);
if (Dispatcher.ActiveNames.Contains("big") || !Dispatcher.ActiveNames.Contains("small") ||
    !Dispatcher.CanCall(0x800C0100) || Dispatcher.CanCall(0x800C4000))
    throw new Exception("stale code bank");

var left = new Fake("left", 202, 0x800D0000u, 0x3000u, 0x800D0100u);
var right = new Fake("right", 203, 0x800D2000u, 0x3000u, 0x800D2100u);
Dispatcher.Register("left", left);
Dispatcher.Register("right", right);
Dispatcher.Load("left");
Dispatcher.Load("right");
if (!Dispatcher.ActiveNames.Contains("left") || !Dispatcher.ActiveNames.Contains("right"))
    throw new Exception("different-base partial overlap must be retained");

var main = new Fake("main-test", -1, 0u, 0u, 0x80011000u);
var bishi1 = new Fake("bishi1-test", 24, 0x80010000u, 0x52800u, 0x800189B8u);
var bishi2 = new Fake("bishi2-test", 4809, 0x80010000u, 0x42800u, 0x8001ED24u);
Dispatcher.Reset();
foreach (var overlay in new[] { main, bishi1, bishi2 })
    Dispatcher.Register(overlay.Name, overlay);
Dispatcher.Load(main.Name);
Dispatcher.Load(bishi1.Name);
Dispatcher.Load(bishi2.Name);
if (!Dispatcher.ActiveNames.Contains(main.Name) ||
    !Dispatcher.ActiveNames.Contains(bishi2.Name) ||
    Dispatcher.ActiveNames.Contains(bishi1.Name))
    throw new Exception("main/EXE bank transition failed");
Console.WriteLine("fake bank switch passed");

sealed class Fake(string name, int lba, uint @base, uint size, uint entry) : IOverlay
{
    public string Name => name;
    public int LbaStart => lba;
    public uint Base => @base;
    public uint Size => size;
    public IReadOnlyDictionary<uint, Action<CpuContext, IMemory>> Functions { get; } =
        new Dictionary<uint, Action<CpuContext, IMemory>> { [entry] = (_, _) => { } };
}
