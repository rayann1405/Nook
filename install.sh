#!/usr/bin/env bash
# Installe Nook comme application de bureau Ubuntu (sans terminal).
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="${HOME}/.local/share/nook"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
CONFIG_DIR="${HOME}/.config/nook"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
AUTOSTART_DIR="${HOME}/.config/autostart"

echo "==> Installation de Nook"

# Dépendances système minimales
MISSING=()
for pkg in python3 python3-venv python3-pip libxcb-cursor0 libxkbcommon-x11-0; do
  if ! dpkg -s "$pkg" &>/dev/null; then
    MISSING+=("$pkg")
  fi
done
if ((${#MISSING[@]})); then
  echo "    Paquets manquants : ${MISSING[*]}"
  echo "    Exécutez : sudo apt install -y python3 python3-venv python3-pip \\"
  echo "               libxcb-cursor0 libxkbcommon-x11-0 libegl1 python3-xlib"
fi

mkdir -p "$INSTALL_ROOT" "$BIN_DIR" "$DESKTOP_DIR" "$CONFIG_DIR" "$ICON_DIR"

echo "    Copie des fichiers vers $INSTALL_ROOT"
rsync -a --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.git' \
  "$SOURCE_DIR/nook" \
  "$SOURCE_DIR/requirements.txt" \
  "$SOURCE_DIR/pyproject.toml" \
  "$SOURCE_DIR/config.example.yaml" \
  "$SOURCE_DIR/assets" \
  "$INSTALL_ROOT/"

echo "    Environnement Python"
python3 -m venv "$INSTALL_ROOT/venv"
"$INSTALL_ROOT/venv/bin/pip" install --upgrade pip -q
"$INSTALL_ROOT/venv/bin/pip" install -r "$INSTALL_ROOT/requirements.txt" -q
"$INSTALL_ROOT/venv/bin/pip" install "$INSTALL_ROOT" -q

echo "    Lanceur ~/.local/bin/nook"
cat > "$BIN_DIR/nook" <<EOF
#!/usr/bin/env bash
set -euo pipefail
INSTALL_ROOT="${INSTALL_ROOT}"
export NOOK_HOME="\${INSTALL_ROOT}"
export PYTHONPATH="\${INSTALL_ROOT}\${PYTHONPATH:+:\${PYTHONPATH}}"
LOG="\${INSTALL_ROOT}/nook.log"

if ! "\${INSTALL_ROOT}/venv/bin/python" -m nook "\$@" 2>"\${LOG}.err"; then
  {
    echo "=== \$(date -Iseconds) ==="
    cat "\${LOG}.err"
  } >> "\${LOG}"
  rm -f "\${LOG}.err"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send -u critical "Nook" "Échec au démarrage — voir \${LOG}"
  fi
  exit 1
fi
rm -f "\${LOG}.err"
EOF
chmod +x "$BIN_DIR/nook"

echo "    Icône et entrée menu"
cp "$INSTALL_ROOT/assets/nook.svg" "$ICON_DIR/nook.svg"
cat > "$DESKTOP_DIR/nook.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Nook
GenericName=Assistant IA local
Comment=Assistant discret connecté à Ollama (100 % local)
Exec=${BIN_DIR}/nook
Icon=nook
Terminal=false
StartupNotify=false
Categories=Utility;Development;
Keywords=AI;Ollama;Assistant;Local;
EOF
chmod +x "$DESKTOP_DIR/nook.desktop"

if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
  cp "$INSTALL_ROOT/config.example.yaml" "$CONFIG_DIR/config.yaml"
  echo "    Config créée : $CONFIG_DIR/config.yaml"
fi

if command -v update-desktop-database &>/dev/null; then
  update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

# PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo ""
  echo "    Ajoutez ~/.local/bin à votre PATH si ce n'est pas déjà fait :"
  echo '    echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.profile'
fi

echo ""
echo "==> Installation terminée."
echo ""
echo "    Lancer Nook :"
echo "      • Menu des applications → « Nook »"
echo "      • Ou : nook"
echo ""
echo "    Prérequis : Ollama installé avec au moins un modèle (ollama pull llama3.2)"
echo ""
read -r -p "    Démarrer Nook au lancement de la session ? [o/N] " AUTOSTART || true
if [[ "${AUTOSTART,,}" == "o" || "${AUTOSTART,,}" == "oui" || "${AUTOSTART,,}" == "y" ]]; then
  mkdir -p "$AUTOSTART_DIR"
  cp "$DESKTOP_DIR/nook.desktop" "$AUTOSTART_DIR/nook.desktop"
  echo "    Autostart activé."
fi
