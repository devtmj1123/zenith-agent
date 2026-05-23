from .shell import run_command
from .file_ops import read_file, write_file, list_dir
from .web_search import search

BUILTIN_TOOLS = {
    "run_command": run_command,
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "search": search,
}
