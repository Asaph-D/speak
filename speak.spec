# -*- mode: python ; coding: utf-8 -*-
# =====================================================
# Fichier de configuration PyInstaller pour speak.py
#
# Pour compiler l'exécutable :
# pyinstaller speak.spec
#
# Assurez-vous que les modèles Vosk sont placés dans :
# models/vosk-model-small-fr-0.22/
# models/vosk-model-small-en-us-0.15/
#
# Et que l'icône icon11.ico est dans le dossier courant
# =====================================================

from PyInstaller.utils.hooks import collect_data_files

datas = [('models/vosk-model-small-fr-0.22', 'models/vosk-model-small-fr-0.22'), ('models/vosk-model-small-en-us-0.15', 'models/vosk-model-small-en-us-0.15'), ('icon.ico', '.')]
datas += collect_data_files('vosk')


a = Analysis(
    ['speak.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='speak',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon11.ico'],
)
