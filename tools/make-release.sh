#!/bin/zsh
# Build the GitHub release files into ./dist (run from the repository root, on macOS or Linux):
#   W5PL-truSDX-Driver-<version>-macos-linux.zip   the repository files (macOS + Linux + docs; no Windows binaries)
#   Setup_W5PL_truSDX_Driver_beta_x64.exe / _arm64.exe   copied from windows/installer-build/ (build them first on Windows)
#   SHA256SUMS.txt
# Usage: tools/make-release.sh [version]     (default: the DRIVER_VERSION date in trusdx-txrx.py, e.g. beta-2026-11-07)
set -e
ROOT="${0:A:h:h}"; cd "$ROOT"
VER="${1:-$(sed -n 's/^DRIVER_VERSION = "\(beta-[0-9-]*\).*/\1/p' trusdx-txrx.py)}"
[[ -n "$VER" ]] || { echo "version not found"; exit 1; }
NAME="W5PL-truSDX-Driver-$VER"
rm -rf dist; mkdir -p "dist/$NAME"

# repository files without Windows binaries, build output or local environments
rsync -a --exclude dist --exclude .git --exclude ".venv/" --exclude ".arch" --exclude "__pycache__/" --exclude ".DS_Store" \
  --exclude "windows/installer-build/Setup_*.exe" --exclude "windows/installer-build/SetupVSPE_32/" \
  --exclude "windows/installer-build/Setup_vbcable/" --exclude "windows/installer-build/CH341SER.EXE" \
  --exclude "windows/installer-build/arm64-drivers/*" --include "windows/installer-build/arm64-drivers/README.txt" \
  ./ "dist/$NAME/"
cp windows/installer-build/arm64-drivers/README.txt "dist/$NAME/windows/installer-build/arm64-drivers/" 2>/dev/null || true
chmod +x "dist/$NAME"/macOS/*.sh "dist/$NAME/macOS/Start W5PL truSDX Driver.command" "dist/$NAME"/linux/*.sh
(cd dist && zip -qry "$NAME-macos-linux.zip" "$NAME" && rm -rf "$NAME")

for f in windows/installer-build/Setup_W5PL_truSDX_Driver_beta_x64.exe windows/installer-build/Setup_W5PL_truSDX_Driver_beta_arm64.exe; do
  if [[ -f "$f" ]]; then
    [[ "$f" -nt trusdx-txrx.py ]] || echo "WARNING: $f is older than trusdx-txrx.py - rebuild it on Windows first"
    cp "$f" dist/
  else
    echo "NOTE: $f not found (build it with windows/installer-build/build.bat)"
  fi
done
(cd dist && shasum -a 256 *.zip *.exe 2>/dev/null > SHA256SUMS.txt)
echo "Release files in $ROOT/dist:"; ls -l dist; cat dist/SHA256SUMS.txt
