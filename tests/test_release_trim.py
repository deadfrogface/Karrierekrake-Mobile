"""Release trims must retain the Google schemas and local inference engine."""
import importlib.util
from pathlib import Path


def policy():
    spec = importlib.util.spec_from_file_location('trim_policy', Path(__file__).parents[1] / 'packaging/kk_content_policy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_google_discovery_schema_allowlist():
    p = policy()
    prefix = 'googleapiclient/discovery_cache/documents/'
    assert p.release_data_allowed(prefix + 'gmail.v1.json')
    assert p.release_data_allowed(prefix + 'calendar.v3.json')
    assert not p.release_data_allowed(prefix + 'compute.v1.json')
    assert not p.release_data_allowed(prefix.replace('/', '\\') + 'drive.v3.json')
    assert p.release_data_allowed('assets/oauth/desktop_client.json')
    assert p.release_data_allowed('models/qwen3.5-4b/model.gguf')


def test_unused_qt_parts_stay_out_of_the_windows_package():
    p = policy()
    for name in ('PySide6\\opengl32sw.dll', 'PySide6\\Qt6Quick.dll', 'PySide6/Qt6Qml.dll', 'PySide6/Qt6Pdf.dll',
                 'PySide6/plugins/imageformats/qpdf.dll', 'PySide6/plugins/platforms/qdirect2d.dll'):
        assert not p.lean_bundle_allowed(name, os_name='win32')
        assert p.lean_bundle_allowed(name, os_name='linux')  # Linux names differ (next test)
    for name in ('PySide6/Qt6Core.dll', 'PySide6/Qt6Widgets.dll', 'PySide6/Qt6Svg.dll', 'PySide6/Qt6Network.dll',
                 'PySide6/plugins/platforms/qwindows.dll', 'PySide6/plugins/platforms/qoffscreen.dll',
                 'PySide6/plugins/imageformats/qsvg.dll', 'PySide6/plugins/styles/qmodernwindowsstyle.dll',
                 'PySide6/plugins/tls/qschannelbackend.dll', 'llama_cpp/lib/llama.dll', 'numpy.libs/libopenblas.dll'):
        assert p.lean_bundle_allowed(name, os_name='win32')


def test_only_german_and_english_qt_texts_ship():
    p = policy()
    for os_name in ('win32', 'linux', 'darwin'):
        assert p.lean_bundle_allowed('PySide6/translations/qtbase_de.qm', os_name=os_name)
        assert p.lean_bundle_allowed('PySide6/Qt/translations/qtbase_en.qm', os_name=os_name)
        assert not p.lean_bundle_allowed('PySide6/translations/qtbase_ja.qm', os_name=os_name)
        assert not p.lean_bundle_allowed('PySide6\\Qt\\translations\\qtdeclarative_de.qm', os_name=os_name)
    assert p.lean_bundle_allowed('translations/app_fr.qm', os_name='win32')  # not Qt's own folder


def test_legacy_providers_and_llama_server_excluded_but_product_paths_retained():
    p = policy()
    for name in ('integrations.calendar.microsoft.adapter', 'llama_cpp.server.app'):
        assert not p.module_allowed(name)
    for name in ('integrations.mail.imap.adapter', 'integrations.mail.imap.outlook_auth',
                 'integrations.mail.microsoft.oauth_pkce', 'integrations.calendar.local_ics',
                 'integrations.calendar.caldav.client', 'integrations.mail.google.adapter', 'integrations.calendar.google.adapter',
                 'core.cv_llm_runtime', 'core.cover_quality', 'llama_cpp.llama'):
        assert p.module_allowed(name)
    assert 'llama_cpp' in p.ALLOWED_COLLECT_ALL_PACKAGES
    assert 'googleapiclient' not in p.ANALYSIS_EXCLUDES


NUMPY_PARTS_LEFT_OUT = ("numpy.random", "numpy.fft", "numpy.ma", "numpy.polynomial", "numpy.f2py", "numpy.testing")


def test_the_numpy_parts_left_out_of_the_package_are_never_loaded():
    """The package has no numpy.random, fft, ma, polynomial, f2py, testing: the import path must not ask for them."""
    import subprocess
    import sys

    p = policy()
    assert set(NUMPY_PARTS_LEFT_OUT) <= set(p.ANALYSIS_EXCLUDES)
    code = (
        "import sys\n"
        f"for name in {NUMPY_PARTS_LEFT_OUT!r}:\n"
        "    sys.modules[name] = None\n"
        "import numpy, llama_cpp\n"
        "assert int(numpy.__version__.split('.')[0]) >= 2, numpy.__version__\n"
        "import core.llm_fast_json, core.llm_lookahead, core.cv_llm_runtime, core.cv_docpick_import\n"
        "scores = numpy.zeros(8, dtype=numpy.single); scores[5] = 1\n"
        "assert int(numpy.argmax(scores)) == 5 and float(numpy.linalg.norm(scores)) == 1.0\n"
        "print('ok')\n"
    )
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0 and done.stdout.strip().endswith("ok"), done.stderr[-2000:]


def test_pillow_reads_images_without_the_avif_codec_left_out_of_the_package():
    """The AVIF codec (7.5 MB) is not packaged; Pillow, pypdf and Docpick must work as before without it."""
    import subprocess
    import sys

    p = policy()
    assert {"PIL._avif", "PIL.AvifImagePlugin"} <= set(p.ANALYSIS_EXCLUDES)
    code = (
        "import io, sys\n"
        "sys.modules['PIL._avif'] = None\n"
        "sys.modules['PIL.AvifImagePlugin'] = None\n"
        "from PIL import Image\n"
        "Image.init()\n"
        "for fmt in ('PNG', 'JPEG'):\n"
        "    buf = io.BytesIO(); Image.new('RGB', (4, 3), 'red').save(buf, fmt); buf.seek(0)\n"
        "    assert Image.open(buf).size == (4, 3)\n"
        "import pypdf, core.cv_extract, core.cv_docpick_import\n"
        "print('ok')\n"
    )
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0 and done.stdout.strip().endswith("ok"), done.stderr[-2000:]


def test_unused_qt_and_duplicate_llama_libraries_stay_out_of_the_linux_package():
    p = policy()
    for name in ('PySide6/Qt/lib/libQt6Quick.so.6', 'libQt6Quick.so.6', 'PySide6/Qt/lib/libQt6Qml.so.6',
                 'PySide6/Qt/lib/libQt6Pdf.so.6', 'libQt6VirtualKeyboardQml.so.6',
                 'PySide6/Qt/plugins/imageformats/libqpdf.so',
                 'PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so',
                 'llama_cpp/lib/libllama.so.0', 'llama_cpp/lib/libllama.so.0.1.0', 'libllama.so.0',
                 'llama_cpp/lib/libggml-cpu.so', 'llama_cpp/lib/libggml-cpu.so.0.20.0',
                 'llama_cpp/lib/libggml-base.so', 'llama_cpp/lib/libggml.so.0.20.0',
                 'llama_cpp/lib/libmtmd.so', 'llama_cpp/lib/libmtmd.so.SOVERSION'):
        assert not p.lean_bundle_allowed(name, os_name='linux'), name
    for name in ('PySide6/Qt/lib/libQt6Core.so.6', 'PySide6/Qt/lib/libQt6Gui.so.6', 'libQt6Widgets.so.6',
                 'PySide6/Qt/lib/libQt6OpenGL.so.6', 'PySide6/Qt/lib/libQt6WaylandClient.so.6',
                 'PySide6/Qt/lib/libQt6XcbQpa.so.6', 'PySide6/Qt/lib/libicudata.so.73',
                 'PySide6/Qt/plugins/platforms/libqxcb.so', 'PySide6/Qt/plugins/platforms/libqwayland.so',
                 'llama_cpp/lib/libllama.so', 'llama_cpp/lib/libggml.so', 'llama_cpp/lib/libggml.so.0',
                 'llama_cpp/lib/libggml-base.so.0', 'llama_cpp/lib/libggml-cpu.so.0', 'libggml-cpu.so.0',
                 'llama_cpp/__init__.py'):
        assert p.lean_bundle_allowed(name, os_name='linux'), name


def test_parts_no_system_uses_stay_out_of_every_package():
    p = policy()
    for os_name in ('win32', 'linux', 'darwin'):
        for name in ('llama_cpp/lib/mtmd.dll', 'llama_cpp/lib/llama.lib', 'llama_cpp/lib/libmtmd.dylib',
                     'playwright/driver/package/types/types.d.ts', 'assets/brand/social-preview.png',
                     'assets/brand/icons/icon-1024.png', 'assets/brand/logo.png'):
            assert not p.lean_bundle_allowed(name, os_name=os_name), (os_name, name)
        for name in ('llama_cpp/lib/llama.dll', 'playwright/driver/package/lib/server/x.js',
                     'assets/brand/karrierekrake-logo-master.png', 'assets/brand/app.ico',
                     'assets/brand/icons/icon-256.png', 'assets/brand/icons/icon-64.png'):
            assert p.lean_bundle_allowed(name, os_name=os_name), (os_name, name)


def test_every_image_a_window_asks_for_is_still_packaged():
    """desktop/branding.py asks for these; the filter must keep each first choice."""
    p = policy()
    for name in ('assets/brand/karrierekrake-logo-master.png', 'assets/brand/app.ico',
                 'assets/brand/icons/icon-256.png', 'assets/brand/icons/icon-128.png',
                 'assets/brand/icons/icon-64.png', 'assets/brand/icons/icon-48.png',
                 'assets/brand/icons/icon-32.png'):
        assert p.lean_bundle_allowed(name, os_name='win32'), name



def test_unused_qt_frameworks_and_duplicate_llama_libraries_stay_out_of_the_mac_package():
    p = policy()
    for name in ('PySide6/Qt/lib/QtQuick.framework/Versions/A/QtQuick',
                 'PySide6/Qt/lib/QtQuick.framework/Versions/A/Resources/Info.plist',
                 'PySide6/Qt/lib/QtQuick.framework', 'PySide6/Qt/lib/QtQml.framework/QtQml',
                 'PySide6/Qt/lib/QtPdf.framework/Versions/A/QtPdf',
                 'PySide6/Qt/lib/QtVirtualKeyboardQml.framework/Versions/Current',
                 'PySide6/Qt/plugins/imageformats/libqpdf.dylib',
                 'PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.dylib',
                 'llama_cpp/lib/libllama.0.1.0.dylib', 'llama_cpp/lib/libllama.0.dylib', 'libllama.0.dylib',
                 'llama_cpp/lib/libggml-base.dylib', 'llama_cpp/lib/libggml-base.0.20.0.dylib',
                 'llama_cpp/lib/libggml-blas.dylib', 'llama_cpp/lib/libggml-cpu.0.20.0.dylib',
                 'llama_cpp/lib/libggml.0.20.0.dylib', 'llama_cpp/lib/libmtmd.0.dylib'):
        assert not p.lean_bundle_allowed(name, os_name='darwin'), name
    for name in ('PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore', 'PySide6/Qt/lib/QtGui.framework/QtGui',
                 'PySide6/Qt/lib/QtWidgets.framework/Versions/A/QtWidgets',
                 'PySide6/Qt/lib/QtOpenGL.framework/Versions/A/QtOpenGL',
                 'PySide6/Qt/lib/QtNetwork.framework/Versions/A/QtNetwork',
                 'PySide6/Qt/lib/QtSvg.framework/Versions/A/QtSvg', 'PySide6/Qt/lib/QtDBus.framework/QtDBus',
                 'PySide6/Qt/plugins/platforms/libqcocoa.dylib', 'PySide6/Qt/plugins/imageformats/libqsvg.dylib',
                 'llama_cpp/lib/libllama.dylib', 'llama_cpp/lib/libggml.dylib', 'llama_cpp/lib/libggml.0.dylib',
                 'llama_cpp/lib/libggml-base.0.dylib', 'llama_cpp/lib/libggml-cpu.0.dylib',
                 'llama_cpp/lib/libggml-blas.0.dylib', 'libggml-blas.0.dylib', 'llama_cpp/llama.py'):
        assert p.lean_bundle_allowed(name, os_name='darwin'), name


def test_command_line_front_ends_and_their_terminal_libraries_stay_out():
    p = policy()
    for name in ('httpx._main', 'ddgs.cli', 'ddgs.api_server', 'docpick.cli', 'rich.console', 'pygments.lexers',
                 'click', 'setuptools', 'pkg_resources', 'pydoc_data.topics'):
        assert not p.module_allowed(name), name
    for name in ('httpx', 'ddgs', 'ddgs.ddgs', 'docpick', 'dotenv', 'keyring', 'jaraco.classes', 'pydoc', 'cffi'):
        assert p.module_allowed(name), name
    assert set(p.UNUSED_TOOL_MODULES) <= set(p.ANALYSIS_EXCLUDES)
    assert 'distutils' not in p.ANALYSIS_EXCLUDES  # PyInstaller's distutils hook aborts the build on it


def test_the_libraries_the_app_uses_import_without_the_command_line_parts():
    import subprocess
    import sys

    p = policy()
    code = (
        "import importlib.abc, sys\n"
        f"hidden = {p.UNUSED_TOOL_MODULES!r}\n"
        "class Hide(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if any(name == h or name.startswith(h + '.') for h in hidden):\n"
        "            raise ModuleNotFoundError(name, name=name)\n"
        "sys.meta_path.insert(0, Hide())\n"
        "import httpx, ddgs, docpick, dotenv, pydantic, pydantic_settings, cffi, keyring, numpy, llama_cpp\n"
        "import google_auth_oauthlib.flow, googleapiclient.discovery\n"
        "import core.cv_docpick_import, core.cv_llm_runtime, search, integrations.mail.google.adapter\n"
        "assert httpx.Client and ddgs.DDGS\n"
        "print('ok')\n"
    )
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0 and done.stdout.strip().endswith("ok"), done.stderr[-2000:]


def test_only_the_dateparser_languages_the_parser_asks_for_ship():
    import re

    p = policy()
    root = Path(__file__).resolve().parents[1]
    asked = re.findall(r"dateparser\.parse\([^)]*languages=\[([^\]]*)\]", (root / "integrations/proposal_parse.py").read_text(encoding="utf-8"))
    assert asked and {tuple(x.strip().strip("'\"") for x in a.split(",")) for a in asked} == {p.DATEPARSER_LANGUAGES}
    excluded = p.analysis_excludes()
    assert set(p.ANALYSIS_EXCLUDES) <= set(excluded)
    tables = [n for n in excluded if n.startswith("dateparser.data.date_translation_data.")]
    assert len(tables) > 150 and "dateparser.data.date_translation_data.fr" in tables
    assert not {f"dateparser.data.date_translation_data.{lang}" for lang in p.DATEPARSER_LANGUAGES} & set(tables)


def test_dates_still_parse_with_only_those_language_tables():
    import subprocess
    import sys

    p = policy()
    hidden = [n for n in p.analysis_excludes() if n.startswith("dateparser.data.date_translation_data.")]
    code = (
        "import importlib.abc, sys\n"
        f"hidden = set({hidden!r})\n"
        "class Hide(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name in hidden:\n"
        "            raise ModuleNotFoundError(name, name=name)\n"
        "sys.meta_path.insert(0, Hide())\n"
        "from datetime import datetime\n"
        "from integrations.proposal_parse import parse_scheduling_proposal\n"
        "ref = datetime(2026, 11, 16, 9, 0)\n"
        "for text, day in (('morgen um 10:30', 17), ('übermorgen', 18), ('tomorrow at 10:30', 17)):\n"
        "    r = parse_scheduling_proposal(text, reference=ref)\n"
        "    assert r.used_dateparser and r.fixed_slots and r.fixed_slots[0].day == day, (text, r)\n"
        "print('ok')\n"
    )
    root = Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=300,
                          encoding="utf-8")
    assert done.returncode == 0 and done.stdout.strip().endswith("ok"), done.stderr[-2000:]
