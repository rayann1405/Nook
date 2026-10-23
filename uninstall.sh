#!/usr/bin/env bash
# Désinstalle Nook du système utilisateur.
set -euo pipefail

INSTALL_ROOT="${HOME}/.local/share/nook"
BIN="${HOME}/.local/bin/nook"
DESKTOP="${HOME}/.local/share/applications/nook.desktop"
AUTOSTART="${HOME}/.config/autostart/nook.desktop"
ICON="${HOME}/.local/share/icons/hicolor/scalable/apps/nook.svg"
LEGACY_BIN="${HOME}/.local/bin/daemonai"
LEGACY_DESKTOP="${HOME}/.local/share/applications/daemonai.desktop"
LEGACY_AUTOSTART="${HOME}/.config/autostart/daemonai.desktop"
LEGACY_ICON="${HOME}/.local/share/icons/hicolor/scalable/apps/daemonai.svg"

echo "==> Désinstallation de Nook"

rm -f \
  "$BIN" "$DESKTOP" "$AUTOSTART" "$ICON" \
  "$LEGACY_BIN" "$LEGACY_DESKTOP" "$LEGACY_AUTOSTART" "$LEGACY_ICON"
rm -rf "$INSTALL_ROOT"

if command -v gtk-update-icon-cache &>/dev/null; then
  gtk-update-icon-cache --force --ignore-theme-index \
    "${HOME}/.local/share/icons/hicolor"
fi

if command -v update-desktop-database &>/dev/null; then
  update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true
fi

echo "    Fichiers application supprimés."
echo "    Config conservée : ~/.config/nook/ (supprimez-la manuellement si besoin)."
