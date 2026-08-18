import unittest

from aws_spot_price_selector.config import (
    Config,
    RegionsConfig,
    excluded_by,
    included_by,
    validate_config,
)
from aws_spot_price_selector.errors import ConfigError


class RegionExclusionTests(unittest.TestCase):
    def test_mask_and_exact_patterns(self):
        config = RegionsConfig(excluded_regions=["eu-*", "us-east-1"])
        self.assertEqual(excluded_by("eu-west-1", config), ["pattern:eu-*"])
        self.assertEqual(excluded_by("us-east-1", config), ["pattern:us-east-1"])
        self.assertEqual(excluded_by("ca-central-1", config), [])

    def test_glob_matches_whole_region(self):
        config = RegionsConfig(excluded_regions=["eu-west-*"])
        self.assertEqual(excluded_by("eu-west-1", config), ["pattern:eu-west-*"])
        self.assertEqual(excluded_by("eu-central-1", config), [])
        self.assertEqual(excluded_by("x-eu-west-1", config), [])

    def test_normalizes_case_and_deduplicates(self):
        config = Config()
        config.run.mode = "latency"
        config.regions = RegionsConfig(
            excluded_regions=["EU-WEST-*", "eu-west-*"],
        )
        validate_config(config)
        self.assertEqual(config.regions.excluded_regions, ["eu-west-*"])

    def test_rejects_unsupported_glob(self):
        config = Config()
        config.run.mode = "latency"
        config.regions.excluded_regions = ["eu-west-?"]
        with self.assertRaises(ConfigError):
            validate_config(config)

    def test_default_include_rules_allow_every_region(self):
        config = RegionsConfig()
        self.assertTrue(included_by("eu-west-1", config))
        self.assertTrue(included_by("us-east-1", config))

    def test_explicit_include_patterns(self):
        config = RegionsConfig(included_regions=["eu-*", "us-east-*"])
        self.assertTrue(included_by("eu-central-1", config))
        self.assertTrue(included_by("us-east-2", config))
        self.assertFalse(included_by("ap-south-1", config))

    def test_exclusion_can_override_inclusion(self):
        config = RegionsConfig(
            included_regions=["eu-*"],
            excluded_regions=["eu-west-*"],
        )
        self.assertTrue(included_by("eu-west-1", config))
        self.assertTrue(excluded_by("eu-west-1", config))

    def test_rejects_empty_allowlist(self):
        config = Config()
        config.run.mode = "latency"
        config.regions.included_regions = []
        with self.assertRaises(ConfigError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
