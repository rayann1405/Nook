import unittest

from nook.config import _build_from_dict


class ConfigTests(unittest.TestCase):
    def test_meta_endpoint_and_model_can_be_configured(self):
        config = _build_from_dict(
            {
                "meta": {
                    "base_url": "https://meta.example/v1/",
                    "model": "custom-model",
                }
            }
        )

        self.assertEqual(config.meta.base_url, "https://meta.example/v1")
        self.assertEqual(config.meta.model, "custom-model")


if __name__ == "__main__":
    unittest.main()
