# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for bundling the Price Tracker Flask backend
into a standalone binary (no Python installation needed).

Usage:
  pyinstaller backend.spec --distpath electron-resources/backend --noconfirm
"""

a = Analysis(
    ['api_secure.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('database.py', '.'),
        ('src/playwright_scraper.py', 'src/'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'flask_limiter',
        'flask_limiter.util',
        'playwright',
        'playwright.sync_api',
        'requests',
        'dotenv',
        'gunicorn',
        'sqlite3',
        'dataclasses',
        'concurrent.futures',
        'logging',
        'threading',
        'json',
        'secrets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'test',
        'unittest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='api_secure',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='api_secure',
)
