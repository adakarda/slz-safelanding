#!/usr/bin/env bash
# Symlink this package's Gazebo model and world into the PX4 tree.
#
# WHY THIS IS NECESSARY
#
# The plan originally assumed GZ_SIM_RESOURCE_PATH was enough to keep our
# simulation assets outside PX4-Autopilot. Reading
# ROMFS/px4fmu_common/init.d-posix/px4-rc.gzsim shows it is not, for two
# independent reasons:
#
#   1. The script sources build/px4_sitl_default/rootfs/gz_env.sh, which does an
#      unconditional `export PX4_GZ_WORLDS=<px4>/Tools/simulation/gz/worlds`.
#      It is not a `${VAR:=default}`, so exporting PX4_GZ_WORLDS ourselves is
#      overwritten before the world path is used.
#   2. The model is spawned by literal path:
#        <uri>file://${PX4_GZ_MODELS}/${MODEL_NAME}/model.sdf</uri>
#      GZ_SIM_RESOURCE_PATH still resolves the *nested* includes inside that
#      file (x500, model://seg_cam), but not the top-level model itself.
#
# Symlinks rather than copies, so the package stays the single source of truth
# and edits to the SDF take effect without re-running anything.
#
# Safe to re-run. Run it again after a `make clean` or a fresh PX4 checkout.

set -euo pipefail

PX4_DIR="${PX4_DIR:-$HOME/PX4-Autopilot}"
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PX4_MODELS="$PX4_DIR/Tools/simulation/gz/models"
PX4_WORLDS="$PX4_DIR/Tools/simulation/gz/worlds"

if [ ! -d "$PX4_MODELS" ] || [ ! -d "$PX4_WORLDS" ]; then
	echo "ERROR: PX4 gz asset directories not found under $PX4_DIR" >&2
	echo "       Set PX4_DIR if PX4-Autopilot lives somewhere else." >&2
	exit 1
fi

link() {
	local src="$1" dst="$2"
	if [ -e "$dst" ] && [ ! -L "$dst" ]; then
		echo "ERROR: $dst exists and is not a symlink; refusing to replace it." >&2
		exit 1
	fi
	ln -sfn "$src" "$dst"
	echo "  $dst -> $src"
}

echo "Linking eland_sim assets into $PX4_DIR:"
link "$PKG_DIR/models/seg_cam" "$PX4_MODELS/seg_cam"
link "$PKG_DIR/models/x500_seg_cam_down" "$PX4_MODELS/x500_seg_cam_down"
link "$PKG_DIR/worlds/eland_test.sdf" "$PX4_WORLDS/eland_test.sdf"
echo "Done."
