import functools
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence, Set

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

    def build(self) -> None:
        static_files = []
        for bd in self.board_dirs:
            board_file = bd / f"{bd.name}.kicad_pcb"
            schematic_file = bd / f"{bd.name}.kicad_sch"
            if not board_file.is_file():
                continue

            if "static" in BUILD_TARGETS:
                schematic_pdf = f"{bd}/{bd.name}-schematic.pdf"
                self.env.Command(
                    schematic_pdf, str(schematic_file), self.render_schematic
                )
                static_files.append(schematic_pdf)
            self.env.Command(
                f"{bd}/fab-jlcpcb/gerbers.zip",
                str(board_file),
                self.render_board,
            )
        self.env.Alias("static", static_files)

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
            c += ["-v", ".:/kikit", "yaqwsx/kikit"]
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
        self.run(["kikit", "fab", "jlcpcb", source[0], fab_dir])
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
