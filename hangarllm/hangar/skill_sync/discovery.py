"""Find Agent Skills in a repository archive and flag anything unexpected before it reaches the hub.

Each skill is validated in isolation so one broken or suspicious skill never blocks the others.
Errors quarantine the skill; warnings and info are reported but the skill is still applied.
"""

import io
import re
import stat
import zipfile
from collections import Counter
from dataclasses import dataclass
from typing import Final

from hangarllm.hangar.guardrails.secret_detection import SecretScanner
from hangarllm.hangar.skill_sync.types import SyncIssue
from hangarllm.proxy.discovery_endpoints.agent_skills_archive import (
    MAX_ARCHIVE_ENTRIES,
    MAX_ARCHIVE_UNPACKED_BYTES,
    MAX_SKILL_FILE_BYTES,
    SKILL_ARCHIVE_ERRORS,
    SKILL_MANIFEST_FILENAME,
    SkillArchive,
    agent_skill_frontmatter,
    build_agent_skill_archive,
)

MAX_REPO_SCOPE_ENTRIES: Final = 20_000
MAX_REPO_SCOPE_BYTES: Final = 500 * 1024 * 1024
_MAX_SCANNED_TEXT_BYTES: Final = 1024 * 1024
_NAME: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_BINARY_MAGIC: Final = (b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe")
_DANGEROUS: Final = (
    ("pipe_to_shell", re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b")),
    ("decode_and_execute", re.compile(r"base64\s+(?:-d|--decode)[^\n|]*\|\s*(?:ba|z)?sh\b")),
    ("reverse_shell", re.compile(r"/dev/tcp/|\bnc\b[^\n]*\s-e\s|\bsocat\b[^\n]*exec:")),
    ("destructive_delete", re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(?:/|~|\$HOME)(?:\s|$|/\*)")),
    ("credential_files", re.compile(r"(?:/etc/shadow|~/\.ssh/id_[a-z0-9]+|~/\.aws/credentials)")),
    ("eval_encoded", re.compile(r"\beval\s*\(\s*(?:base64|atob|codecs\.decode)")),
)
_INJECTION: Final = re.compile(
    r"ignore (?:all |any )?(?:the )?(?:previous|prior|above) instructions"
    r"|disregard (?:the |your )?(?:system prompt|previous instructions)"
    r"|do not (?:tell|inform) the user",
    re.IGNORECASE,
)
_SCANNER: Final = SecretScanner()
_GENERIC_SECRET_PATTERNS: Final = frozenset({"credential_assignment", "basic_auth_in_url", "bearer_header", "jwt"})
_DOC_SUFFIXES: Final = (".md", ".mdx", ".txt", ".rst", ".adoc", ".html")


@dataclass(frozen=True, slots=True)
class DiscoveredSkill:
    path: str
    archive: SkillArchive | None
    issues: tuple[SyncIssue, ...]

    @property
    def name(self) -> str | None:
        return None if self.archive is None else self.archive.declared_name

    @property
    def blocked(self) -> bool:
        return self.archive is None or any(i.severity == "error" for i in self.issues)


@dataclass(frozen=True, slots=True)
class Discovery:
    skills: tuple[DiscoveredSkill, ...]
    issues: tuple[SyncIssue, ...]


@dataclass(frozen=True, slots=True)
class DiscoveryFailure:
    message: str


def _issue(severity: str, code: str, message: str, file: str | None = None) -> SyncIssue:
    return SyncIssue.model_validate({"severity": severity, "code": code, "message": message, "file": file})


def _safe_rel(path: str) -> str | None:
    if not path or "\0" in path or "\\" in path or path.startswith("/"):
        return None
    parts: Final = tuple(p for p in path.split("/") if p)
    return None if not parts or any(p in (".", "..") for p in parts) else "/".join(parts)


def _repo_entries(archive: zipfile.ZipFile) -> tuple[tuple[zipfile.ZipInfo, str | None], ...]:
    infos: Final = tuple(info for info in archive.infolist() if not info.is_dir())
    roots: Final = frozenset(info.filename.split("/", 1)[0] for info in infos)
    strip: Final = len(roots) == 1 and all("/" in info.filename for info in infos)
    return tuple((info, _safe_rel(info.filename.split("/", 1)[1] if strip else info.filename)) for info in infos)


def _in_scope(path: str, skills_path: str) -> bool:
    return not skills_path or path == skills_path or path.startswith(f"{skills_path}/")


def _parent(path: str) -> str:
    return path.rpartition("/")[0]


def _is_under(path: str, root: str) -> bool:
    return not root or path.startswith(f"{root}/")


def _entry_issues(info: zipfile.ZipInfo, rel: str, content: bytes | None) -> tuple[SyncIssue, ...]:
    mode: Final = stat.S_IFMT(info.external_attr >> 16) if info.create_system == 3 else 0
    structural: Final = (
        *(
            (_issue("error", "symlink", "Symbolic links are not allowed in skills", rel),)
            if mode == stat.S_IFLNK
            else ()
        ),
        *((_issue("error", "encrypted_file", "Encrypted files are not allowed", rel),) if info.flag_bits & 1 else ()),
        *(
            (_issue("error", "file_too_large", "File is larger than 10 MiB", rel),)
            if info.file_size > MAX_SKILL_FILE_BYTES
            else ()
        ),
    )
    if structural or content is None:
        return structural
    if content.startswith(_BINARY_MAGIC):
        return (_issue("error", "binary_executable", "Compiled executables are not allowed in skills", rel),)
    return _text_issues(content, rel)


def _text_issues(content: bytes, rel: str) -> tuple[SyncIssue, ...]:
    if len(content) > _MAX_SCANNED_TEXT_BYTES:
        return ()
    try:
        text: Final = content.decode("utf-8")
    except UnicodeDecodeError:
        return ()
    found: Final = frozenset(name for name, _, _ in _SCANNER.find(text))
    specific: Final = sorted(found - _GENERIC_SECRET_PATTERNS)
    generic: Final = sorted(found & _GENERIC_SECRET_PATTERNS)
    dangerous: Final = tuple(code for code, pattern in _DANGEROUS if pattern.search(text))
    command_severity: Final = "warning" if rel.lower().endswith(_DOC_SUFFIXES) else "error"
    injection: Final = _INJECTION.search(text)
    return (
        *(
            (
                _issue(
                    "error",
                    "secret_detected",
                    f"Secret found ({', '.join(specific)}). Remove it from the repository and rotate it.",
                    rel,
                ),
            )
            if specific
            else ()
        ),
        *(
            (
                _issue(
                    "warning",
                    "possible_credential",
                    f"Looks like an inline credential ({', '.join(generic)}). Fine for examples, never for real values.",
                    rel,
                ),
            )
            if generic
            else ()
        ),
        *(
            _issue(command_severity, "dangerous_command", f"Dangerous command pattern: {code}", rel)
            for code in dangerous
        ),
        *(
            (_issue("warning", "prompt_injection_phrase", f"Suspicious instruction: '{injection.group(0)}'", rel),)
            if injection
            else ()
        ),
    )


def _manifest_issues(manifest: bytes, root: str) -> tuple[SyncIssue, ...]:
    frontmatter: Final = agent_skill_frontmatter(manifest)
    name: Final = frontmatter.get("name")
    description: Final = frontmatter.get("description")
    file: Final = f"{root}/{SKILL_MANIFEST_FILENAME}" if root else SKILL_MANIFEST_FILENAME
    if not frontmatter:
        return (
            _issue(
                "error", "invalid_manifest", "SKILL.md needs a YAML frontmatter block with name and description", file
            ),
        )
    return (
        *(
            (
                _issue(
                    "error",
                    "invalid_name",
                    "name must be lowercase letters, digits and hyphens, at most 64 chars",
                    file,
                ),
            )
            if not isinstance(name, str) or not _NAME.fullmatch(name) or len(name) > 64
            else ()
        ),
        *(
            (_issue("error", "invalid_description", "description is required and must be at most 1024 chars", file),)
            if not isinstance(description, str) or not description.strip() or len(description) > 1024
            else ()
        ),
    )


def _pack(members: tuple[tuple[str, bytes, int], ...]) -> bytes:
    buffer: Final = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
        for name, data, mode in members:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.create_system = 3
            out.writestr(info, data)
    return buffer.getvalue()


def _discover_one(
    archive: zipfile.ZipFile, root: str, entries: tuple[tuple[zipfile.ZipInfo, str], ...]
) -> DiscoveredSkill:
    own: Final = tuple((info, rel) for info, rel in entries if _is_under(rel, root))
    if len(own) > MAX_ARCHIVE_ENTRIES or sum(info.file_size for info, _ in own) > MAX_ARCHIVE_UNPACKED_BYTES:
        return DiscoveredSkill(
            root, None, (_issue("error", "skill_too_large", "Skill exceeds 1000 files or 50 MiB", root),)
        )
    readable: Final = tuple(
        (info, rel, archive.read(info) if info.file_size <= MAX_SKILL_FILE_BYTES and not info.flag_bits & 1 else None)
        for info, rel in own
    )
    issues: Final = tuple(issue for info, rel, data in readable for issue in _entry_issues(info, rel, data))
    manifest: Final = next(
        data for _, rel, data in readable if rel == (f"{root}/" if root else "") + SKILL_MANIFEST_FILENAME
    )
    manifest_issues: Final = _manifest_issues(manifest or b"", root)
    all_issues: Final = (*issues, *manifest_issues)
    if any(i.severity == "error" for i in all_issues):
        return DiscoveredSkill(root, None, all_issues)
    prefix: Final = f"{root}/" if root else ""
    members: Final = tuple(
        (rel[len(prefix) :], data, 0o755 if (info.external_attr >> 16) & 0o111 else 0o644)
        for info, rel, data in readable
        if data is not None
    )
    built: Final = build_agent_skill_archive(_pack(members))
    if built is None:
        return DiscoveredSkill(
            root, None, (*all_issues, _issue("error", "invalid_skill", "Not a valid Agent Skill archive", root))
        )
    folder: Final = root.rpartition("/")[2]
    mismatch: Final = (
        (
            _issue(
                "warning", "name_mismatch", f"Skill name '{built.declared_name}' differs from folder '{folder}'", root
            ),
        )
        if folder and built.declared_name != folder
        else ()
    )
    return DiscoveredSkill(root, built, (*all_issues, *mismatch))


def _with_duplicates(skills: tuple[DiscoveredSkill, ...]) -> tuple[DiscoveredSkill, ...]:
    counts: Final = Counter(s.name for s in skills if s.name is not None)
    return tuple(
        DiscoveredSkill(
            s.path,
            None,
            (
                *s.issues,
                _issue("error", "duplicate_name", f"Another folder also declares the skill '{s.name}'", s.path),
            ),
        )
        if s.name is not None and counts[s.name] > 1
        else s
        for s in skills
    )


def discover_skills(content: bytes, skills_path: str) -> Discovery | DiscoveryFailure:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return _discover(archive, skills_path)
    except SKILL_ARCHIVE_ERRORS:
        return DiscoveryFailure("The repository archive could not be read")


def _discover(archive: zipfile.ZipFile, skills_path: str) -> Discovery | DiscoveryFailure:
    all_entries: Final = _repo_entries(archive)
    unsafe: Final = tuple(info.filename for info, rel in all_entries if rel is None)
    entries: Final = tuple((info, rel) for info, rel in all_entries if rel is not None and _in_scope(rel, skills_path))
    if len(entries) > MAX_REPO_SCOPE_ENTRIES or sum(info.file_size for info, _ in entries) > MAX_REPO_SCOPE_BYTES:
        return DiscoveryFailure("The skills folder has more than 20,000 files or 500 MiB; narrow the skills path")
    if skills_path and not entries:
        return DiscoveryFailure(f"The folder '{skills_path}' does not exist in this commit")
    manifests: Final = sorted(rel for _, rel in entries if rel.rpartition("/")[2] == SKILL_MANIFEST_FILENAME)
    roots: Final = tuple(_parent(m) for m in manifests)
    top: Final = tuple(r for r in roots if not any(other != r and _is_under(r, other) for other in roots))
    nested: Final = tuple(r for r in roots if r not in top)
    lowercase: Final = tuple(
        rel
        for _, rel in entries
        if rel.rpartition("/")[2].lower() == "skill.md" and rel.rpartition("/")[2] != "SKILL.md"
    )
    skills: Final = _with_duplicates(tuple(_discover_one(archive, root, entries) for root in top))
    outside: Final = sum(1 for _, rel in entries if not any(_is_under(rel, r) for r in top))
    issues: Final = (
        *(
            _issue("error", "unsafe_path", "Archive entry with an unsafe path was ignored", name)
            for name in unsafe[:20]
        ),
        *(_issue("warning", "nested_skill", "Skills inside another skill folder are ignored", r) for r in nested),
        *(
            _issue("warning", "manifest_case", "Rename to SKILL.md (upper case) so it is detected", rel)
            for rel in lowercase
        ),
        *(
            (_issue("info", "files_outside_skills", f"{outside} file(s) outside skill folders were ignored"),)
            if outside and top
            else ()
        ),
        *(
            (
                _issue(
                    "warning",
                    "no_skills_found",
                    "No SKILL.md found. Check the skills folder setting (e.g. 'skills') and the branch.",
                ),
            )
            if not top
            else ()
        ),
    )
    return Discovery(skills=skills, issues=issues)
