"""Install new local copies without overwriting any existing installation."""
import os
from pathlib import Path
import shutil

source = Path(__file__).resolve().parent
home = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
package = home / 'plugins' / 'hermes-slash-router'
desktop = home / 'desktop-plugins' / 'hermes-slash-router'
if package.exists() or desktop.exists():
    raise SystemExit('Installation already exists; inspect it before updating.')
shutil.copytree(source, package, ignore=shutil.ignore_patterns(
    'tests', '__pycache__', '.git', 'install.py', 'live-results.json'))
shutil.copytree(source / 'desktop', desktop)
print(f'Installed desktop: {desktop}')
print(f'Installed backend package: {package}')
print('Jev-first routing is ready to load. Enable the backend plugin and set TYPESAFE_API_KEY in the gateway environment for Jev.')
