from pathlib import Path

repo_path = Path("..")
while not (repo_path / ".git").is_dir():
    if (next_path := repo_path / "..").resolve() == repo_path.resolve():
        raise Exception("Unable to locate repository root")
    repo_path = next_path

# Create project library table symlinks
for link_name in ["fp-lib-table", "sym-lib-table"]:
    (Path(".") / link_name).symlink_to(repo_path / "libraries" / link_name)
