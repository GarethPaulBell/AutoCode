"""Project- and shared-level persistence for AutoCode.

Standardizes DB discovery and adds optional SQLite backend while keeping
backward-compatible pickle support. Default is per-project DB at
".autocode/code_db.pkl" unless overridden by env or config.
"""
from __future__ import annotations

import json
import os
import pickle
import shutil
import sqlite3
import tempfile
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Literal, Optional, Tuple

# -------- Defaults & Env --------
AUTOCODE_DIRNAME = ".autocode"
DEFAULT_DB_BASENAME = "code_db"
DEFAULT_PICKLE_EXT = ".pkl"
DEFAULT_SQLITE_EXT = ".sqlite"

DEFAULT_MODE: Literal["project", "shared"] = "project"
DEFAULT_BACKEND: Literal["pickle", "sqlite"] = "pickle"

# Env overrides
ENV_DB_PATH = "AUTOCODE_DB"  # explicit path to DB file
ENV_DB_MODE = "AUTOCODE_DB_MODE"  # project | shared
ENV_BACKEND = "AUTOCODE_BACKEND"  # pickle | sqlite
ENV_PROJECT_ROOT = "AUTOCODE_PROJECT_ROOT"  # explicit project root
ENV_SHARED_DIR = "AUTOCODE_SHARED_DIR"  # explicit shared root dir

# Back-compat constant (used by code_db.py import). Keep as default filename.
DB_PATH = f"{DEFAULT_DB_BASENAME}{DEFAULT_PICKLE_EXT}"


# -------- Utilities --------
def _is_windows() -> bool:
    return os.name == "nt"


def _find_project_root(start: Optional[Path] = None) -> Path:
    """Find nearest directory containing Project.toml or .git, else start/CWD."""
    root = Path(os.environ.get(ENV_PROJECT_ROOT) or (start or Path.cwd())).resolve()
    for p in [root] + list(root.parents):
        if (p / "Project.toml").exists() or (p / ".git").exists():
            return p
    return root


def _project_autocode_dir(project_root: Path) -> Path:
    return project_root / AUTOCODE_DIRNAME


def _shared_root() -> Path:
    env = os.environ.get(ENV_SHARED_DIR)
    if env:
        return Path(env).expanduser().resolve()
    if _is_windows():
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else (Path.home() / "AppData" / "Roaming")
        return (base / "AutoCode").resolve()
    # POSIX default
    return (Path.home() / ".local" / "share" / "AutoCode").resolve()


def _ext_for_backend(backend: str) -> str:
    return DEFAULT_SQLITE_EXT if backend == "sqlite" else DEFAULT_PICKLE_EXT


def _config_path_for(mode: str, project_root: Optional[Path] = None) -> Path:
    if mode == "shared":
        return _shared_root() / "config.json"
    pr = _find_project_root(project_root)
    return _project_autocode_dir(pr) / "config.json"


def _load_config(mode: str, project_root: Optional[Path] = None) -> dict:
    cfg_path = _config_path_for(mode, project_root)
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_config(mode: str, data: dict, project_root: Optional[Path] = None) -> None:
    cfg_path = _config_path_for(mode, project_root)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class FileLock:
    """Simple cross-process lock using exclusive lockfile create."""

    def __init__(self, path: Path, timeout_s: float = 10.0):
        self.path = path
        self.timeout_s = timeout_s
        self._fd: Optional[int] = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()
        while True:
            try:
                self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self._fd, str(os.getpid()).encode("utf-8"))
                break
            except FileExistsError:
                if time.time() - start > self.timeout_s:
                    raise TimeoutError(f"Timeout acquiring DB lock: {self.path}")
                time.sleep(0.05)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._fd is not None:
                os.close(self._fd)
        finally:
            try:
                if self.path.exists():
                    self.path.unlink()
            except Exception:
                pass
        return False


