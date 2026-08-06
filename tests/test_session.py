import json
import tempfile
import unittest
from pathlib import Path

from bridge.session import write_session, load_session, update_session_with_capture


class TestSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = Path(self.tmp)

    def test_write_and_load_session(self):
        path = write_session(
            screens=["home.png", "profile.png"],
            app="TestApp",
            tagline="Hello",
            store="play",
            output_dir=self.out,
        )
        self.assertTrue(Path(path).exists())

        session = load_session(self.out)
        self.assertEqual(session["app"], "TestApp")
        self.assertEqual(session["tagline"], "Hello")
        self.assertEqual(session["screens"], ["home.png", "profile.png"])
        self.assertEqual(session["store"], "play")
        self.assertEqual(session["version"], "1.0")

    def test_update_session_appends_screen(self):
        write_session(screens=["a.png"], app="App", output_dir=self.out)
        update_session_with_capture("b.png", output_dir=self.out)
        session = load_session(self.out)
        self.assertEqual(session["screens"], ["a.png", "b.png"])


if __name__ == "__main__":
    unittest.main()
