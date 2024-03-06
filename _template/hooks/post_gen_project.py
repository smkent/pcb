from pathlib import Path

# Create project library table symlinks
for link_name in ["fp-lib-table", "sym-lib-table"]:
    (Path(".") / link_name).symlink_to(Path("..") / "libraries" / link_name)
