using System.Reflection;
using System.Text.Json;
using RecompOne.Runtime.Context;
using RecompOne.Runtime.Dispatch;
using RecompOne.Runtime.Memory;

if (args is ["draw-env"])
{
    var memory = new PSMemory();
    const uint source = 0x80071000u, cache = 0x800605A8u;
    for (uint i = 0; i < 0x5C; i++)
    {
        memory.WriteU8(source + i, (byte)(i + 1));
        memory.WriteU8(cache + i, 0xFF);
    }
    memory.WriteU16(source + 4, 320);
    memory.WriteU16(source + 6, 240);
    memory.WriteU8(source + 0x18, 0); // No background fill; exercise the draw environment only.
    memory.WriteU8(cache + 0x5C, 0xA5);
    var context = new CpuContext { A0 = source };
    Recompiled.BishiBashi_bishi1.PutDrawEnv_bishi1(context, memory);
    for (uint i = 0; i < 0x5C; i++)
        if (memory.ReadU8(cache + i) != memory.ReadU8(source + i))
            throw new Exception($"BISHI1 PutDrawEnv did not cache byte {i:X2}");
    if (memory.ReadU8(cache + 0x5C) != 0xA5 || context.V0 != source)
        throw new Exception("BISHI1 PutDrawEnv changed the cache boundary or return value");
    Console.WriteLine("BISHI1 draw environment cache passed");
}
else if (args is ["fake"])
{
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
}
else if (args is [var auditPath])
{
    var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true,
                                              PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
                                              WriteIndented = true };
    var catalog = JsonSerializer.Deserialize<List<BankRow>>(File.ReadAllText(auditPath), options)!;
    if (catalog.Count != 96 || catalog.Count(b => b.Slot >= 0) != 94)
        throw new Exception("expected all 96 catalog records before activating banks");
    var byName = typeof(Recompiled.Entry).Assembly.GetTypes()
        .Where(t => typeof(IOverlay).IsAssignableFrom(t) && !t.IsAbstract)
        .Select(t => (IOverlay)Activator.CreateInstance(t)!)
        .ToDictionary(o => o.Name);
    Dispatcher.Reset();
    foreach (var active in byName.Values)
        Dispatcher.Register(active.Name, active);
    var map = (Dictionary<uint, Action<CpuContext, IMemory>>)typeof(Dispatcher)
        .GetField("_funcMap", BindingFlags.NonPublic | BindingFlags.Static)!.GetValue(null)!;
    foreach (var bank in catalog.Where(b => b.Slot >= 0))
    {
        var active = byName[bank.Name];
        var entry = Convert.ToUInt32(bank.Entry![2..], 16);
        Dispatcher.LoadByLba(bank.Lba);
        Dispatcher.NotifyWrite(bank.Base & 0x1FFFFFFFu);
        if (!Dispatcher.ActiveNames.Contains(bank.Name) ||
            active.LbaStart != bank.Lba || active.Base != bank.Base ||
            active.Size != bank.Size ||
            Dispatcher.ActiveNames.Count(n => byName.TryGetValue(n, out var o) &&
                                              o.Base == bank.Base) != 1 ||
            !active.Functions.TryGetValue(entry, out var expected) ||
            !map.TryGetValue(entry, out var actual) || actual != expected)
            throw new Exception($"{bank.Game} slot {bank.Slot}: activation failed");
    }
    File.WriteAllText(auditPath, JsonSerializer.Serialize(
        catalog.Select(b => b with { ActivationTest = b.Slot >= 0 ? "passed" : b.ActivationTest }),
        options) + "\n");
    using var audit = JsonDocument.Parse(File.ReadAllText(auditPath));
    if (!audit.RootElement[0].TryGetProperty("game", out _) ||
        !audit.RootElement[0].TryGetProperty("activationTest", out _))
        throw new Exception("activation check changed audit field names");
    Console.WriteLine("bank activation passed for 46 Super + 48 Hyper slots");
}
else
{
    throw new ArgumentException("usage: BankSwitchCheck fake|draw-env|.local/probe/bank-audit.json");
}

sealed class Fake(string name, int lba, uint @base, uint size, uint entry) : IOverlay
{
    public string Name => name;
    public int LbaStart => lba;
    public uint Base => @base;
    public uint Size => size;
    public IReadOnlyDictionary<uint, Action<CpuContext, IMemory>> Functions { get; } =
        new Dictionary<uint, Action<CpuContext, IMemory>> { [entry] = (_, _) => { } };
}

record BankRow(string Game, int Slot, string Name, string? Pointer, string? Entry,
               int RelativeSector, int Lba, int DeclaredSize, int Size,
               int PaddedSize, uint Base, bool GeneratedEntry, string ActivationTest);
