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
