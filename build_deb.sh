#!/usr/bin/env bash
# Build lml_<version>_all.deb from the project root (run: bash build_deb.sh)
set -euo pipefail

PKG="lml"
VERSION="1.0.0~alpha"
MAINTAINER="nether1082 <gitdev@nether1082.pe.kr>"
ROOT="build/${PKG}_${VERSION}"
DEB="build/${PKG}_${VERSION}_all.deb"

FILES="lml_core.py lml_engine.py lml_config.py lml_dataset_loader.py lml_utils.py lml_persona.md"

# Fail early if a source file is missing
for f in $FILES; do
  [ -f "$f" ] || { echo "missing file: $f (run this from the project root)" >&2; exit 1; }
done

rm -rf "$ROOT" "$DEB"
install -d "$ROOT/DEBIAN" "$ROOT/usr/bin"

# Application files (the persona must sit beside lml_engine.py)
for f in $FILES; do
  install -Dm644 "$f" "$ROOT/usr/lib/lml/$f"
done

# Launcher: set LML_PYTHON to use a specific interpreter (e.g. a venv with torch)
cat > "$ROOT/usr/bin/lml" <<'LAUNCHER'
#!/bin/sh
exec "${LML_PYTHON:-python3}" /usr/lib/lml/lml_engine.py "$@"
LAUNCHER
chmod 755 "$ROOT/usr/bin/lml"

SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: ${PKG}
Version: ${VERSION}
Section: science
Priority: optional
Architecture: all
Depends: python3 (>= 3.10)
Recommends: python3-venv, python3-pip
Installed-Size: ${SIZE}
Maintainer: ${MAINTAINER}
Description: Let's Make LLM - AI-assisted model training pipeline
 Alpha release. Requires torch, transformers, datasets, accelerate and
 tokenizers in the Python environment that runs it (see LML_PYTHON).
CONTROL

chmod 755 "$ROOT/DEBIAN"
dpkg-deb --build --root-owner-group "$ROOT" "$DEB"
echo
echo "Built: $DEB"
