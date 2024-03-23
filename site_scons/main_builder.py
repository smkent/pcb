import functools
import os
import subprocess
import sys
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

    def build(self) -> None:
        for bd in self.board_dirs:
            board_file = bd / f"{bd.name}.kicad_pcb"
            if not board_file.is_file():
                continue
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
        docker_ep: str = "",
        docker_only: bool = False,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess:
        def _docker_cmd() -> Sequence[str]:
            c = ["docker", "run", "--rm"]
            if docker_ep:
                c += ["--entrypoint", docker_ep]
            c += ["-v", ".:/kikit", "yaqwsx/kikit"]
            return c

        cmds = [str(c) for c in cmd]
        if not self.is_ci:
            cmds = _docker_cmd() + cmds
        else:
            cmds = ["kikit"] + cmds
        if not quiet:
            print("+", " ".join(cmds), file=sys.stderr)
        return subprocess.run(cmds, *args, check=check, **kwargs)

    def render_board(
        self,
        target: Sequence[SConsFile],
        source: Sequence[SConsFile],
        env: SConsEnvironment,
    ) -> None:
        fab_dir = str(Path(target[0].path).parent)
        self.run(["drc", "run", source[0]])
        self.run(["fab", "jlcpcb", source[0], fab_dir])
        if not self.is_ci:
            self.run(
                ["-c", f"chown -R {os.getegid()}:{os.getegid()} {fab_dir}"],
                docker_ep="/bin/sh",
            )
