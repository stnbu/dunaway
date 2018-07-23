import subprocess
import logging
import os
import re
import getpass
import urllib
import socket
import paths
import json
import time

# 3rd party
import uuid

# my modules
import config
import constants


__author__ = 'mburr'
logger = logging.getLogger(__name__)


def is_superuser():
    """We wrap this for future portability...
    """
    if getpass.getuser() == 'root':
        return True
    return False


def system(command):
    """execute shell command with subprocess.Popen, return
    (returncode, stdout, stderr) tuple
    """
    logger.debug('Executing: %s' % ' '.join(command))
    p = subprocess.Popen(command, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    pout, perr = p.communicate()
    return p.returncode, pout, perr


def dhcp_service_do(subcommand, sudo=True):
    """Wrapper providing "service" interface to dnsmasq (start, stop, etc)

    WARNING: This is highly unwise in any kind of production environment. Maybe
    modify /etc/ethers and send SIGHUP to dnsmasq proc...?
    """
    command = []
    if sudo:
        command.append('sudo')
    command.extend(['service', 'dnsmasq'])
    command.append(subcommand)  # start, restart, etc...
    p = subprocess.Popen(command, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    pout, perr = p.communicate()
    returncode, pout, perr = system(command)
    if returncode:
        raise Exception(perr)


def dashify_mac_address(string):
    """Naively turn : separated MAC string into - separated MAC string
    """
    string = string.lower()
    mac = string.split(':')
    mac = '-'.join(mac)
    return mac


def is_path(string):
    return string.startswith(os.path.sep)


def media_is_mounted(mount_point):
    return os.path.exists(os.path.join(mount_point,
                                       constants.MEDIA_MOUNTED_SENTINEL))


def mount_iso(iso_path, mount_point):
    if media_is_mounted(mount_point):
        return
    command = 'sudo mount -t iso9660 -o loop,check=relaxed'.split()
    command.append(iso_path)
    command.append(mount_point)
    logger.info('Mounting ISO')
    returncode, pout, perr = system(command)
    if returncode:
        raise Exception(perr)


def write_pxe_config_file(info, path):
    """Write a pxe boot file to path, that is, menu file initially loaded by
    pxelinux.0
    """
    template = (
        'default menu.c32\n'
        'prompt 0\n'
        'timeout 1\n'
        'ONTIMEOUT 1\n'
        'menu title ########## PXE Boot Menu ##########\n'
        'label 1\n'
        'menu label ^1) Install ESXi\n'
        'kernel {mboot32_path}\n'
        'append  -c {kernel_config_path}\n')
    content = template.format(**info)
    logger.debug('Writing out new config file to %s' % path)
    with open(path, 'w') as f:
        f.write(content)


def gen_adapted_ro_boot_file(path, prefix, ks_address):
    """Make changes necessary to adapt "boot.cfg" from CDROM media to PXE boot
    """
    ip, port = ks_address
    with open(path, 'r') as f:
        for line in f:
            if line.lstrip().startswith('kernel='):
                line = line.replace('/', '')
                prefix = 'prefix=%s\n' % prefix
                line = prefix + line
            if line.lstrip().startswith('kernelopt='):
                if 'ks=' not in line:
                    line = line.rstrip() + ' ks=http://%s:%s/ks/\n' % \
                        (ip, port)
            if line.lstrip().startswith('modules='):
                line = line.replace('/', '')
            yield line


def get_media_name(install_source):
    iso_path = install_source
    assert os.path.exists(iso_path), \
        "ISO at path %s was requested but does not exist" % iso_path
    name = os.path.basename(iso_path)
    name, _ = os.path.splitext(name)
    return name, iso_path


def prepare_install_source(data, ks_address):
    for ip_address, config in data.iteritems():
        mac_address = config['mac_address']
        os.chdir(paths.TFTP_BASE_PATH)
        logger.debug('Preparing install source for %s' % mac_address)
        install_source = config.get('install_source', None)
        iso_path = config.get('iso_path', None)
        if install_source is None and iso_path is None:
            raise Exception('For host %s: one of "install_source" or '
                            '"iso_path" must be specified' % data['hostname'])
        if iso_path is not None:
            media = iso_path
        else:  # if both are specified, iso_path is used
            media = install_source
        media_name, iso_path = get_media_name(media)
        iso_mnt_basename = os.path.basename(paths.ISO_MNT_BASE_PATH)
        mount_point = os.path.join(iso_mnt_basename, media_name)
        if not os.path.exists(mount_point):
            os.mkdir(mount_point)
        mount_iso(iso_path, mount_point)

        mboot32_path = os.path.join(iso_mnt_basename, media_name, 'mboot.c32')

        boot_cfg_basename = os.path.basename(paths.BOOT_CFG_BASE_PATH)
        boot_cfg_path = os.path.join(boot_cfg_basename, media_name)

        with open(boot_cfg_path, 'w') as f:
            kernel_config_path = os.path.join(
                iso_mnt_basename, media_name, 'boot.cfg')
            content = gen_adapted_ro_boot_file(
                kernel_config_path, prefix=mount_point, ks_address=ks_address)
            f.writelines(content)
        kernel_config_path = boot_cfg_path

        cwd = os.path.join(paths.PXELINUX_CFG)
        logger.debug('Changing current working directory: %s' % cwd)
        os.chdir(cwd)

        info = {
            'mboot32_path': mboot32_path,
            'kernel_config_path': kernel_config_path,
        }
        path = os.path.join(paths.PXELINUX_CFG, media_name)
        logger.info('writing a pxe file to %s' % path)
        write_pxe_config_file(info, path)

        orig_dst = dashify_mac_address(mac_address)
        for prefix in '', '01-':
            dst = dashify_mac_address(prefix + mac_address)
            if os.path.exists(dst) or os.path.islink(dst):
                if not os.path.islink(dst):
                    raise Exception('Not a symlink. Refusing to remove: %s'
                                    % os.path.join(cwd, dst))
                logger.debug('Removing existing symlink: %s' %
                             os.path.join(cwd, dst))
                os.remove(dst)

            src = media_name
            logger.debug('Creating symlink: %s -> %s' % (repr(src), repr(dst)))
            os.symlink(src, dst)


def write_dhcp_conf_file(data):
    """Write out separate dnsmasq conf file containing dhcp-host directives
    for each record
    """
    template = 'dhcp-host=%s,%s'
    for ip_address, config in data.iteritems():
        mac_address = config['mac_address']
        path = os.path.join(paths.DHCP_CONF_D_DIR, mac_address + '.conf')
        logger.debug('Writing config file: %s' % path)
        with open(path, 'w') as config_file:
            config_file.write(template % (mac_address, ip_address))


def disable_dhcp(mac_address):
    """Disable DHCP for mac_address
    """
    template = 'dhcp-host=%s,ignore'
    path = os.path.join(paths.DHCP_CONF_D_DIR, mac_address + '.conf')
    logger.debug('Writing config file to disable host %s: %s' %
                 (mac_address, path))
    with open(path, 'w') as config_file:
        config_file.write(template % mac_address)


def get_normalized_ipv4_address(ip):
    """better-than-nothing ipv4 address normalization
    """
    quads = [str(int(i)) for i in ip.split('.')]
    assert len(quads) == 4, 'really an IP address? %s' % ip
    assert ':' not in ip, 'is this an IPv6 address? %s' % ip
    return '.'.join(quads)


def touch(path):
    with open(path, 'w') as f:
        f.write('')


def _db(db_name, update=None, overwrite=False):

    path = os.path.join(paths.DB_PATH, db_name)
    lock = path + '.lock'

    timeout = 20
    start_time = time.time()
    while os.path.exists(lock):
        if time.time() - start_time > timeout:
            raise Exception('Timed out waiting on lock for %s' % path)
        logger.info('Waiting on lock for %s' % path)
        time.sleep(1)

    touch(lock)

    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
    else:
        data = {}
    if update is not None:
        if overwrite:
            data = update
        else:
            data.update(update)
        with open(path, 'w') as f:
            json.dump(data, f)

    os.remove(lock)
    return data


def get_mac_from_ip(ipaddress):
    data = _db(constants.PXE_CONFIG)
    return data[ipaddress]['mac_address']


def get_ip_from_mac(mac_address):
    want = get_normalized_mac_address(mac_address)
    data = _db(constants.PXE_CONFIG)
    for ip_address, info in data.iteritems():
        have = get_normalized_mac_address(info['mac_address'])
        if have == want:
            return ip_address
    else:
        raise ValueError('Unable to find host info for IP address %s' % ip)
    return data[ip_address]['mac_address']


def get_resource_path(name):
    dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(dir, 'resources', name)


def delete_pxe_config_links(mac_address):
    cwd = os.path.join(paths.PXELINUX_CFG)
    logger.debug('Changing current working directory: %s' % cwd)
    os.chdir(cwd)
    for prefix in '', '01-':
        path = dashify_mac_address(prefix + mac_address)
        if not os.path.islink(path):
            logger.warn('Expected link %s is missing or is not a link.' % path)
            continue
        os.remove(path)


def get_dnsmasq_conf():
    info = {}
    info['pxe_tftp_root'] = paths.TFTP_BASE_PATH
    info['pxe_dhcp_conf_dir'] = paths.DHCP_CONF_D_DIR
    info.update(vars(config))
    path = get_resource_path('dnsmasq.conf.template')
    with open(path, 'r') as f:
        template = f.read()
    return template.format(**info)


def cli_print_dnsmasq_conf():
    """Wrapper function for CLI
    """
    print get_dnsmasq_conf()
