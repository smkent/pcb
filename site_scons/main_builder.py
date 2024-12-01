import functools
import os
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any, Iterator, Sequence, Set

from SCons.Builder import Builder
from SCons.Defaults import DefaultEnvironment
from SCons.Node.FS import File as SConsFile
from SCons.Script import BUILD_TARGETS
from SCons.Script.SConscript import SConsEnvironment


class MainBuilder:
    @functools.cached_property
    def is_ci(self) -> bool:
        return os.environ.get("CI", "") != ""

    @functools.cached_property
    def env_vars(self) -> dict[str, str]:
        if self.is_ci:
            return os.environ
        return {v: os.environ[v] for v in ["DISPLAY", "PATH"]}

    @functools.cached_property
    def env(self) -> SConsEnvironment:
        env = DefaultEnvironment().Environment(ENV=self.env_vars)
        env["BUILDERS"]["schematic_pdf"] = Builder(
            action="kicad-cli sch export pdf $SOURCE -o $TARGET"
        )
        env["BUILDERS"]["drc"] = Builder(action=self.pcb_design_rules_check)
        env["BUILDERS"]["fab_jlcpcb"] = Builder(action=self.fab_jlcpcb)
        return env

    @functools.cached_property
    def board_dirs(self) -> Set[Path]:
        start_dir = Path(
            "."
            if self.env.Dir("#").path == self.env.GetLaunchDir()
            else self.env.Dir(self.env.GetLaunchDir()).path
        )
        return {
            Path(self.env.Dir(x.parent).path)
            for x in start_dir.glob("**/*.kicad_pcb")
            if not (str(x).startswith("_") or "/_" in str(x))
        }

    @functools.cached_property
    def repo_libraries_path(self) -> Path:
        return Path(self.env.Dir("#").path) / "libraries"

    def _process_board(self, bd: Path) -> None:
        self._ensure_lib_table_links(bd)
        self._warn_extra_files(bd)
        if "setup" in BUILD_TARGETS:
            return
        # Sources
        pcb_source = bd / f"{bd.name}.kicad_pcb"
        schematic_source = bd / f"{bd.name}.kicad_sch"
        # Targets
        drc_target = bd / f"{bd.name}.rpt"
        if not pcb_source.is_file():
            return

        self.env.schematic_pdf(
            f"{bd}/{bd.name}-schematic.pdf", schematic_source
        )
        self.env.drc(drc_target, pcb_source)
        fab_jlcpcb_output = self.env.fab_jlcpcb(
            f"{bd}/fab-jlcpcb/{bd.name}-gerbers.zip", pcb_source
        )
        self.env.Depends(fab_jlcpcb_output, str(drc_target))

    def start(self) -> None:
        for bd in self.board_dirs:
            self._process_board(bd)
        self.env.Alias("setup", [])

    def _ensure_lib_table_links(self, board_dir: Path) -> None:
        def _set_link(target: Path, link: Path) -> None:
            with suppress(FileNotFoundError, OSError):
                if link.readlink() == target:
                    return
            with suppress(FileNotFoundError):
                link.unlink()
            print(f"Resetting symlink {link}")
            link.symlink_to(target)

        _set_link(
            self._relpath(self.repo_libraries_path, board_dir),
            board_dir / "libraries",
        )
        for lib in ["fp", "sym"]:
            lib_table_file_name = f"{lib}-lib-table"
            lib_link = board_dir / lib_table_file_name
            _set_link(Path("libraries") / lib_table_file_name, lib_link)

    @staticmethod
    def _warn_extra_files(board_dir: Path) -> None:
        def _project_files() -> Iterator[Path]:
            for fn in board_dir.iterdir():
                if not fn.is_file():
                    continue
                yield Path(fn)

        expect_extensions = {
            ".kicad_pcb": "{board}.kicad_pcb",
            ".kicad_pro": "{board}.kicad_pro",
            ".pdf": "{board}-schematic.pdf",
        }
        for path in _project_files():
            if fmt := expect_extensions.get(path.suffix):
                if path.name.startswith("_autosave"):
                    continue
                if path.name != fmt.format(board=board_dir.name):
                    print(f"Extraneous file found: {path}")

    @classmethod
    def pcb_design_rules_check(
        cls,
        target: Sequence[SConsFile],
        source: Sequence[SConsFile],
        env: SConsEnvironment,
    ) -> None:
        try:
            cls._run(
                [
                    "kicad-cli",
                    "pcb",
                    "drc",
                    "--exit-code-violations",
                    source[0],
                    "-o",
                    target[0],
                ]
            )
        except subprocess.CalledProcessError:
            if (target_path := Path(str(target[0]))).is_file():
                print(target_path.read_text())
            raise

    @classmethod
    def fab_jlcpcb(
        cls,
        target: Sequence[SConsFile],
        source: Sequence[SConsFile],
        env: SConsEnvironment,
    ) -> None:
        board_dir = Path(source[0].path).parent
        fab_dir = Path(target[0].path).parent
        cls._run(
            [
                "kikit",
                "fab",
                "jlcpcb",
                "--assembly",
                "--field",
                "LCSC Part",
                "--schematic",
                (board_dir / f"{board_dir.name}.kicad_sch"),
                "--nametemplate",
                f"{board_dir.name}-{{}}",
                source[0],
                fab_dir,
            ]
        )

    @staticmethod
    def _run(cmd: list, **kwargs: Any) -> subprocess.CompletedProcess:
        kwargs.setdefault("check", True)
        return subprocess.run([str(c) for c in cmd], **kwargs)

    @staticmethod
    def _relpath(path: Path | str, start: Path | str) -> Path:
        if sys.version_info >= (3, 12):
            return path.absolute().relative_to(start.absolute(), walk_up=True)
        return Path(os.path.relpath(path, start))
