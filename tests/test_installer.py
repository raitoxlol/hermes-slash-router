import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('slash_router_installer', ROOT / 'install.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTest(unittest.TestCase):
    def test_installs_one_unified_package_and_skips_local_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            package = installer.install(home)

            self.assertEqual(package, home / 'plugins' / 'hermes-slash-router')
            self.assertTrue((package / 'plugin.yaml').is_file())
            self.assertTrue((package / 'desktop' / 'plugin.js').is_file())
            self.assertTrue((package / 'dashboard' / 'plugin_api.py').is_file())
            self.assertTrue((package / 'core' / 'resolve.py').is_file())
            self.assertTrue((package / 'catalogs' / 'hermes.json').is_file())
            self.assertTrue((package / 'slash_route.py').is_file())
            self.assertFalse((package / 'videos').exists())
            self.assertFalse((home / 'desktop-plugins').exists())
            self.assertFalse((package / 'live-results.json').exists())
            self.assertFalse((package / 'install.py').exists())
    def test_refuses_to_overwrite_existing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            package = installer.install(home)
            marker = package / 'keep-me.txt'
            marker.write_text('existing user data', encoding='utf-8')

            with self.assertRaisesRegex(FileExistsError, 'Existing plugin installation'):
                installer.install(home)

            self.assertEqual(marker.read_text(encoding='utf-8'), 'existing user data')

    def test_refuses_to_shadow_existing_standalone_desktop_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            desktop_plugin = home / 'desktop-plugins' / 'hermes-slash-router'
            desktop_plugin.mkdir(parents=True)
            marker = desktop_plugin / 'keep-me.txt'
            marker.write_text('existing user data', encoding='utf-8')

            with self.assertRaisesRegex(FileExistsError, 'Existing plugin installation'):
                installer.install(home)

            self.assertEqual(marker.read_text(encoding='utf-8'), 'existing user data')
            self.assertFalse((home / 'plugins' / 'hermes-slash-router').exists())

    def test_reports_both_existing_installation_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            package = home / 'plugins' / 'hermes-slash-router'
            desktop_plugin = home / 'desktop-plugins' / 'hermes-slash-router'
            package.mkdir(parents=True)
            desktop_plugin.mkdir(parents=True)

            with self.assertRaises(FileExistsError) as result:
                installer.install(home)

            self.assertIn(str(package), str(result.exception))
            self.assertIn(str(desktop_plugin), str(result.exception))


if __name__ == '__main__':
    unittest.main()
