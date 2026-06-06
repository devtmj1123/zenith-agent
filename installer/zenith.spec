# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Zenith-OS Desktop Application."""

import os
import sys
from pathlib import Path

block_cipher = None

# Project root
root = Path(os.path.abspath(SPECPATH)).parent

a = Analysis(
    [str(root / 'app' / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        # Include templates and static files
        (str(root / 'app' / 'templates'), 'app/templates'),
        (str(root / 'app' / 'static'), 'app/static'),
        # Include config files
        (str(root / 'config'), 'config'),
        # Include skills
        (str(root / 'skills'), 'skills'),
        # Include zenith.md
        (str(root / 'zenith.md'), '.'),
    ],
    hiddenimports=[
        'flask',
        'flask_sock',
        'webview',
        'httpx',
        'yaml',
        'core.agent_loop',
        'core.tools_manager',
        'core.memory_compressor',
        'core.codebook_compiler',
        'core.desire_engine',
        'core.unrelated_association',
        'core.dream_controller',
        'research.science_engine',
        'research.rebuttal_engine',
        'research.debate',
        'research.sources.pubmed',
        'research.sources.arxiv',
        'memory.soft_memory',
        'memory.hard_memory',
        'tools.builtin',
        'filters.entropy_brake',
        'filters.zero_error_filter',
        'filters.unit_standardizer',
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
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Zenith-OS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Show console for logs
    icon=str(root / 'installer' / 'icon.ico') if (root / 'installer' / 'icon.ico').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Zenith-OS',
)
