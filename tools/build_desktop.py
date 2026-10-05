"""Build a native desktop app without original game assets.

Run after `uv sync --locked --extra build`. Only LICENSE and the authored kiwi
logo are explicitly collected as data. User game files, screenshots, saves and
native decompilations have no path into the executable's resource collection.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile


def build_icon(svg, destination):
    """Render the single SVG source into a native ICO or ICNS container."""
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    import pygame
    from PIL import Image

    surface = pygame.image.load_sized_svg(str(svg), (1024, 1024))
    image = Image.frombytes('RGBA', surface.get_size(), pygame.image.tobytes(surface, 'RGBA'))
    if destination.suffix == '.ico':
        image.save(destination, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    else:
        image.save(destination)


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'dist' / 'desktop'
    work = root / 'build' / 'desktop'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='exp-build-') as temporary:
        stage = Path(temporary)
        entry = stage / 'exp_launcher.py'
        entry.write_text('from exp_runtime.application import main\n\nif __name__ == "__main__":\n    main()\n', encoding='utf-8')
        logo = root / 'src' / 'exp_runtime' / 'assets' / 'kiwi.svg'
        # pygame's hook supplies its bundled fallback font and SDL libraries.
        # Only authored runtime modules are reachable through this entry point.
        args = [sys.executable, '-m', 'PyInstaller', '--windowed', '--onedir', '--noconfirm',
                '--name', 'EXP Runtime', '--distpath', str(output), '--workpath', str(work),
                '--specpath', str(stage), '--paths', str(root / 'src'), '--noupx',
                '--add-data', str(root / 'LICENSE') + ':.',
                '--add-data', str(logo) + ':exp_runtime/assets',
                '--exclude-module', 'tkinter']
        if sys.platform in ('darwin', 'win32'):
            icon = stage / ('kiwi.icns' if sys.platform == 'darwin' else 'kiwi.ico')
            build_icon(logo, icon)
            args += ['--icon', str(icon)]
        if sys.platform == 'darwin':
            args += ['--osx-bundle-identifier', 'org.expruntime.player']
        env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(work / 'pyinstaller-cache'))
        subprocess.run([*args, str(entry)], cwd=stage, env=env, check=True)
    print(f'Built desktop app in {output}')


if __name__ == '__main__':
    main()
