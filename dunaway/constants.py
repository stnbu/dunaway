
def _make_constants(string):
    for line in string.splitlines():
        name = line.strip()
        if not name or name.startswith('#'):
            continue
        globals()[name] = name


_make_constants("""
IMAGING_STARTED
IMAGING_COMPLETE
NOT_ALL_HOSTS_IMAGING_COMPLETE
ALL_HOSTS_IMAGING_COMPLETE
MANUAL_HOST_MANAGEMENT
IPMI_HOST_MANAGEMENT
""")


MEDIA_MOUNTED_SENTINEL = 'menu.c32'