# -------- Resolution --------
def resolve_db(mode: Optional[str] = None,
               backend: Optional[str] = None,
               explicit_path: Optional[Path] = None,
               project_root: Optional[Path] = None) -> tuple[Path, str, str]:
    """Resolve DB file path and active mode/backend.

    Returns: (db_path, mode, backend)
    Resolution order:
      - explicit_path or ENV AUTOCODE_DB
      - mode from args/env/config (default project)
      - backend from args/env/config (default pickle)
      - default path: project/.autocode/code_db.<ext> or shared_root/code_db.<ext>
    """
    # Explicit DB path overrides everything
    env_db = os.environ.get(ENV_DB_PATH)
    if explicit_path is None and env_db:
        explicit_path = Path(env_db)

    # Mode
    active_mode = (mode or os.environ.get(ENV_DB_MODE) or None)
    if active_mode not in ("project", "shared"):
        # Fallback to config (project first, then shared)
        cfg_p = _load_config("project", project_root)
        active_mode = cfg_p.get("db_mode")
        if active_mode not in ("project", "shared"):
            cfg_s = _load_config("shared", project_root)
            active_mode = cfg_s.get("db_mode")
    if active_mode not in ("project", "shared"):
        active_mode = DEFAULT_MODE

    # Backend
    active_backend = (backend or os.environ.get(ENV_BACKEND) or None)
    if active_backend not in ("pickle", "sqlite"):
        cfg = _load_config(active_mode, project_root)
        active_backend = cfg.get("backend")
    if active_backend not in ("pickle", "sqlite"):
        active_backend = DEFAULT_BACKEND

    # Path
    if explicit_path is not None:
        return explicit_path.resolve(), active_mode, active_backend

    ext = _ext_for_backend(active_backend)
    if active_mode == "shared":
        base = _shared_root()
        cfg = _load_config("shared", project_root)
        rel = cfg.get("db_path")  # may be absolute
        if rel:
            path = Path(rel)
            if not path.is_absolute():
                path = base / rel
        else:
            path = base / f"{DEFAULT_DB_BASENAME}{ext}"
        return path.resolve(), active_mode, active_backend
    else:
        pr = _find_project_root(project_root)
        base = _project_autocode_dir(pr)
        cfg = _load_config("project", pr)
        rel = cfg.get("db_path")
        if rel:
            path = Path(rel)
            if not path.is_absolute():
                path = base / rel
        else:
            path = base / f"{DEFAULT_DB_BASENAME}{ext}"
        return path.resolve(), active_mode, active_backend


# -------- Backups --------
def _rotate_backup(db_path: Path, keep: int = 5) -> Optional[Path]:
    if not db_path.exists():
        return None
    backups_dir = db_path.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_path = backups_dir / f"{db_path.stem}-{ts}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    existing = sorted(backups_dir.glob(f"{db_path.stem}-*{db_path.suffix}"))
    if len(existing) > keep:
        for old in existing[: len(existing) - keep]:
            try:
                old.unlink()
            except Exception:
                pass
    return backup_path


