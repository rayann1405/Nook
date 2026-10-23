# Nook

Nook is a local-first desktop AI assistant for Ubuntu, powered by Ollama.
It combines a lightweight PyQt6 interface with a ReAct agent to interact with local language models.

Assistant virtuel de bureau **100 % local** pour Ubuntu. Interface ultra-discrète en bas à droite, connectée à [Ollama](http://localhost:11434). **Détection automatique** du modèle installé sur la machine.

## Stack technique

| Composant | Choix |
|-----------|-------|
| Langage | Python 3.10+ |
| UI | PyQt6 (frameless, always-on-top, ~30 Mo RAM) |
| LLM | Ollama HTTP — modèle détecté automatiquement |
| Agent | ReAct (Thought → Action → Observation) |
| Raccourci | pynput — Ctrl+Alt+Espace (configurable) |

## Structure

```
Nook/
├── install.sh               # Installation application Ubuntu
├── uninstall.sh
├── config.example.yaml
├── requirements.txt
├── assets/nook.svg
└── nook/
    ├── main.py
    ├── config.py            # ~/.config/nook/config.yaml
    ├── ollama_client.py     # Détection auto du modèle
    ├── agent.py
    ├── tools.py
    ├── hotkey.py
    └── ui/
```

## Installation (application Ubuntu)

### 1. Prérequis

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
    libxcb-cursor0 libxkbcommon-x11-0 libegl1 python3-xlib rsync

# Ollama + au moins un modèle
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2   # ou tout autre modèle chat
```

### 2. Installer Nook

```bash
cd Nook
chmod +x install.sh uninstall.sh
./install.sh
```

L'installateur :
- copie l'app dans `~/.local/share/nook`
- crée le lanceur `~/.local/bin/nook`
- enregistre **Nook** dans le menu des applications Ubuntu
- crée `~/.config/nook/config.yaml`
- propose le démarrage automatique à la session

### 3. Lancer

- **Menu des applications** → rechercher **Nook**
- Ou en ligne de commande : `nook`

Aucune fenêtre de terminal n'est ouverte (`Terminal=false`).

### Désinstallation

```bash
./uninstall.sh
```

---

## Détection automatique du modèle

Au démarrage, Nook interroge Ollama et choisit le modèle sans configuration manuelle :

1. Modèle explicitement défini dans la config / `NOOK_MODEL` (s'il est installé)
2. Sinon, modèle **actuellement chargé** en mémoire (`/api/ps`)
3. Sinon, modèle chat **le plus récemment installé** (`/api/tags`)

Les modèles d'embedding (`nomic-embed`, etc.) sont ignorés.

Re-détection automatique toutes les 15 secondes (si Ollama démarre après l'app).

---

## Interface discrète

| État | Description |
|------|-------------|
| **Bulle** | Carré sombre 22×22 px, coin bas-droit, au-dessus de la barre des tâches |
| **Déplié** | Panneau compact 320×420 px, même ancrage |
| **Ctrl+Alt+Espace** | Afficher / masquer instantanément |
| **Clic bulle** | Ouvre le chat |
| **×** | Replie en bulle |

La fenêtre reste **verrouillée en bas à droite** (pas de déplacement).

---

## Configuration (`~/.config/nook/config.yaml`)

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: auto          # auto = détection (recommandé)
  temperature: 0.3

ui:
  hotkey: "ctrl+alt+space"
  bubble_opacity: 0.42
  bubble_size: 22
  screen_margin: 6
```

Variables d'environnement optionnelles : `NOOK_MODEL`, `NOOK_OLLAMA_URL`, `NOOK_HOTKEY`.

---

## Outils agent

- **`run_command`** — commandes shell non bloquantes
- **`read_file`** — lecture de fichiers locaux
- **`list_directory`** — listage de répertoires

---

## Dépannage

| Problème | Solution |
|----------|----------|
| Ollama hors ligne | `systemctl --user start ollama` ou lancer Ollama |
| Aucun modèle | `ollama pull llama3.2` |
| App absente du menu | Vérifier `~/.local/share/applications/nook.desktop` |
| Raccourci global | Sur Wayland, permissions accessibilité ou session X11 |

## Développement local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m nook
```

## Licence

MIT
