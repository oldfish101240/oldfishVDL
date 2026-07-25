"""不需 GUI 的核心服務測試。"""

import os
import sys
import tempfile
import time
import unittest

APP_DIR = os.path.join(os.path.dirname(__file__), '..', 'app')
sys.path.insert(0, os.path.abspath(APP_DIR))

from scripts.config.constants import DEFAULT_SETTINGS
from scripts.config.settings import SettingsManager
from scripts.core.video_info import cache_thumbnail
from scripts.services.progress_dispatcher import ProgressDispatcher


class SettingsManagerTests(unittest.TestCase):
    def test_settings_are_stored_in_runtime_state(self):
        with tempfile.TemporaryDirectory() as root:
            manager = SettingsManager(root)
            manager.save_settings({'themeMode': 'dark'})
            self.assertTrue(os.path.isfile(os.path.join(root, 'state', 'settings.json')))
            self.assertEqual(manager.load_settings()['themeMode'], 'dark')
            self.assertTrue(set(DEFAULT_SETTINGS).issubset(manager.load_settings()))


class ProgressDispatcherTests(unittest.TestCase):
    def test_bursty_updates_are_coalesced(self):
        received = []
        dispatcher = ProgressDispatcher(lambda *args: received.append(args), interval=0.02)
        dispatcher.publish(1, 1, 10)
        dispatcher.publish(1, 1, 20)
        dispatcher.publish(1, 1, 30)
        time.sleep(0.06)
        self.assertEqual(received[0], (1, 10))
        self.assertEqual(received[-1], (1, 30))
        self.assertLessEqual(len(received), 2)


class FrontendRuntimePathTests(unittest.TestCase):
    def test_cached_thumbnail_is_resolvable_from_frontend(self):
        with tempfile.TemporaryDirectory() as root:
            cache_dir = os.path.join(root, 'thumb_cache')
            os.makedirs(cache_dir)
            url = 'https://example.invalid/thumb.jpg'
            # 建立預期的快取檔，測試不會碰觸網路。
            import hashlib
            thumb_hash = hashlib.md5(url.encode()).hexdigest()
            open(os.path.join(cache_dir, f'{thumb_hash}.jpg'), 'wb').close()
            self.assertEqual(
                cache_thumbnail(url, root),
                f'../runtime/thumb_cache/{thumb_hash}.jpg',
            )


if __name__ == '__main__':
    unittest.main()
