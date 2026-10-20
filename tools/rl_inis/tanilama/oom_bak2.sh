#!/bin/bash
journalctl --since "14:56" --until "14:59" --no-pager 2>/dev/null | grep -v -E 'audit|snapd' | head -40
echo "== oomd"; systemctl is-active systemd-oomd 2>/dev/null
dmesg | awk '/4460/' | grep -E 'python|bash' | head -20
