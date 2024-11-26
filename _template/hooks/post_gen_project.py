import subprocess
from pathlib import Path

repo_path = Path("..")
while not (repo_path / ".git").is_dir():
    if (next_path := repo_path / "..").resolve() == repo_path.resolve():
        raise Exception("Unable to locate repository root")
    repo_path = next_path

# Create project library table symlinks
subprocess.run(["scons", "-u", "setup"])
