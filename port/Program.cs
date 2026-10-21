using Recompiled;
using RecompOne.Runtime.Config;
using RecompOne.Runtime.Memory;

if (args.Length != 1 || !File.Exists(args[0]) ||
    (Path.GetExtension(args[0]).ToLowerInvariant() is not (".cue" or ".chd")))
{
    Console.Error.WriteLine("Usage: BishiBashi <existing .cue or .chd disc image>");
    return 2;
}

var disc = Path.GetFullPath(args[0]);
Settings.System.DiscPath = disc;
Settings.MarkDirty();
Settings.Save();
var failed = false;
try
{
    RecompOne.Runtime.Runtime.Run(() =>
    {
        try { Entry.Run(new PSMemory(), disc); }
        catch { failed = true; throw; }
    });
}
finally
{
    RecompOne.Runtime.Runtime.Shutdown();
}
return failed ? 3 : 0;
