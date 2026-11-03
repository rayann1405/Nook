"""Chaînes de l'interface Nook (français / anglais)."""

from __future__ import annotations

LANGUAGE_LABELS = {"fr": "Français", "en": "English"}
LANGUAGE_NAMES = {"fr": "French", "en": "English"}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "fr": {
        "new": "Nouveau",
        "settings": "Réglages",
        "collapse": "Réduire (Échap)",
        "clear": "Effacer",
        "clear_tooltip": "Vider l'historique",
        "new_tooltip": "Effacer la conversation",
        "settings_tooltip": "Afficher ou masquer les réglages",
        "bubble_tooltip": "Nook — cliquer pour ouvrir",
        "mode": "Mode",
        "model": "Modèle",
        "auto_model": "Automatique",
        "language": "Langue",
        "cloud_enabled": "Cloud activé",
        "hard_task": "Tâche complexe",
        "hard_task_tip": "En mode Auto, essaie d'abord le cloud pour les demandes difficiles.",
        "connection": "CONNEXION",
        "meta_section": "META API (CLOUD)",
        "api_key_placeholder": "Clé Meta (META_API_KEY)",
        "save": "Enregistrer",
        "meta_hint": "La clé est enregistrée dans ~/.config/nook/config.yaml (chmod 600).",
        "input_placeholder": "Écrivez un message…",
        "send": "Envoyer",
        "hint": "Entrée pour envoyer · Maj+Entrée pour une nouvelle ligne · Échap pour réduire",
        "empty_state": "Posez une question, demandez une commande\nou collez une erreur à expliquer.",
        "ready": "Prêt",
        "thinking": "Réflexion…",
        "information": "Information",
        "request_failed": "Échec de la requête",
        "key_missing": "Clé Meta manquante",
        "invalid_url": "URL Meta invalide",
        "meta_model_missing": "Modèle Meta manquant",
        "key_validated": "Clé Meta validée",
        "settings_not_saved": "Réglages non enregistrés : {error}",
        "cloud_off": "Cloud désactivé",
        "cloud_key_required": "Cloud · clé requise",
        "local_unavailable": "Local indisponible",
        "auto_offline": "Auto · hors ligne",
        "cloud": "Cloud",
        "local": "Local",
        "auto": "Auto",
        "add_key_hint": "Ajoutez la clé Meta dans Réglages ou dans .env.",
        "enable_cloud_hint": "Activez « Cloud activé » dans les réglages.",
        "compacting": "Réflexion…",
        "step_thought": "Réflexion en cours…",
        "step_action": "Outil : {name}",
        "step_observation": "Résultat : {text}",
        "step_confirmation": "Confirmation requise : {text}",
        "steps": "Détails de l'agent ({count})",
        "role_user": "Vous",
        "role_assistant": "Nook",
        "error_prefix": "Erreur : {error}",
        "confirm_title": "Confirmer l'action",
        "confirm_text": "Nook demande l'autorisation d'effectuer cette action :",
        "yes": "Oui",
        "no": "Non",
        "agent_max_iterations": (
            "J'ai atteint la limite d'itérations sans conclusion. "
            "Reformulez votre demande."
        ),
        "restart_needed": "Clé enregistrée. Vérification de la connexion…",
        "checking_ollama": "Vérification d'Ollama…",
        "wayland_notice": (
            "Wayland peut limiter les raccourcis globaux et l'affichage "
            "toujours au-dessus. Utilisez le menu d'applications Nook si le "
            "raccourci ne fonctionne pas."
        ),
        "hotkey_unavailable": (
            "Raccourci global indisponible ({error}). "
            "Ouvrez Nook depuis le menu d'applications."
        ),
    },
    "en": {
        "new": "New",
        "settings": "Settings",
        "collapse": "Collapse (Esc)",
        "clear": "Clear",
        "clear_tooltip": "Clear history",
        "new_tooltip": "Clear the conversation",
        "settings_tooltip": "Show or hide settings",
        "bubble_tooltip": "Nook — click to open",
        "mode": "Mode",
        "model": "Model",
        "auto_model": "Automatic",
        "language": "Language",
        "cloud_enabled": "Cloud enabled",
        "hard_task": "Hard task",
        "hard_task_tip": "In Auto mode, try the cloud first for difficult requests.",
        "connection": "CONNECTION",
        "meta_section": "META API (CLOUD)",
        "api_key_placeholder": "Meta key (META_API_KEY)",
        "save": "Save",
        "meta_hint": "The key is saved to ~/.config/nook/config.yaml (chmod 600).",
        "input_placeholder": "Type a message…",
        "send": "Send",
        "hint": "Enter to send · Shift+Enter for a new line · Esc to collapse",
        "empty_state": "Ask a question, request a command,\nor paste an error to explain.",
        "ready": "Ready",
        "thinking": "Thinking…",
        "information": "Notice",
        "request_failed": "Request failed",
        "key_missing": "Meta key missing",
        "invalid_url": "Invalid Meta URL",
        "meta_model_missing": "Meta model missing",
        "key_validated": "Meta key validated",
        "settings_not_saved": "Settings not saved: {error}",
        "cloud_off": "Cloud disabled",
        "cloud_key_required": "Cloud · key required",
        "local_unavailable": "Local unavailable",
        "auto_offline": "Auto · offline",
        "cloud": "Cloud",
        "local": "Local",
        "auto": "Auto",
        "add_key_hint": "Add the Meta key in Settings or in .env.",
        "enable_cloud_hint": "Enable “Cloud enabled” in settings.",
        "compacting": "Thinking…",
        "step_thought": "Thinking…",
        "step_action": "Tool: {name}",
        "step_observation": "Result: {text}",
        "step_confirmation": "Confirmation required: {text}",
        "steps": "Agent details ({count})",
        "role_user": "You",
        "role_assistant": "Nook",
        "error_prefix": "Error: {error}",
        "confirm_title": "Confirm action",
        "confirm_text": "Nook requests permission to perform this action:",
        "yes": "Yes",
        "no": "No",
        "agent_max_iterations": (
            "I reached the iteration limit without a conclusion. "
            "Please rephrase your request."
        ),
        "restart_needed": "Key saved. Checking the connection…",
        "checking_ollama": "Checking Ollama…",
        "wayland_notice": (
            "Wayland may limit global shortcuts and always-on-top behavior. "
            "Use the Nook app menu if the shortcut does not work."
        ),
        "hotkey_unavailable": (
            "Global shortcut unavailable ({error}). "
            "You can still open Nook from the app menu."
        ),
    },
}


def normalize_language(language: str | None) -> str:
    value = (language or "").strip().lower()
    if value in TRANSLATIONS:
        return value
    if value.startswith("en"):
        return "en"
    return "fr"


def tr(language: str | None, key: str, **kwargs: object) -> str:
    lang = normalize_language(language)
    text = TRANSLATIONS[lang].get(key) or TRANSLATIONS["fr"].get(key, key)
    return text.format(**kwargs) if kwargs else text
