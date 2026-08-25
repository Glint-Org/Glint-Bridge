import json
import unittest
from unittest.mock import patch

from bridge.ai_config import resolve_ai_settings
from bridge.ai_planner import (
    _extract_json,
    heuristic_decision,
    summarize_android_hierarchy,
)


SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy>
  <node class="android.widget.FrameLayout" clickable="false" scrollable="false" text="" content-desc="" resource-id="" bounds="[0,0][1080,1920]">
    <node class="android.widget.TextView" clickable="false" scrollable="false" text="Home" content-desc="" resource-id="com.app:id/title" bounds="[40,80][200,120]"/>
    <node class="android.widget.Button" clickable="true" scrollable="false" text="Get Started" content-desc="" resource-id="com.app:id/cta" bounds="[100,800][980,900]"/>
    <node class="android.widget.ScrollView" clickable="false" scrollable="true" text="" content-desc="" resource-id="com.app:id/list" bounds="[0,200][1080,1800]"/>
  </node>
</hierarchy>
"""


class TestAiPlanner(unittest.TestCase):
    def test_summarize_hierarchy_finds_targets(self):
        s = summarize_android_hierarchy(SAMPLE_XML, package="com.app")
        self.assertTrue(any(t.clickable for t in s.targets))
        self.assertTrue(any(t.scrollable for t in s.targets))
        self.assertTrue(any("Get Started" in t.label for t in s.targets))

    def test_heuristic_prefers_scroll(self):
        s = summarize_android_hierarchy(SAMPLE_XML, package="com.app")
        d = heuristic_decision(s, step=0)
        self.assertEqual(d.action, "scroll")
        self.assertEqual(d.source, "heuristic")

    def test_extract_json_fenced(self):
        data = _extract_json('```json\n{"action":"done","score":0.9,"keep":true,"label":"home"}\n```')
        self.assertEqual(data["action"], "done")
        self.assertTrue(data["keep"])

    def test_resolve_ai_requires_flag(self):
        with patch.dict("os.environ", {"GLINT_AI_API_KEY": "sk-test"}, clear=False):
            self.assertIsNone(resolve_ai_settings(use_ai=None))
            settings = resolve_ai_settings(use_ai=True, api_key="sk-test")
            self.assertIsNotNone(settings)
            self.assertEqual(settings.api_key, "sk-test")

    def test_resolve_ai_missing_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                resolve_ai_settings(use_ai=True)


if __name__ == "__main__":
    unittest.main()
