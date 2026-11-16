"""Fixes and ideas left in the app's developer mode: `python fixes.py list | show N | done N "..." | skip N "..."`.

See synesthetic/fixes.py. Start every fix-or-add task with `list`; close each entry with what was done.
"""
import sys

from synesthetic.fixes import main

if __name__ == "__main__":
    sys.exit(main())
