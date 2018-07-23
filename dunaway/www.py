"""Web Services / REST endpoints for dunaway
"""

import logging
import os
import threading
import time
import getpass
import json

# 3rd party
import flask
import werkzeug

# my modules
import config
import constants
import util
import paths

__author__ = 'mburr'

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = flask.Flask(__name__)


def _get_worker_threads(data, worker):
    threads = []
    for info in data.itervalues():
        t = threading.Thread(target=worker, args=(info,))
        threads.append(t)
    return threads


def _start_threads_and_wait(threads):
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


@app.route('/update/', methods=['POST'])
def update():
    def physical_host_reset(info):
        ip_address = info['oob_ip_address']
        cmd = 'ipmitool -H %s -I lanplus -U %s -P %s chassis power cycle'
        cmd %= (ip_address, config.oob_username, config.oob_password)
        cmd = cmd.split()
        logger.info('Resetting host at OOB IP %s' % ip_address)
        util.system(cmd)

    if not flask.request.headers['Content-Type'] == 'application/json':
        raise Exception('Content type "%s" not supported here.' %
                        (flask.request.headers['Content-Type'],))

    for db_file in [constants.HOST_STATE, constants.PXE_CONFIG]:
        path = os.path.join(paths.DB_PATH, db_file)
        if os.path.exists(path):
            logger.info('Removing db_file %s' % path)
            os.remove(path)

    data = util._db(constants.PXE_CONFIG, flask.request.json, overwrite=True)

    util.write_dhcp_conf_file(data)
    util.prepare_install_source(data, ks_address=(
        config.pxe_ip_address, config.www_port))
    util.dhcp_service_do('restart')

    if config.host_management_type == constants.IPMI_HOST_MANAGEMENT:
        threads = _get_worker_threads(
            data=data, worker=physical_host_reset)
        _start_threads_and_wait(threads)
    elif config.host_management_type == constants.MANUAL_HOST_MANAGEMENT:
        logger.info(
            'Manual host managment. Someone else is going to reset the hosts.')
    else:
        msg = ('A known "host_management_type" was not configured. Unable to '
               'continue.')
        logger.error(msg)
        response = json.jsonify(message='Invalid')
        response.status_code = 401
        return response

    result = json.dumps({
        'hosts_configured': data.keys(),
    })
    logger.info('Prepared PXE environment for %s hosts.' % len(data))
    return flask.Response(result, mimetype='application/json')


@app.route('/ks/', methods=['GET'])
def ks():
    """Return kickstart script (text), customized based upon connecting IP address.
    """

    pxe_config = util._db(constants.PXE_CONFIG)
    ip_address = flask.request.remote_addr
    ip_address = util.get_normalized_ipv4_address(ip_address)
    host_info = pxe_config[ip_address]
    mac_address = host_info['mac_address']

    template = util.get_resource_path('template.ks')
    template = open(template, 'r').read()
    kwargs = dict(host_info)
    kwargs.update(pxe_ip_address=config.pxe_ip_address,
                  www_port=config.www_port, ip_address=ip_address)
    result = flask.render_template_string(template, **kwargs)
    logger.debug('%s asked for kickstart file. Marking as "%s"' %
                 (mac_address, constants.IMAGING_STARTED))
    util._db(constants.HOST_STATE, {mac_address: constants.IMAGING_STARTED})
    util.delete_pxe_config_links(mac_address)
    util.disable_dhcp(mac_address)
    util.dhcp_service_do('restart')
    logger.debug(
        'Unconfigured DHCP for %s. Serving kickstart file...' % mac_address)
    return flask.Response(result, mimetype='text/plain')


@app.route('/report_imaging_complete/', methods=['GET'])
def report_imaging_complete():
    ip_address = flask.request.remote_addr
    ip_address = util.get_normalized_ipv4_address(ip_address)
    util._db(constants.HOST_STATE, {ip_address: constants.IMAGING_COMPLETE})
    msg = ('Marking imaging for host with ip address %s as complete.' %
           ip_address)
    logger.info(msg)
    return flask.Response(msg, mimetype='text/plain')


@app.route('/state/', methods=['GET'])
def state():
    known_hosts = set(util._db(constants.PXE_CONFIG).keys())
    host_state = util._db(constants.HOST_STATE)
    for host in tuple(known_hosts):
        if host_state.get(host) == constants.IMAGING_COMPLETE:
            known_hosts.remove(host)
    if known_hosts:
        state = constants.NOT_ALL_HOSTS_IMAGING_COMPLETE
    else:
        state = constants.ALL_HOSTS_IMAGING_COMPLETE
    result = json.dumps({'state': state})
    return flask.Response(result, mimetype='application/json')


def cli_www_server():
    # this is an abuse of the flask DEVELOPMENT server
    if getpass.getuser() == 'root':
        raise Exception('no superuser!')
    app.run('0.0.0.0', port=config.www_port, debug=False)
