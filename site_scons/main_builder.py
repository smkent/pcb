import functools
import os
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any, Sequence, Set

from SCons.Defaults import DefaultEnvironment
from SCons.Node.FS import File as SConsFile
from SCons.Script.SConscript import SConsEnvironment


class MainBuilder:
    @functools.cached_property
    def is_ci(self) -> bool:
        return os.environ.get("CI", "") != ""

    @functools.cached_property
    def env(self) -> SConsEnvironment:
        return DefaultEnvironment()

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
            if not str(x).startswith("_")
        }

    def ensure_lib_table_links(self, board_dir: Path) -> None:
        libraries_path = Path(self.env.Dir("#").path) / "libraries"
        link_root = libraries_path.relative_to(
            board_dir.absolute(), walk_up=True
        )
        for lib in ["fp", "sym"]:
            lib_file = f"{lib}-lib-table"
            lib_link = board_dir / lib_file
            with suppress(FileNotFoundError, OSError):
                if lib_link.readlink() == link_root / lib_file:
                    continue
            with suppress(FileNotFoundError):
                lib_link.unlink()
            print(f"Resetting symlink {lib_link}")
            lib_link.symlink_to(link_root / lib_file)

    def build(self) -> None:
        for bd in self.board_dirs:
            self.ensure_lib_table_links(bd)
            board_file = bd / f"{bd.name}.kicad_pcb"
            schematic_file = bd / f"{bd.name}.kicad_sch"
            if not board_file.is_file():
                continue

            self.env.Command(
                f"{bd}/{bd.name}-schematic.pdf",
                str(schematic_file),
                self.render_schematic,
            )
            self.env.Command(
                f"{bd}/fab-jlcpcb/gerbers.zip",
                str(board_file),
                self.render_board,
            )

    def run(
        self,
        cmd: list,
        *args: Any,
        quiet: bool = False,
        check: bool = True,
        docker_only: bool = False,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess:
        def _docker_cmd() -> Sequence[str]:
            c = ["docker", "run", "--rm"]
            cexec = cmds.pop(0)
            if cexec != "kikit":
                c += ["--entrypoint", cexec]
            c += [
                "-v",
                ".:/kikit",
                "-v",
                "{}:/usr/local/share/fonts".format(
                    str(Path(self.env.Dir("#").path) / "fonts")
                ),
                "yaqwsx/kikit",
            ]
            return c

        cmds = [str(c) for c in cmd]
        if not self.is_ci:
            cmds = _docker_cmd() + cmds
        if not quiet:
            print("+", " ".join(cmds), file=sys.stderr)
        return subprocess.run(cmds, *args, check=check, **kwargs)

    def render_board(
        self,
        target: Sequence[SConsFile],
        source: Sequence[SConsFile],
        env: SConsEnvironment,
    ) -> None:
        board_dir = Path(source[0].path).parent
        fab_dir = Path(target[0].path).parent
        self.run(["kikit", "drc", "run", source[0]])
        self.run(
            [
                "kikit",
                "fab",
                "jlcpcb",
                "--assembly",
                "--field",
                "LCSC Part",
                "--schematic",
                (board_dir / f"{board_dir.name}.kicad_sch"),
                source[0],
                fab_dir,
            ]
        )
        self.chown_project_dir(board_dir)

    def render_schematic(
        self,
        target: Sequence[SConsFile],
        source: Sequence[SConsFile],
        env: SConsEnvironment,
    ) -> None:
        board_dir = Path(source[0].path).parent
        self.run(
            ["kicad-cli", "sch", "export", "pdf", source[0], "-o", target[0]]
        )
        self.chown_project_dir(board_dir)

    def chown_project_dir(self, board_dir: Path) -> None:
        if not self.is_ci:
            self.run(
                [
                    "/bin/sh",
                    "-c",
                    f"chown -R {os.getegid()}:{os.getegid()} {board_dir}",
                ],
            )
