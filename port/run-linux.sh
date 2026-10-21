#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
native="$root/port/bin/Release/net10.0/runtimes/linux-x64/native"
export LD_LIBRARY_PATH="$native${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
dotnet="$root/.local/dotnet/dotnet"
if [ ! -x "$dotnet" ]; then dotnet=dotnet; fi
exec "$dotnet" "$root/port/bin/Release/net10.0/BishiBashi.dll" "$@"
