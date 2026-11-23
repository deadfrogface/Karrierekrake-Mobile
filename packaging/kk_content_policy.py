"""Production content policy for Karrierekrake release artifacts.

Allowlist-first: only explicitly approved repo datas and module prefixes may
ship in the PyInstaller onefile EXE. Forbidden path markers / content patterns
always block release — never silence the scanner permanently.

Dev datasets (tests/, benchmark/, tools/cover_opt, fixtures, demo seeding)
remain in Git for development; they must not appear in dist/.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, NamedTuple

POLICY_VERSION = 1

# ---------------------------------------------------------------------------
# Repo-relative datas that MAY be bundled (explicit allowlist)
# ---------------------------------------------------------------------------

ALLOWED_DATAS: tuple[tuple[str, str], ...] = (
    ("config/commercial_release.json", "config"),
    # (source relative to repo root, destination inside bundle)
    ("templates", "templates"),
    ("packaging/native-current.json", "."),
    ("config/profile.yaml.example", "config"),
    ("config/application_profile.yaml.example", "config"),
    ("config/settings.yaml.example", "config"),
    ("assets/brand", "assets/brand"),
    # Public installed-app identity; never a user token or service account key.
    ("assets/oauth/desktop_client.json", "assets/oauth"),
    ("data/geo", "data/geo"),
    # Optional embed (slow onefile extract). Prefer sidecar next to EXE —
    # enabled only when KARRIEREKRAKE_EMBED_CV_MODEL_IN_EXE=1.
    # ("vendor/cv_model/qwen3.5-4b", "models/qwen3.5-4b"),
    ("NOTICE", "."),
    ("LICENSE", "."),
)

# Private CI inputs provisioned before packaging, absent from a clean checkout.
BUILD_PROVISIONED_DATAS = ("assets/oauth/desktop_client.json", "packaging/native-current.json")

# First-party Python packages that may be collected as hiddenimports.
ALLOWED_FIRST_PARTY_PREFIXES: tuple[str, ...] = (
    "app",
    "apply",
    "browser",
    "core",
    "desktop",
    "guenther",
    "integrations",
    "search",
)

# Command-line front ends of libraries the app uses as libraries only, and what only they need: rich, pygments,
# click, markdown_it, mdurl (terminal output), setuptools/pkg_resources (building packages) and
# pydoc_data (help() texts). About 4 MB of the 20 MB Python archive (Windows build 2026-11-15). Every other
# packaged module imports the same with these hidden (tests/test_release_trim.py). "distutils" itself is not
# listed: on Python 3.12+ PyInstaller's own hook maps it to setuptools._distutils and fails the build when the
# name is already excluded; with setuptools out, that alias points nowhere and nothing is collected.
UNUSED_TOOL_MODULES: tuple[str, ...] = (
    "httpx._main",
    "docpick.cli",
    "ddgs.cli",
    "ddgs.api_server",
    "dotenv.cli",
    "google_auth_oauthlib.tool",
    "rich",
    "pygments",
    "click",
    "markdown_it",
    "mdurl",
    "setuptools",
    "pkg_resources",
    "_distutils_hack",
    "pydoc_data",
)

# First-party modules that must NEVER ship (even under allowed prefixes).
EXCLUDED_FIRST_PARTY_MODULES: tuple[str, ...] = (
    "desktop.demo_data",
    "integrations.calendar.microsoft",
    "llama_cpp.server",
    "benchmark",
    "tools",
    "tools.cover_opt",
    "tests",
    *UNUSED_TOOL_MODULES,
)

# Third-party packages we intentionally collect_all / pull binaries for.
# Documented: playwright Python driver only,
# llama_cpp (native libllama / ggml for offline CV import + writing).
ALLOWED_COLLECT_ALL_PACKAGES: tuple[str, ...] = (
    # Explicit stdlib closure for the downloaded/frozen application.
    "certifi",
    "random",
    "secrets",
    "keyring",
    "ddgs",
    "playwright",
    "playwright_stealth",
    "llama_cpp",
)

# Extra hiddenimports (third-party) that Analysis may need.
ALLOWED_THIRD_PARTY_HIDDEN: tuple[str, ...] = (
    # Account secrets need the dynamically discovered Windows credential backend.
    "keyring",
    "keyring.backends.Windows",
    "keyring.backends.macOS",
    "keyring.backends.SecretService",
    "win32ctypes",
    "app.main",
    "browser.browser_manager",
    "playwright",
    "yaml",
    "PySide6",
    "numpy",
    "lxml",
    "bs4",
    # Productive CV import (Docpick + in-process llama.cpp; Docling not shipped).
    "docpick",
    "docpick.llm",
    "docpick.llm.vllm_provider",
    "docpick.llm.prompt",
    "docpick.llm.base",
    "llama_cpp",
    "llama_cpp.llama",
    # Lazy `import psutil` in core.cv_llm_runtime._psutil_cpu_count. Analysis of
    # app.py does not see a top-level import; these names force the bundle,
    # including the Windows extension the noconsole EXE must load.
    "psutil",
    "psutil._pswindows",
    "psutil._psutil_windows",
)

# Always excluded from Analysis (dev / unused UI stacks).
ANALYSIS_EXCLUDES: tuple[str, ...] = (
    "tls_client",  # retired Go transport; search now uses our own requests clients
    "integrations.calendar.microsoft",
    "llama_cpp.server",
    "dspy",
    "litellm",
    "boto3",
    "botocore",
    "s3transfer",
    "jmespath",
    "matplotlib",
    "tkinter",
    "readline",  # GUI app; only consumer of libreadline/libtinfo in the Linux bundle
    "pytest",
    "pytest_qt",
    "hypothesis",
    "benchmark",
    "tools",
    "tools.cover_opt",
    "tests",
    "desktop.demo_data",
    "streamlit",
    "IPython",
    "notebook",
    # numpy 2 loads these only when someone asks for them; llama_cpp and the app use arrays, argmax and
    # ctypes views, nothing else (tests/test_release_trim.py holds that).
    "numpy.random",
    "numpy.fft",
    "numpy.ma",
    "numpy.polynomial",
    "numpy.f2py",
    "numpy.testing",
    # Pillow comes with pypdf and Docpick (page images); nothing reads AVIF images, and its codec is 7.5 MB.
    # Pillow imports it guarded, so without it only AVIF support is missing (tests/test_release_trim.py).
    "PIL._avif",
    "PIL.AvifImagePlugin",
    *UNUSED_TOOL_MODULES,
)

# dateparser holds date words for about 200 languages, one module each, loaded only for the languages a
# call names. Its one caller, integrations/proposal_parse.py, names these two (about 370 KB of the others).
DATEPARSER_LANGUAGES: tuple[str, ...] = ("de", "en")


def analysis_excludes() -> list[str]:
    """ANALYSIS_EXCLUDES plus the dateparser language tables nothing asks for (read from the installed package)."""
    import importlib.util

    out = list(ANALYSIS_EXCLUDES)
    spec = importlib.util.find_spec("dateparser")
    if spec is None or not spec.submodule_search_locations:
        return out
    tables = Path(list(spec.submodule_search_locations)[0]) / "data" / "date_translation_data"
    for path in sorted(tables.glob("*.py")):
        if path.stem != "__init__" and path.stem not in DATEPARSER_LANGUAGES:
            out.append(f"dateparser.data.date_translation_data.{path.stem}")
    return out

# ---------------------------------------------------------------------------
# Forbidden markers — any TOC / extracted path matching these FAILS the gate
# ---------------------------------------------------------------------------

FORBIDDEN_PATH_MARKERS: tuple[str, ...] = (
    # Analysis excludes do not cover Python files copied by collect_all.
    "/llama_cpp/server/",
    "llama_cpp.server",
    "/tests/",
    "\\tests\\",
    "/benchmark/",
    "\\benchmark\\",
    "/tools/cover_opt/",
    "\\tools\\cover_opt\\",
    "/blindset",
    "\\blindset",
    "/goldset",
    "\\goldset",
    "/gold_set",
    "\\gold_set",
    "/.cursor/",
    "\\.cursor\\",
    "/agent-tools/",
    "\\agent-tools\\",
    "cover_specialization",
    "guenther_final_model_shootout",
    "model_tournament_raw",
    "fictional_emails",
    "cv_corpus/",
    "profile_migration/",
    # Match module/file demo_data, not arbitrary substrings
    "/demo_data",
    "demo_data.py",
    "demo_data/",
    "ms-playwright",
    # App log dirs only — NOT botocore/data/logs (AWS API model; justified FP note)
    "/Karrierekrake/logs/",
    "\\Karrierekrake\\logs\\",
    ".pytest_cache",
    ".hypothesis",
)

# Dotenv paths — matched with boundary checks (avoid '.environment_vars' FP)
DOTENV_PATH_SUFFIXES: tuple[str, ...] = (
    "/.env",
    "\\.env",
    "/.env.local",
    "/.env.production",
    "/.env.development",
)

# Relative tops that must not appear as bundled first-party trees
FORBIDDEN_TOP_LEVEL_PREFIXES: tuple[str, ...] = (
    "tests/",
    "benchmark/",
    "tools/cover_opt/",
    "logs/",
    ".cursor/",
    "agent-tools/",
)

FORBIDDEN_BASENAME_GLOBS: tuple[str, ...] = (
    ".env",
    ".env.local",
    ".env.production",
    "jobs.db",
    "jobs.db-wal",
    "jobs.db-shm",
    "oauth_*.json",
    "token.json",
    "credentials.json",
    "client_secret*.json",
    "gmail_credentials.json",
)

# Content substrings that block release when found in *first-party* text members.
# Vendor discovery docs (googleapiclient, botocore examples, playwright stubs) are
# path-scanned only — see FALSE_POSITIVE_NOTES. Do not disable the scanner.
FORBIDDEN_CONTENT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("begin_private_key", "-----BEGIN PRIVATE KEY-----"),
    ("begin_rsa_private", "-----BEGIN RSA PRIVATE KEY-----"),
    ("aws_access_key_id", "AKIA"),  # matched with AKIA[0-9A-Z]{16} in scanner
    ("openai_sk", "sk-proj-"),
    ("openai_sk_legacy", "sk-"),  # matched with sk-[A-Za-z0-9]{20,} in scanner
)

# TOC path prefixes that receive *content* (email/secret) scanning.
# Everything else is still subject to forbidden *path* markers.
FIRST_PARTY_CONTENT_PREFIXES: tuple[str, ...] = (
    "app/",
    "apply/",
    "browser/",
    "core/",
    "desktop/",
    "guenther/",
    "integrations/",
    "search/",
    "templates/",
    "config/",
    "assets/",
    "app.",
    "apply.",
    "browser.",
    "core.",
    "desktop.",
    "guenther.",
    "integrations.",
    "search.",
)

FALSE_POSITIVE_NOTES: dict[str, str] = {
    "config/settings.yaml.example:gmail_credentials_path": (
        "Example path string pointing at gitignored private/; no secret payload."
    ),
    "playwright driver package": (
        "Python playwright package is allowed; ms-playwright browser trees are forbidden."
    ),
    "curl_cffi collect_all": (
        "JobSpy 1.3 transport; legacy Go tls_client is excluded."
    ),
    "botocore/data/logs": (
        "AWS botocore service model for CloudWatch Logs API — not application log files. "
        "Generic '/logs/' marker intentionally narrowed to avoid this FP."
    ),
    "google.auth.environment_vars": (
        "Module name contains '.env' as a substring of '.environment'; dotenv matching uses path boundaries."
    ),
    "googleapiclient/discovery_cache": (
        "Upstream Google API discovery JSON may mention example emails / PEM headers as schema "
        "documentation. Path gate still applies; content email/secret scan is first-party only."
    ),
    "botocore/data/*/examples": (
        "AWS botocore example payloads may contain the AKIA prefix as documentation, not live keys."
    ),
    "jobspy/model.py AKIA": (
        "python-jobspy model field docs may mention AWS key shape; content scan is first-party only."
    ),
    "playwright/_generated.py @microsoft.com": (
        "Generated Playwright API stubs reference Microsoft docs emails; not applicant PII."
    ),
}


class PolicyHit(NamedTuple):
    kind: str
    path: str
    detail: str


def is_first_party_content_path(path: str) -> bool:
    """True if path should receive email/secret *content* scanning.

    Vendor trees (googleapiclient discovery JSON, botocore examples, playwright
    stubs) are still checked for forbidden *path* markers, but their embedded
    documentation emails / example key shapes are documented FPs — not live PII.
    """
    lower = normalize_path(path).lstrip("/").lower()
    for strip in ("pyz-00.pyz/", "pyz.pyz/", "base_library.zip/"):
        if lower.startswith(strip):
            lower = lower[len(strip) :]
    base = lower.rsplit("/", 1)[-1]
    if base in {"notice", "license", "license.txt", "notice.txt", "license.md"}:
        return True
    if lower in {"notice", "license"}:
        return True
    for prefix in FIRST_PARTY_CONTENT_PREFIXES:
        p = prefix.lower()
        if lower.startswith(p):
            return True
        dotted = p.rstrip("./").replace("/", ".")
        if lower == dotted or lower.startswith(dotted + ".") or lower.startswith(dotted + "/"):
            return True
    return False


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def module_allowed(module: str) -> bool:
    """Return True if a hiddenimport / submodule name may ship."""
    name = module.strip()
    if not name:
        return False
    # JobSpy 1.3 no longer needs this obsolete Go transport. Reject a stale
    # build-environment copy as well as its pseudo-module shared libraries.
    if name == "tls_client" or name.startswith("tls_client."):
        return False
    for excluded in EXCLUDED_FIRST_PARTY_MODULES:
        if name == excluded or name.startswith(excluded + "."):
            return False
    for prefix in ALLOWED_FIRST_PARTY_PREFIXES:
        if name == prefix or name.startswith(prefix + "."):
            return True
    # Third-party: allow if listed or under collect_all packages
    if name in ALLOWED_THIRD_PARTY_HIDDEN:
        return True
    for pkg in ALLOWED_COLLECT_ALL_PACKAGES:
        if name == pkg or name.startswith(pkg + "."):
            return True
    # Other third-party modules pulled transitively are OK unless forbidden marker
    lower = name.lower()
    if any(x in lower for x in ("pytest", "hypothesis", "benchmark", "cover_opt")):
        return False
    return True  # transitive third-party; path scan still applies


def filter_hiddenimports(modules: Iterable[str]) -> list[str]:
    return [m for m in modules if module_allowed(m)]


def datas_entry_allowed(src: str, dest: str = "") -> bool:
    """Allowlist check for a PyInstaller datas tuple source path."""
    norm = normalize_path(src)
    allowed = list(ALLOWED_DATAS) + [("vendor/cv_model/qwen3.5-4b", "models/qwen3.5-4b")]
    # Absolute or relative: match against allowed source suffixes
    for allowed_src, allowed_dest in allowed:
        allowed_norm = normalize_path(allowed_src)
        if norm.endswith("/" + allowed_norm) or norm.endswith(allowed_norm) or allowed_norm in norm:
            # Dest should match expected when provided
            if dest and normalize_path(dest) not in {
                normalize_path(allowed_dest),
                normalize_path(allowed_dest) + "/" + allowed_norm.split("/")[-1],
            }:
                # Dest mismatch is soft — still allow if src matches allowlist
                pass
            return True
    # Third-party package datas (site-packages) — allowed unless forbidden marker
    if "site-packages" in norm or "dist-packages" in norm:
        return not path_has_forbidden_marker(norm)
    return False


def path_has_forbidden_marker(path: str) -> bool:
    norm = "/" + normalize_path(path).lstrip("/").lower()
    rel = normalize_path(path).lstrip("/").lower()
    base = rel.rsplit("/", 1)[-1]
    for prefix in FORBIDDEN_TOP_LEVEL_PREFIXES:
        if rel.startswith(prefix.lower()):
            return True
    # Dotenv: exact file or /.env. suffix — not '.environment_vars'
    for suffix in DOTENV_PATH_SUFFIXES:
        s = normalize_path(suffix).lower()
        if norm == s or norm.endswith(s):
            return True
        if s + "." in norm or s + "/" in norm:
            return True
    if not native_dependency_allowed(path):
        return True
    for marker in FORBIDDEN_PATH_MARKERS:
        m = normalize_path(marker).lower()
        if m.startswith("/"):
            if m in norm or norm.endswith(m.rstrip("/")):
                return True
        elif m in norm:
            return True
    for pattern in FORBIDDEN_BASENAME_GLOBS:
        if _basename_matches(base, pattern.lower()):
            return True
    return False


def _basename_matches(name: str, pattern: str) -> bool:
    if "*" not in pattern:
        return name == pattern
    # simple glob: prefix*suffix
    if pattern.startswith("*") and pattern.endswith("*"):
        return pattern.strip("*") in name
    if pattern.startswith("*"):
        return name.endswith(pattern[1:])
    if pattern.endswith("*"):
        return name.startswith(pattern[:-1])
    # mid star
    left, right = pattern.split("*", 1)
    return name.startswith(left) and name.endswith(right)


def scan_paths(paths: Iterable[str]) -> list[PolicyHit]:
    hits: list[PolicyHit] = []
    for raw in paths:
        p = normalize_path(str(raw))
        if path_has_forbidden_marker(p):
            hits.append(PolicyHit(kind="forbidden_path", path=p, detail="matches forbidden marker"))
    return hits


def native_dependency_allowed(src: str, *, os_name: str | None = None, machine: str | None = None) -> bool:
    """Exclude the retired Go transport even from a reused build environment."""
    normalized = normalize_path(src).lower()
    parts = normalized.split('/')
    return ('tls_client' not in parts
            and not (parts[-1].startswith('tls-client-')
                     and parts[-1].endswith(('.dll', '.so', '.dylib'))))


def filter_collect_all_datas(
    datas: list[tuple],
) -> list[tuple]:
    """Drop forbidden trees from collect_all results (ms-playwright, tests, …)."""
    out: list[tuple] = []
    for item in datas:
        src = str(item[0]) if item else ""
        dest = str(item[1]) if item and len(item) > 1 else ""
        combined = f"{src}|{dest}"
        if any(path_has_forbidden_marker(path) for path in (src, dest, combined)) or not native_dependency_allowed(src):
            continue
        if "chromium" in normalize_path(src).lower() and "playwright" in normalize_path(src).lower():
            continue
        out.append(item)
    return out


def filter_collect_all_binaries(binaries: list[tuple]) -> list[tuple]:
    out: list[tuple] = []
    for item in binaries:
        src = str(item[0]) if item else ""
        if path_has_forbidden_marker(src) or not native_dependency_allowed(src):
            continue
        out.append(item)
    return out


def build_repo_datas(root: str) -> list[tuple[str, str]]:
    """Materialize allowlisted datas as absolute (src, dest) for the spec."""
    import os

    datas: list[tuple[str, str]] = []
    entries: list[tuple[str, str]] = list(ALLOWED_DATAS)
    embed = (os.environ.get("KARRIEREKRAKE_EMBED_CV_MODEL_IN_EXE") or "").strip().lower()
    if embed in {"1", "true", "yes"}:
        # Optional: embed GGUF into onefile (slow cold extract). Prefer sidecar.
        entries.append(("vendor/cv_model/qwen3.5-4b", "models/qwen3.5-4b"))
    for rel, dest in entries:
        src = os.path.join(root, *rel.split("/"))
        if os.path.exists(src):
            datas.append((src, dest))
    return datas


def require_bundled_cv_model(root: str) -> str:
    """Return absolute GGUF path or raise SystemExit when release build demands it.

    Set ``KARRIEREKRAKE_REQUIRE_BUNDLED_CV_MODEL=1`` (Windows release CI) so a
    build without the offline model cannot ship. Default layout: prepare vendor
    GGUF then copy as ``dist/models/…`` sidecar beside the EXE (same install
    folder). Optional embed into the EXE archive via
    ``KARRIEREKRAKE_EMBED_CV_MODEL_IN_EXE=1``.
    """
    import os

    flag = (os.environ.get("KARRIEREKRAKE_REQUIRE_BUNDLED_CV_MODEL") or "").strip().lower()
    if flag not in {"1", "true", "yes"}:
        return ""
    rel = "vendor/cv_model/qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf"
    path = os.path.join(root, *rel.split("/"))
    if not os.path.isfile(path):
        raise SystemExit(
            "Production content policy: bundled CV model missing at "
            f"{rel!r}. Run scripts/prepare_bundled_cv_model.py before PyInstaller."
        )
    size = os.path.getsize(path)
    if size < 1_000_000_000:  # ~1 GiB floor — Q4_K_M is ~2.5 GiB
        raise SystemExit(
            f"Production content policy: bundled CV model too small ({size} bytes) at {rel!r}"
        )
    return path


def release_data_allowed(path: str) -> bool:
    """Only Gmail/Calendar static discovery schemas belong in the release."""
    norm = normalize_path(path).lower()
    marker = "googleapiclient/discovery_cache/documents/"
    if marker in norm:
        return norm.rsplit("/", 1)[-1] in {"gmail.v1.json", "calendar.v3.json"}
    return True


# Qt parts the widget application never loads: QML/Quick, the PDF module, the on-screen keyboard, the software
# OpenGL renderer and spare platform plugins. PyInstaller's PySide6 hook collects them with every Qt program.
# Windows only: the trimmed program was started there on both the normal and the offscreen platform.
_UNUSED_QT_WINDOWS = frozenset({
    "pyside6/opengl32sw.dll",
    "pyside6/qt6quick.dll", "pyside6/qt6qml.dll", "pyside6/qt6qmlmeta.dll", "pyside6/qt6qmlmodels.dll",
    "pyside6/qt6qmlworkerscript.dll", "pyside6/qt6pdf.dll", "pyside6/qt6virtualkeyboard.dll",
    "pyside6/qt6opengl.dll",
    "pyside6/plugins/imageformats/qpdf.dll",
    "pyside6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
    "pyside6/plugins/platforms/qdirect2d.dll", "pyside6/plugins/platforms/qminimal.dll",
    "pyside6/plugins/generic/qtuiotouchplugin.dll",
})
# The same parts on Linux. Read from the DT_NEEDED entries of the built package (2026-11-15): only these files
# and the QML/PDF/keyboard plugins below need them. PyInstaller also links each library into the top folder.
_UNUSED_QT_LINUX_LIBS = ("quick", "qml", "qmlmeta", "qmlmodels", "qmlworkerscript", "pdf", "virtualkeyboard",
                         "virtualkeyboardqml")
_UNUSED_QT_LINUX = frozenset(
    [f"pyside6/qt/lib/libqt6{name}.so.6" for name in _UNUSED_QT_LINUX_LIBS]
    + [f"libqt6{name}.so.6" for name in _UNUSED_QT_LINUX_LIBS]
    + ["pyside6/qt/plugins/imageformats/libqpdf.so",
       "pyside6/qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so"]
)
# llama.cpp on Linux: Python opens libllama.so and libggml.so by these names, and they need libggml.so.0,
# libggml-base.so.0 and libggml-cpu.so.0. The wheel holds each library up to three times (libX.so, libX.so.0,
# libX.so.0.20.0, symlinks resolved to copies); libllama.so.0 is needed only by libmtmd.
_LLAMA_LINUX_KEPT = frozenset({"libllama.so", "libggml.so", "libggml.so.0", "libggml-base.so.0", "libggml-cpu.so.0"})
# Never used here, on every system: the image/audio part of llama.cpp (mtmd: only llama_cpp's LLaVA chat handler
# opens it), Windows linker import libraries (.lib), Playwright's TypeScript declarations, and brand artwork no
# window shows (desktop/branding.py: the dialogs use the logo master, window and tray the 256 px and smaller icons).
_UNUSED_BRAND = frozenset({
    "assets/brand/social-preview.png", "assets/brand/karrierekrake-app-icon-master.png",
    "assets/brand/logo.png", "assets/brand/icons/icon-1024.png", "assets/brand/icons/icon-512.png",
})


# macOS (release SBOM of efb7dcf5): the same Qt parts as frameworks, and llama.cpp again as libX.dylib,
# libX.0.dylib and libX.0.20.0.dylib copies. Kept: the two names Python opens and the SOVERSION names the
# libraries load each other by (@rpath/libX.0.dylib), libllama.0.dylib only by mtmd. The packaged program
# loads the real model twice in CI (package-model-setup), which checks this.
_UNUSED_QT_MAC_FRAMEWORKS = re.compile(
    r"(?:^|/)qt(?:" + "|".join(_UNUSED_QT_LINUX_LIBS) + r")\.framework(?:/|$)")
_UNUSED_QT_MAC_PLUGINS = frozenset({
    "pyside6/qt/plugins/imageformats/libqpdf.dylib",
    "pyside6/qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.dylib",
})


def _unused_mac(norm: str) -> bool:
    if norm in _UNUSED_QT_MAC_PLUGINS or _UNUSED_QT_MAC_FRAMEWORKS.search(norm):
        return True
    name = norm.rsplit("/", 1)[-1]
    if not (norm.startswith("llama_cpp/lib/") and name.endswith(".dylib")):
        return name == "libllama.0.dylib"
    if name in {"libllama.dylib", "libggml.dylib"}:
        return False
    return not re.fullmatch(r"lib[a-z0-9-]+\.0\.dylib", name) or name == "libllama.0.dylib"


def _unused_everywhere(norm: str) -> bool:
    name = norm.rsplit("/", 1)[-1]
    if norm.startswith("llama_cpp/lib/") and (name.startswith(("mtmd", "libmtmd")) or name.endswith(".lib")):
        return True
    return norm.startswith("playwright/driver/package/types/") or norm in _UNUSED_BRAND


def _unused_linux(norm: str) -> bool:
    if norm in _UNUSED_QT_LINUX or norm == "libllama.so.0":
        return True
    if norm.startswith("llama_cpp/lib/") and ".so" in norm:
        return norm.rsplit("/", 1)[-1] not in _LLAMA_LINUX_KEPT
    return False


# The interface is German and English; Qt's own texts (dialog buttons) are needed in those two languages only.
_KEPT_QT_TRANSLATIONS = frozenset({"qtbase_de.qm", "qtbase_en.qm", "qt_de.qm", "qt_en.qm"})


def lean_bundle_allowed(dest: str, *, os_name: str | None = None) -> bool:
    """False for bundled Qt files the program does not use (``dest`` is the path inside the package)."""
    import sys

    norm = normalize_path(dest).lower()
    if "/translations/" in norm and norm.startswith("pyside6/") and norm.endswith(".qm"):
        return norm.rsplit("/", 1)[-1] in _KEPT_QT_TRANSLATIONS
    if _unused_everywhere(norm):
        return False
    system = os_name or sys.platform
    if system == "win32":
        return norm not in _UNUSED_QT_WINDOWS
    if system.startswith("linux"):
        return not _unused_linux(norm)
    if system == "darwin":
        return not _unused_mac(norm)
    return True
