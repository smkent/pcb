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
    def env(self) -> SConsEnvironment:
        env = DefaultEnvironment().Environment(
            ENV={v: os.environ[v] for v in ["DISPLAY", "PATH"]}
        )
        env["BUILDERS"]["schematic_pdf"] = Builder(
            action="kicad-cli sch export pdf $SOURCE -o $TARGET"
        )
        env["BUILDERS"]["drc"] = Builder(
            action=(
                "kicad-cli pcb drc --exit-code-violations $SOURCE -o $TARGET"
            )
        )
        env["BUILDERS"]["ibom"] = Builder(
            action=(
                "generate_interactive_bom"
                " --no-browser"
                " --include-tracks"
                " --include-nets"
                " --dest-dir="
                ' --name-format="%f-bom"'
                " $SOURCE"
            )
        )
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
        html_bom_target = bd / f"{bd.name}-bom.html"
        if not pcb_source.is_file():
            return

        self.env.schematic_pdf(
            f"{bd}/{bd.name}-schematic.pdf", schematic_source
        )
        self.env.drc(drc_target, pcb_source)
        fab_jlcpcb_output = self.env.Command(
            f"{bd}/fab-jlcpcb/{bd.name}-fab_jlcpcb_output.zip",
            pcb_source,
            self.fab_jlcpcb,
        )
        self.env.Depends(fab_jlcpcb_output, str(drc_target))
        self.env.ibom(html_bom_target, pcb_source)

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

        link_root = self.repo_libraries_path.relative_to(
            board_dir.absolute(), walk_up=True
        )
        _set_link(link_root, board_dir / "libraries")
        for lib in ["fp", "sym"]:
            lib_table_file_name = f"{lib}-lib-table"
            lib_link = board_dir / lib_table_file_name
            _set_link(Path("libraries") / lib_table_file_name, lib_link)

    def _warn_extra_files(self, board_dir: Path) -> None:
        def _project_files() -> Iterator[Path]:
            for fn in board_dir.iterdir():
                if not fn.is_file():
                    continue
                yield Path(board_dir / fn)

        expect_extensions = {
            ".kicad_pcb": "{board}.kicad_pcb",
            ".kicad_pro": "{board}.kicad_pro",
            ".pdf": "{board}-schematic.pdf",
        }
        for path in _project_files():
            if fmt := expect_extensions.get(path.suffix):
                if path.name != fmt.format(board=board_dir.name):
                    print(f"Extraneous file found: {path}")

    def _run(
        self,
        cmd: list,
        *args: Any,
        quiet: bool = False,
        check: bool = True,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess:
        cmds = [str(c) for c in cmd]
        if not quiet:
            print("+", " ".join(cmds), file=sys.stderr)
        return subprocess.run(cmds, *args, check=check, **kwargs)

    def fab_jlcpcb(
        self,
        target: Sequence[SConsFile],
        source: Sequence[SConsFile],
        env: SConsEnvironment,
    ) -> None:
        board_dir = Path(source[0].path).parent
        fab_dir = Path(target[0].path).parent
        self._run(
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
