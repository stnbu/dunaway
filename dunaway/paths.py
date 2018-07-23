import os

dunaway_USER = 'dunaway'
dunaway_ROOT = os.path.expanduser('~%s' % dunaway_USER)
DHCP_CONF_D_DIR = os.path.join(dunaway_ROOT, 'dnsmasq.d')
TFTP_BASE_PATH = os.path.join(dunaway_ROOT, 'tftpboot')
ISO_PATH = os.path.join(dunaway_ROOT, 'iso')
BOOT_CFG_BASE_PATH = os.path.join(TFTP_BASE_PATH, 'boot_cfg')
ISO_MNT_BASE_PATH = os.path.join(TFTP_BASE_PATH, 'iso_mnt')
PXELINUX_CFG = os.path.join(TFTP_BASE_PATH, 'pxelinux.cfg')

DB_PATH = os.path.join(dunaway_ROOT, 'var')
KICKSTART_TEMPLATE_PATH = os.path.join(dunaway_ROOT, 'etc', 'template.ks')
