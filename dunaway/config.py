import os
import imp
from dunaway.constants import *

pxe_ip_address = '192.168.1.2'
www_port = 8000
host_management_type = MANUAL_HOST_MANAGEMENT

# The pxe_* values are primarally used to generate a dnsmasq.conf file.
pxe_dhcp_broadcast = '192.168.1.255'
pxe_dhcp_network_ip = '192.168.1.0'
pxe_dhcp_nameserver_list = '10.0.0.1,10.0.0.2'
pxe_dhcp_ntp = '0.0.0.0'
pxe_dhcp_domain = 'dunaway.unintuitive.local'
pxe_dhcp_gateway = pxe_ip_address
pxe_internal_if = 'eth0'
pxe_internal_ip = pxe_ip_address

###################################################
# FIXME -- get a config system
if os.path.exists('/etc/dunaway/config.py'):
    user_config = imp.load_source('user_config', '/etc/dunaway/config.py')
    globals().update(vars(user_config))
