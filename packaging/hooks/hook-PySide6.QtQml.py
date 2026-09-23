"""Collect the app's QML dependency closure before DLL dependency analysis.

The standard hook collects every installed QML extension, including WebEngine,
3D and multimedia. Those modules are not used by this app. Keep complete module
directories (including resources), rather than deleting DLLs from a finished build.
"""
from pathlib import Path
import re

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info


QML_MODULES = {
    'QtQml', 'QtQml/Models', 'QtQml/WorkerScript',
    'QtQuick', 'QtQuick/Window', 'QtQuick/Layouts', 'QtQuick/Templates',
    'QtQuick/Controls', 'QtQuick/Controls/impl',
    'QtQuick/Controls/Basic', 'QtQuick/Controls/Basic/impl',
    'QtQuick/Controls/Material', 'QtQuick/Controls/Material/impl',
    'QtQuick/Effects', 'QtQuick/Shapes', 'QtQuick/tooling',
}

# Fail clearly if future app changes need an additional QML module.
project = Path(__file__).resolve().parents[2]
for qml_file in (project / 'qml').rglob('*.qml'):
    imports = re.findall(r'^\s*import\s+([\w.]+)', qml_file.read_text(encoding='utf-8'), re.M)
    missing = {name for name in imports if name.replace('.', '/') not in QML_MODULES}
    if missing:
        raise RuntimeError(f'Add required QML modules to the packaging hook: {sorted(missing)}')

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
qml_root = Path(pyside6_library_info.location['QmlImportsPath']).resolve()
qml_destination = Path(pyside6_library_info.qt_rel_dir) / 'qml'

for module in sorted(QML_MODULES):
    module_dir = qml_root / module
    qmldir = module_dir / 'qmldir'
    if not qmldir.is_file():
        raise RuntimeError(f'Required QML module is missing: {module}')
    # Use the same plugin validation/resource collection as the standard hook,
    # but only for this explicit module closure. PyInstaller resolves DLL imports.
    module_binaries, module_datas = pyside6_library_info._process_qml_plugin(qmldir)
    for sources, destination in [(module_binaries, binaries), (module_datas, datas)]:
        for source in sources:
            relative = source.relative_to(qml_root)
            folder = relative if source.is_dir() else relative.parent
            destination.append((str(source), str(qml_destination / folder)))
