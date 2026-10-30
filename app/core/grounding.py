"""Repository grounding: locate real code targets before any patch is proposed.

Prevents agents from inventing fixes in README.md or other non-executable
files when the reported function, class, or module is not in the repository.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.rag.scanner import IGNORED_DIRECTORIES

DEFECT_TARGET_NOT_FOUND = (
    "Defect target not found in repository. No code modifications possible."
)

MISSING_CODE_GUIDANCE = (
    "The bug report names behavior that is not present as source code in the "
    "selected repository. Point Atlas at the project that contains the relevant "
    "implementation, or rewrite the report to match existing files, classes, "
    "and functions."
)

QA_FILE_TYPE_REJECT = (
    "QA rejected the proposed patch: modified file type does not match the "
    "nature of the bug report. Application-logic defects cannot be fixed by "
    "editing documentation or data files."
)

SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".mjs",
    ".cjs",
    ".java",
    ".go",
    ".rs",
    ".cpp",
    ".cc",
    ".c",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".kt",
    ".swift",
    ".scala",
}

DOCUMENT_EXTENSIONS = {".md", ".markdown", ".rst", ".txt", ".adoc"}
DATA_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
NON_EXECUTABLE_FOR_LOGIC = DOCUMENT_EXTENSIONS | {".json"}

STOPWORDS = {
    "the",
    "and",
    "this",
    "that",
    "with",
    "from",
    "when",
    "they",
    "have",
    "been",
    "were",
    "will",
    "their",
    "which",
    "then",
    "than",
    "your",
    "issue",
    "title",
    "description",
    "repository",
    "expected",
    "actual",
    "error",
    "returns",
    "instead",
    "fails",
    "failing",
    "failed",
    "bug",
    "fix",
    "code",
    "file",
    "files",
    "function",
    "class",
    "method",
    "module",
    "should",
    "would",
    "could",
    "does",
    "doesn",
    "accepts",
    "accept",
    "any",
    "user",
    "users",
    "what",
    "happened",
    "behavior",
    "traceback",
    "stack",
    "trace",
    "optional",
    "please",
    "project",
    "empty",
    "input",
    "inputs",
    "unexpected",
    "returning",
    "return",
    "false",
    "true",
    "none",
    "null",
    "raises",
    "raise",
}

DOC_HINTS = (
    "readme",
    "documentation",
    "docs site",
    "markdown",
    "typo in readme",
    "update the docs",
    "changelog",
)
CODE_HINTS = (
    "traceback",
    "exception",
    "stack trace",
    "function",
    "method",
    "class ",
    "login",
    "auth",
    "password",
    "crash",
    "returns",
    "expected",
    "actual",
    "nullpointer",
    "typeerror",
    "valueerror",
    "endpoint",
    "api",
    "unittest",
    "pytest",
)
CONFIG_HINTS = (
    "config file",
    "configuration",
    "settings.json",
    "package.json",
    "yaml",
    "env var",
)

_FILE_RE = re.compile(
    r"[\w./\\-]+\.(?:py|js|ts|tsx|jsx|mjs|cjs|java|go|rs|cpp|c|h|hpp|cs|rb|php|kt|swift)\b",
    re.IGNORECASE,
)
_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")
_SNAKE_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_CAMEL_RE = re.compile(r"\b[A-Z][a-zA-Z0-9]*[A-Z][A-Za-z0-9]*\b")
_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\s*\(")
_QUOTED_RE = re.compile(r"['\"`]([A-Za-z_][\w./-]{1,80})['\"`]")
_DIFF_PATH_RE = re.compile(
    r"^(?:diff --git a/(.+?) b/.+|--- a/(.+)|--- (.+)|(?:\+\+\+) b/(.+)|(?:\+\+\+) (.+))$",
    re.MULTILINE,
)
_JS_SYMBOL_RE = re.compile(
    r"\b(?:export\s+)?(?:async\s+)?(?:function|class|def)\s+([A-Za-z_]\w*)"
    r"|\b(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?(?:\(|function)"
)
_GO_SYMBOL_RE = re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)")


class DefectTargetNotFound(ValueError):
    """Raised when the reported defect cannot be located in source files."""

    def __init__(self, message: str = DEFECT_TARGET_NOT_FOUND) -> None:
        super().__init__(message)


class PatchTypeMismatch(ValueError):
    """Raised when a patch edits files that cannot fix the reported defect."""

    def __init__(self, message: str = QA_FILE_TYPE_REJECT) -> None:
        super().__init__(message)


@dataclass
class LocatedSymbol:
    path: str
    name: str
    kind: str
    start_line: int = 1


@dataclass
class TargetSearchResult:
    found: bool
    nature: str
    files: list[str] = field(default_factory=list)
    symbols: list[LocatedSymbol] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    reason: str = ""


def is_source_file(path: str | Path) -> bool:
    return Path(str(path).split("?")[0]).suffix.lower() in SOURCE_EXTENSIONS


def is_document_file(path: str | Path) -> bool:
    name = Path(str(path)).name.lower()
    suffix = Path(str(path)).suffix.lower()
    return suffix in DOCUMENT_EXTENSIONS or name == "readme"


def is_disallowed_logic_patch_file(path: str | Path) -> bool:
    suffix = Path(str(path)).suffix.lower()
    name = Path(str(path)).name.lower()
    return suffix in NON_EXECUTABLE_FOR_LOGIC or name.startswith("readme")


def classify_issue_nature(title: str, description: str = "") -> str:
    text = f"{title}\n{description}".lower()
    doc_hits = sum(1 for hint in DOC_HINTS if hint in text)
    code_hits = sum(1 for hint in CODE_HINTS if hint in text)
    config_hits = sum(1 for hint in CONFIG_HINTS if hint in text)
    if code_hits and code_hits >= doc_hits and code_hits >= config_hits:
        return "code"
    if doc_hits > code_hits and doc_hits >= config_hits:
        return "docs"
    if config_hits > code_hits and config_hits > doc_hits:
        return "config"
    return "code"


def extract_search_terms(*parts: str) -> list[str]:
    text = " ".join(part for part in parts if part)
    terms: list[str] = []

    for match in _FILE_RE.findall(text):
        terms.append(match.replace("\\", "/"))
        terms.append(Path(match).stem)

    for match in _QUOTED_RE.findall(text):
        terms.append(match)
        terms.append(Path(match).stem)

    for match in _SNAKE_RE.findall(text):
        terms.append(match)

    for match in _CAMEL_RE.findall(text):
        terms.append(match)

    for match in _CALL_RE.findall(text):
        if match.lower() not in STOPWORDS:
            terms.append(match)

    for raw in _IDENT_RE.findall(text):
        lowered = raw.lower()
        if lowered in STOPWORDS or len(raw) < 4:
            continue
        if raw[0].isupper() or len(raw) >= 5:
            terms.append(raw)

    normalized: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.replace("\\", "/").lower().strip("./")
        if not key or key in seen or key in STOPWORDS:
            continue
        seen.add(key)
        normalized.append(term.replace("\\", "/"))
    return normalized


def retrieval_queries(title: str, description: str = "", analysis_queries: list[str] | None = None) -> list[str]:
    text = f"{title}\n{description}"
    focused: list[str] = []
    for match in list(_FILE_RE.findall(text)) + list(_SNAKE_RE.findall(text)) + list(_CAMEL_RE.findall(text)):
        focused.append(match.replace("\\", "/"))
    for match in _CALL_RE.findall(text):
        if match.lower() not in STOPWORDS:
            focused.append(match)
    combined: list[str] = []
    seen: set[str] = set()
    for item in list(analysis_queries or []) + focused + ([title] if title else []):
        key = item.strip().lower()
        if not key or key in seen or key in STOPWORDS:
            continue
        seen.add(key)
        combined.append(item.strip())
        if len(combined) >= 6:
            break
    return combined or ([title] if title else ["bug"])


def allowed_extensions_for_nature(nature: str) -> set[str]:
    if nature == "docs":
        return DOCUMENT_EXTENSIONS
    if nature == "config":
        return DATA_EXTENSIONS
    return SOURCE_EXTENSIONS


def parse_patch_paths(patch: str) -> list[str]:
    if not patch or not patch.strip():
        return []
    found: list[str] = []
    for line in patch.splitlines():
        stripped = line.strip()
        path = ""
        if stripped.startswith("diff --git "):
            parts = stripped.split()
            if len(parts) >= 4:
                path = parts[2]
                if path.startswith("a/"):
                    path = path[2:]
        elif stripped.startswith("--- ") or stripped.startswith("+++ "):
            path = stripped[4:].strip()
            if path in {"/dev/null", ""}:
                continue
            if path.startswith("a/") or path.startswith("b/"):
                path = path[2:]
        if path and path not in found:
            found.append(path)
    return found


def assert_patch_matches_nature(
    patch: str,
    affected_files: list[str] | None = None,
    *,
    nature: str = "code",
) -> list[str]:
    paths = list(dict.fromkeys((affected_files or []) + parse_patch_paths(patch)))
    if nature == "docs":
        allowed = DOCUMENT_EXTENSIONS
        label = "documentation"
    elif nature == "config":
        allowed = DATA_EXTENSIONS
        label = "configuration"
    else:
        if not patch.strip() or not paths:
            raise DefectTargetNotFound(DEFECT_TARGET_NOT_FOUND)
        disallowed = [path for path in paths if is_disallowed_logic_patch_file(path)]
        if disallowed:
            raise PatchTypeMismatch(QA_FILE_TYPE_REJECT)
        not_source = [path for path in paths if not is_source_file(path)]
        if not_source:
            raise PatchTypeMismatch(QA_FILE_TYPE_REJECT)
        return paths

    bad = [path for path in paths if Path(path).suffix.lower() not in allowed]
    if bad:
        raise PatchTypeMismatch(
            f"QA rejected the proposed patch: modified file type does not match "
            f"the nature of the bug report ({label} expected)."
        )
    return paths


def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.exists() or not root.is_dir():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRECTORIES for part in path.parts):
            continue
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > 750_000:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def _symbols_for(path: Path, text: str) -> list[tuple[str, str, int]]:
    suffix = path.suffix.lower()
    found: list[tuple[str, str, int]] = []
    if suffix == ".py":
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    found.append((node.name, "class", int(getattr(node, "lineno", 1) or 1)))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                    found.append((node.name, kind, int(getattr(node, "lineno", 1) or 1)))
            return found
    if suffix in {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}:
        for match in _JS_SYMBOL_RE.finditer(text):
            name = match.group(1) or match.group(2)
            if name:
                line = text[: match.start()].count("\n") + 1
                found.append((name, "function", line))
        return found
    if suffix == ".go":
        for match in _GO_SYMBOL_RE.finditer(text):
            line = text[: match.start()].count("\n") + 1
            found.append((match.group(1), "function", line))
    return found


def locate_defect_targets(
    repository_path: str | Path,
    *,
    title: str,
    description: str = "",
    extra_queries: list[str] | None = None,
) -> TargetSearchResult:
    nature = classify_issue_nature(title, description)
    terms = extract_search_terms(title, description, *(extra_queries or []))
    root = Path(repository_path).expanduser().resolve()
    if nature != "code":
        return TargetSearchResult(found=True, nature=nature, terms=terms)

    if not terms:
        return TargetSearchResult(
            found=False,
            nature=nature,
            terms=terms,
            reason=DEFECT_TARGET_NOT_FOUND,
        )

    term_keys = {term.lower() for term in terms}
    matched_files: list[str] = []
    matched_symbols: list[LocatedSymbol] = []

    for path in _iter_source_files(root):
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = path.name
        stem = path.stem.lower()
        name = path.name.lower()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lowered = text.lower()
        file_hit = stem in term_keys or name in term_keys or relative.lower() in term_keys
        if file_hit and relative not in matched_files:
            matched_files.append(relative)

        for name_, kind, line in _symbols_for(path, text):
            if name_.lower() in term_keys:
                matched_symbols.append(
                    LocatedSymbol(path=relative, name=name_, kind=kind, start_line=line)
                )
                if relative not in matched_files:
                    matched_files.append(relative)

        if relative not in matched_files:
            hits = sum(
                1
                for key in term_keys
                if len(key) >= 5 and re.search(rf"\b{re.escape(key)}\b", lowered)
            )
            if hits >= 2:
                matched_files.append(relative)

    found = bool(matched_files or matched_symbols)
    return TargetSearchResult(
        found=found,
        nature=nature,
        files=matched_files,
        symbols=matched_symbols,
        terms=terms,
        reason="" if found else DEFECT_TARGET_NOT_FOUND,
    )


def filter_evidence_sources(sources: list, *, nature: str, allowed_files: list[str] | None = None):
    """Keep evidence whose path matches the issue nature and optional target files."""
    allowed_norm = {item.replace("\\", "/").lower() for item in (allowed_files or [])}
    kept = []
    for item in sources:
        source = getattr(item, "source", str(item))
        if nature == "code" and not is_source_file(source):
            continue
        if nature == "docs" and not is_document_file(source):
            continue
        if allowed_norm:
            name = Path(source).name.lower()
            rel = source.replace("\\", "/").lower()
            if rel not in allowed_norm and name not in {Path(p).name.lower() for p in allowed_norm}:
                continue
        kept.append(item)
    return kept


def snippets_for_targets(repository_path: str | Path, files: list[str], *, max_lines: int = 80):
    root = Path(repository_path).expanduser().resolve()
    snippets: list[tuple[str, str, int, int]] = []
    for rel in files:
        path = root / rel
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        excerpt = "\n".join(lines[:max_lines])
        if excerpt.strip():
            snippets.append((rel.replace("\\", "/"), excerpt, 1, min(len(lines), max_lines)))
    return snippets
