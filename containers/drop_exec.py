"""Trusted privilege boundary: never used outside the container."""
import os
import resource
import sys

resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
os.setgroups([])
os.setgid(10001)
os.setuid(10001)
os.chdir('/sandbox/work')
os.execvpe(sys.argv[1], sys.argv[1:], {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/sandbox/work', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1'})