# -------- IO (pickle/sqlite) --------
def _save_pickle(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass


def _load_pickle(path: Path):
    with open(path, "rb") as f:
        return pickle.load(f)


def _save_sqlite(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS blobs (key TEXT PRIMARY KEY, data BLOB NOT NULL, updated_at TEXT NOT NULL)"
        )
        blob = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
        con.execute(
            "REPLACE INTO blobs (key, data, updated_at) VALUES (?, ?, datetime('now'))",
            ("code_db", sqlite3.Binary(blob)),
        )
        con.commit()


def _load_sqlite(path: Path):
    if not path.exists():
        return None
    with sqlite3.connect(str(path)) as con:
        try:
            cur = con.execute("SELECT data FROM blobs WHERE key = ?", ("code_db",))
            row = cur.fetchone()
            if not row:
                return None
            return pickle.loads(row[0])
        except sqlite3.OperationalError:
            # table missing
            return None


# -------- Public API --------
def init_db(project_root: Optional[Path] = None,
            mode: Optional[Literal["project", "shared"]] = None,
            backend: Optional[Literal["pickle", "sqlite"]] = None,
            overwrite: bool = False,
            explicit_path: Optional[Path] = None) -> Path:
    db_path, active_mode, active_backend = resolve_db(mode, backend, explicit_path, project_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists() and not overwrite:
        # Ensure config is present at least
        cfg = _load_config(active_mode, project_root)
        if "backend" not in cfg:
            cfg["backend"] = active_backend
            _save_config(active_mode, cfg, project_root)
        return db_path

    # Lazy import to avoid cycles
    from code_db import CodeDatabase  # type: ignore

    db = CodeDatabase()
    # Attach meta and schema_version for future migrations
    if not hasattr(db, "meta") or getattr(db, "meta") is None:
        try:
            setattr(db, "meta", {})
        except Exception:
            pass
    try:
        db.meta["schema_version"] = int(db.meta.get("schema_version", 1))
    except Exception:
        pass

    save_db(db, project_root=project_root, mode=active_mode, backend=active_backend, explicit_path=db_path, do_backup=False)

    # Write config defaults
    cfg = _load_config(active_mode, project_root)
    cfg.setdefault("db_mode", active_mode)
    cfg.setdefault("backend", active_backend)
    # Store relative path when under standard dir
    if active_mode == "project":
        base = _project_autocode_dir(_find_project_root(project_root))
    else:
        base = _shared_root()
    try:
        cfg_path_val = db_path.name if db_path.parent == base else str(db_path)
    except Exception:
        cfg_path_val = str(db_path)
    cfg.setdefault("db_path", cfg_path_val)
    cfg.setdefault("backups", {"keep": 5})
    _save_config(active_mode, cfg, project_root)
    return db_path


def load_db(project_root: Optional[Path] = None,
            mode: Optional[Literal["project", "shared"]] = None,
            backend: Optional[Literal["pickle", "sqlite"]] = None,
            explicit_path: Optional[Path] = None):
    db_path, active_mode, active_backend = resolve_db(mode, backend, explicit_path, project_root)
    if not db_path.exists():
        # Legacy fallback: try common legacy locations if no explicit path provided
        if explicit_path is None:
            pr = _find_project_root(project_root)
            legacy_candidates = [
                pr / "code_db.pkl",
                pr / "code_db.sqlite",
            ]
            for cand in legacy_candidates:
                if cand.exists():
                    try:
                        if cand.suffix == ".sqlite":
                            obj = _load_sqlite(cand)
                            # Save into resolved path using current backend
                            if obj is not None:
                                save_db(obj, project_root=project_root, mode=active_mode, backend=active_backend, explicit_path=db_path, do_backup=False)
                                return obj
                        else:
                            obj = _load_pickle(cand)
                            if obj is not None:
                                save_db(obj, project_root=project_root, mode=active_mode, backend=active_backend, explicit_path=db_path, do_backup=False)
                                return obj
                    except Exception:
                        # Ignore and continue
                        pass
        return None
    lock = db_path.with_suffix(db_path.suffix + ".lock")
    with FileLock(lock, timeout_s=10.0):
        if active_backend == "sqlite":
            return _load_sqlite(db_path)
        else:
            return _load_pickle(db_path)


def save_db(db,
            project_root: Optional[Path] = None,
            mode: Optional[Literal["project", "shared"]] = None,
            backend: Optional[Literal["pickle", "sqlite"]] = None,
            explicit_path: Optional[Path] = None,
            do_backup: bool = True) -> Path:
    db_path, active_mode, active_backend = resolve_db(mode, backend, explicit_path, project_root)
    lock = db_path.with_suffix(db_path.suffix + ".lock")
    with FileLock(lock, timeout_s=10.0):
        # backups
        cfg = _load_config(active_mode, project_root)
        keep = int(cfg.get("backups", {}).get("keep", 5))
        if do_backup and db_path.exists():
            _rotate_backup(db_path, keep)
        if active_backend == "sqlite":
            _save_sqlite(db, db_path)
        else:
            _save_pickle(db, db_path)
    return db_path


def status_db(project_root: Optional[Path] = None,
              mode: Optional[Literal["project", "shared"]] = None,
              backend: Optional[Literal["pickle", "sqlite"]] = None,
              explicit_path: Optional[Path] = None) -> dict:
    db_path, active_mode, active_backend = resolve_db(mode, backend, explicit_path, project_root)
    info = {
        "mode": active_mode,
        "backend": active_backend,
        "db_path": str(db_path),
        "exists": db_path.exists(),
        "size_bytes": db_path.stat().st_size if db_path.exists() else 0,
    }
    if db_path.exists():
        try:
            db = load_db(project_root, active_mode, active_backend, db_path)
            meta = getattr(db, "meta", {}) if db is not None else {}
            info["schema_version"] = meta.get("schema_version", 1)
            info["functions"] = len(getattr(db, "functions", {})) if db is not None else None
        except Exception as e:
            info["error"] = str(e)
    return info


def vacuum_db(project_root: Optional[Path] = None,
              mode: Optional[Literal["project", "shared"]] = None,
              backend: Optional[Literal["pickle", "sqlite"]] = None,
              explicit_path: Optional[Path] = None) -> None:
    db_path, active_mode, active_backend = resolve_db(mode, backend, explicit_path, project_root)
    if not db_path.exists():
        return
    lock = db_path.with_suffix(db_path.suffix + ".lock")
    with FileLock(lock, timeout_s=10.0):
        if active_backend == "sqlite":
            with sqlite3.connect(str(db_path)) as con:
                con.execute("VACUUM")
                con.commit()
        else:
            # For pickle, rewrite the file
            obj = _load_pickle(db_path)
            _save_pickle(obj, db_path)


def migrate_db(to_backend: Literal["pickle", "sqlite"],
               project_root: Optional[Path] = None,
               mode: Optional[Literal["project", "shared"]] = None,
               explicit_path: Optional[Path] = None,
               overwrite: bool = False) -> Path:
    """Migrate current DB to a different backend in-place (filename changes)."""
    # Resolve current
    src_path, active_mode, active_backend = resolve_db(mode, None, explicit_path, project_root)
    if active_backend == to_backend:
        return src_path
    if not src_path.exists():
        raise FileNotFoundError(f"Source DB not found: {src_path}")

    # Load object
    obj = load_db(project_root, active_mode, active_backend, src_path)
    if obj is None:
        raise RuntimeError("Failed to load existing DB object for migration")

    # Determine dest path
    dest_ext = _ext_for_backend(to_backend)
    dest_path = src_path.with_suffix(dest_ext)
    if dest_path.exists() and not overwrite:
        raise FileExistsError(f"Destination DB already exists: {dest_path}")

    # Save in new backend
    if to_backend == "sqlite":
        _save_sqlite(obj, dest_path)
    else:
        _save_pickle(obj, dest_path)

    # Update config
    cfg = _load_config(active_mode, project_root)
    cfg["backend"] = to_backend
    # If path followed default naming, switch to new file name in config
    try:
        if src_path.parent == dest_path.parent and src_path.stem == DEFAULT_DB_BASENAME:
            cfg["db_path"] = dest_path.name
    except Exception:
        pass
    _save_config(active_mode, cfg, project_root)
    return dest_path

