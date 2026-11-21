import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nook.config import _build_from_dict, _load_yaml, load_dotenv, save_config


class ConfigTests(unittest.TestCase):
    def test_meta_endpoint_and_model_can_be_configured(self):
        config = _build_from_dict(
            {
                "meta": {
                    "base_url": "https://meta.example/v1/",
                    "model": "custom-model",
                    "api_key": " secret-key ",
                }
            }
        )

        self.assertEqual(config.meta.base_url, "https://meta.example/v1")
        self.assertEqual(config.meta.model, "custom-model")
        self.assertEqual(config.meta.api_key, "secret-key")

    def test_ui_dimensions_are_clamped_to_usable_minimums(self):
        config = _build_from_dict(
            {
                "ui": {
                    "bubble_opacity": 0.1,
                    "expanded_width": 200,
                    "expanded_height": 200,
                    "bubble_size": 10,
                }
            }
        )

        self.assertGreaterEqual(config.ui.expanded_width, 400)
        self.assertGreaterEqual(config.ui.expanded_height, 560)
        self.assertGreaterEqual(config.ui.bubble_size, 40)
        self.assertGreaterEqual(config.ui.bubble_opacity, 0.6)

    def test_dotenv_file_supplies_the_meta_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "export META_API_KEY=from-dotenv\n"
                "# comment\n"
                'META_MODEL="muse-dotenv"\n',
                encoding="utf-8",
            )
            with patch.dict(
                os.environ, {"NOOK_ENV_FILE": str(env_path)}, clear=False
            ):
                os.environ.pop("META_API_KEY", None)
                os.environ.pop("MODEL_API_KEY", None)
                os.environ.pop("META_MODEL", None)
                load_dotenv()

                self.assertEqual(os.environ["META_API_KEY"], "from-dotenv")
                self.assertEqual(os.environ["META_MODEL"], "muse-dotenv")

    def test_dotenv_never_overrides_existing_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("META_API_KEY=from-dotenv\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "NOOK_ENV_FILE": str(env_path),
                    "META_API_KEY": "from-shell",
                    "MODEL_API_KEY": "",
                },
            ):
                load_dotenv()

                self.assertEqual(os.environ["META_API_KEY"], "from-shell")


    def test_save_config_round_trips_meta_key_and_protects_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            config = _build_from_dict(
                {
                    "router": {"mode": "cloud"},
                    "meta": {
                        "api_key": "persisted-key",
                        "base_url": "https://meta.example/v1",
                    },
                    "ui": {"language": "en"},
                }
            )

            save_config(config, path)
            reloaded = _build_from_dict(_load_yaml(path))

            self.assertEqual(reloaded.meta.api_key, "persisted-key")
            self.assertEqual(reloaded.meta.base_url, "https://meta.example/v1")
            self.assertEqual(reloaded.router.mode, "cloud")
            self.assertEqual(reloaded.ui.language, "en")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_ui_language_defaults_to_french_and_normalizes_input(self):
        self.assertEqual(_build_from_dict({}).ui.language, "fr")
        self.assertEqual(
            _build_from_dict({"ui": {"language": "EN-us"}}).ui.language,
            "en",
        )
        self.assertEqual(
            _build_from_dict({"ui": {"language": "unsupported"}}).ui.language,
            "fr",
        )


if __name__ == "__main__":
    unittest.main()
