# -*- coding: utf-8 -*-
'''
Management of Pacemaker/Corosync clusters with PCS
==================================================

A state module to manage Pacemaker/Corosync clusters
with the Pacemaker/Corosync configuration system(PCS)

:depends: pcs

.. versionadded:: 2016.3.0
'''
from __future__ import absolute_import

# Import python libs
import logging
import os

# Import salt libs
import salt.utils
import salt.ext.six as six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if pcs package is installed
    '''
    if salt.utils.which('pcs'):
        return 'pcs'
    return False


def _file_read(path):
    '''
    Read a file and return content
    '''
    content = False
    if os.path.exists(path):
        with salt.utils.fopen(path, 'r+') as fp_:
            content = fp_.read()
        fp_.close()
    return content


def _file_write(path, content):
    '''
    Write content to a file
    '''
    with salt.utils.fopen(path, 'w+') as fp_:
        fp_.write(content)
    fp_.close()


def _get_cibpath():
    '''
    Get the path to the directory on the minion where CIB's are saved
    '''
    cibpath = os.path.join(__opts__['cachedir'], 'pcs', __env__)
    log.trace('cibpath: {0}'.format(cibpath))
    return cibpath


def _get_cibfile(cibname):
    '''
    Get the full path of a cached CIB-file with the name of the CIB
    '''
    cibfile = os.path.join(_get_cibpath(), '{0}.{1}'.format(cibname, 'cib'))
    log.trace('cibfile: {0}'.format(cibfile))
    return cibfile


def _get_cibfile_tmp(cibname):
    '''
    Get the full path of a temporary CIB-file with the name of the CIB
    '''
    cibfile_tmp = '{0}.tmp'.format(_get_cibfile(cibname))
    log.trace('cibfile_tmp: {0}'.format(cibfile_tmp))
    return cibfile_tmp


def _get_cibfile_cksum(cibname):
    '''
    Get the full path of the file containing a checksum of a CIB-file with the name of the CIB
    '''
    cibfile_cksum = '{0}.cksum'.format(_get_cibfile(cibname))
    log.trace('cibfile_cksum: {0}'.format(cibfile_cksum))
    return cibfile_cksum


def auth(name, nodes, pcsuser='hacluster', pcspasswd='hacluster', extra_args=None):
    '''
    Ensure all nodes are authorized to the cluster

    name
        Irrelevant, not used (recommended: pcs_auth__auth)
    nodes
        a list of nodes which should be authorized to the cluster
    pcsuser
        user for communitcation with pcs (default: hacluster)
    pcspasswd
        password for pcsuser (default: hacluster)
    extra_args
        list of extra option for the \'pcs cluster auth\' command

    Example:

    .. code-block:: yaml
        pcs_auth__auth:
            pcs.auth:
                - nodes:
                    - node1.example.com
                    - node2.example.com
                - pcsuser: hacluster
                - pcspasswd: hacluster
                - extra_args: []
    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    auth_required = False

    authorized = __salt__['pcs.is_auth'](nodes=nodes)
    log.trace('Output of pcs.is_auth: ' + str(authorized))

    authorized_dict = {}
    for line in authorized['stdout'].splitlines():
        node = line.split(':')[0].strip()
        auth_state = line.split(':')[1].strip()
        if node in nodes:
            authorized_dict.update({node: auth_state})
    log.trace('authorized_dict: ' + str(authorized_dict))

    for node in nodes:
        if node in authorized_dict and authorized_dict[node] == 'Already authorized':
            ret['comment'] += 'Node {0} is already authorized\n'.format(node)
        else:
            auth_required = True
            if __opts__['test']:
                ret['comment'] += 'Node is set to authorize: {0}\n'.format(node)

    if not auth_required:
        return ret

    if __opts__['test']:
        ret['result'] = None
        return ret
    if not isinstance(extra_args, (list, tuple)):
        extra_args = []
    if '--force' not in extra_args:
        extra_args += ['--force']

    authorize = __salt__['pcs.auth'](nodes=nodes, pcsuser=pcsuser, pcspasswd=pcspasswd, extra_args=extra_args)
    log.trace('Output of pcs.auth: ' + str(authorize))

    authorize_dict = {}
    for line in authorize['stdout'].splitlines():
        node = line.split(':')[0].strip()
        auth_state = line.split(':')[1].strip()
        if node in nodes:
            authorize_dict.update({node: auth_state})
    log.trace('authorize_dict: ' + str(authorize_dict))

    for node in nodes:
        if node in authorize_dict and authorize_dict[node] == 'Authorized':
            ret['comment'] += 'Authorized {0}\n'.format(node)
            ret['changes'].update({node: {'old': '', 'new': 'Authorized'}})
        else:
            ret['result'] = False
            if node in authorized_dict:
                ret['comment'] += 'Authorization check for node {0} returned: {1}\n'.format(node, authorized_dict[node])
            if node in authorize_dict:
                ret['comment'] += 'Failed to authorize {0} with error {1}\n'.format(node, authorize_dict[node])

    return ret


def cluster_setup(name, nodes, pcsclustername='pcscluster', extra_args=None):
    '''
    Setup Pacemaker cluster on nodes.
    Should be run on one cluster node only
    (there may be races)

    name
        Irrelevant, not used (recommended: pcs_setup__setup)
    nodes
        a list of nodes which should be set up
    pcsclustername
        Name of the Pacemaker cluster
    extra_args
        list of extra option for the \'pcs cluster setup\' command

    Example:

    .. code-block:: yaml
        pcs_setup__setup:
            pcs.cluster_setup:
                - nodes:
                    - node1.example.com
                    - node2.example.com
                - pcsclustername: pcscluster
                - extra_args:
                    - '--start'
                    - '--enable'
    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    setup_required = False

    config_show = __salt__['pcs.config_show']()
    log.trace('Output of pcs.config_show: '+str(config_show))

    for line in config_show['stdout'].splitlines():
        if len(line.split(':')) in [2]:
            key = line.split(':')[0].strip()
            value = line.split(':')[1].strip()
            if key in ['Cluster Name']:
                if value in [pcsclustername]:
                    ret['comment'] += 'Node is already set up\n'
                else:
                    setup_required = True
                    if __opts__['test']:
                        ret['comment'] += 'Node is set to set up\n'

    if not setup_required:
        return ret

    if __opts__['test']:
        ret['result'] = None
        return ret

    if not isinstance(extra_args, (list, tuple)):
        extra_args = []

    setup = __salt__['pcs.cluster_setup'](nodes=nodes, pcsclustername=pcsclustername, extra_args=extra_args)
    log.trace('Output of pcs.cluster_setup: ' + str(setup))

    setup_dict = {}
    for line in setup['stdout'].splitlines():
        log.trace('line: ' + line)
        log.trace('line.split(:).len: ' + str(len(line.split(':'))))
        if len(line.split(':')) in [2]:
            node = line.split(':')[0].strip()
            setup_state = line.split(':')[1].strip()
            if node in nodes:
                setup_dict.update({node: setup_state})

    log.trace('setup_dict: ' + str(setup_dict))

    for node in nodes:
        if node in setup_dict and setup_dict[node] in ['Succeeded', 'Success']:
            ret['comment'] += 'Set up {0}\n'.format(node)
            ret['changes'].update({node: {'old': '', 'new': 'Setup'}})
        else:
            ret['result'] = False
            ret['comment'] += 'Failed to setup {0}\n'.format(node)
            if node in setup_dict:
                ret['comment'] += '{0}: setup_dict: {1}\n'.format(node, setup_dict[node])
            ret['comment'] += str(setup)

    log.trace('ret: ' + str(ret))

    return ret


def cluster_node_add(name, node, extra_args=None):
    '''
    Add a node to the Pacemaker cluster via PCS
    Should be run on one cluster node only
    (there may be races)
    Can only be run on a already setup/added node

    name
        Irrelevant, not used (recommended: pcs_setup__node_add_{{node}})
    node
        node that should be added
    extra_args
        list of extra option for the \'pcs cluster node add\' command

    Example:

    .. code-block:: yaml
        pcs_setup__node_add_node1.example.com:
            pcs.cluster_node_add:
                - node: node1.example.com
                - extra_args:
                    - '--start'
                    - '--enable'
    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    node_add_required = True
    current_nodes = []

    is_member_cmd = ['pcs', 'status', 'nodes', 'corosync']
    is_member = __salt__['cmd.run_all'](is_member_cmd, output_loglevel='trace', python_shell=False)
    log.trace('Output of pcs status nodes corosync: ' + str(is_member))

    for line in is_member['stdout'].splitlines():
        if len(line.split(':')) in [2]:
            key = line.split(':')[0].strip()
            value = line.split(':')[1].strip()
            if key in ['Offline', 'Online']:
                if len(value.split()) > 0:
                    if node in value.split():
                        node_add_required = False
                        ret['comment'] += 'Node {0} is already member of the cluster\n'.format(node)
                    else:
                        current_nodes += value.split()

    if not node_add_required:
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] += 'Node {0} is set to be added to the cluster\n'.format(node)
        return ret

    if not isinstance(extra_args, (list, tuple)):
        extra_args = []

    node_add = __salt__['pcs.cluster_node_add'](node=node, extra_args=extra_args)
    log.trace('Output of pcs.cluster_node_add: ' + str(node_add))

    node_add_dict = {}
    for line in node_add['stdout'].splitlines():
        log.trace('line: ' + line)
        log.trace('line.split(:).len: ' + str(len(line.split(':'))))
        if len(line.split(':')) in [2]:
            current_node = line.split(':')[0].strip()
            current_node_add_state = line.split(':')[1].strip()
            if current_node in current_nodes + [node]:
                node_add_dict.update({current_node: current_node_add_state})
    log.trace('node_add_dict: ' + str(node_add_dict))

    for current_node in current_nodes:
        if current_node in node_add_dict:
            if node_add_dict[current_node] not in ['Corosync updated']:
                ret['result'] = False
                ret['comment'] += 'Failed to update corosync.conf on node {0}\n'.format(current_node)
                ret['comment'] += '{0}: node_add_dict: {1}\n'.format(current_node, node_add_dict[current_node])
        else:
            ret['result'] = False
            ret['comment'] += 'Failed to update corosync.conf on node {0}\n'.format(current_node)

    if node in node_add_dict and node_add_dict[node] in ['Succeeded', 'Success']:
        ret['comment'] += 'Added node {0}\n'.format(node)
        ret['changes'].update({node: {'old': '', 'new': 'Added'}})
    else:
        ret['result'] = False
        ret['comment'] += 'Failed to add node{0}\n'.format(node)
        if node in node_add_dict:
            ret['comment'] += '{0}: node_add_dict: {1}\n'.format(node, node_add_dict[node])
        ret['comment'] += str(node_add)

    log.trace('ret: ' + str(ret))

    return ret


def stonith_created(name, stonith_id, stonith_device_type, stonith_device_options=None, cibname=None):
    '''
    Ensure that a fencing resource is created

    Should be run on one cluster node only
    (there may be races)
    Can only be run on a node with a functional pacemaker/corosync

    name
        Irrelevant, not used (recommended: pcs_stonith__created_{{stonith_id}})
    stonith_id
        name for the stonith resource
    stonith_device_type
        name of the stonith agent fence_eps, fence_xvm f.e.
    stonith_device_options
        additional options for creating the stonith resource
    cibname
        use a cached CIB-file named like cibname instead of the live CIB for manipulation


    Example:

    .. code-block:: yaml
        pcs_stonith__created_my_fence_eps:
            pcs.stonith_created:
                - stonith_id: my_fence_eps
                - stonith_device_type: fence_eps
                - stonith_device_options:
                    - 'pcmk_host_map=node1.example.org:01;node2.example.org:02'
                    - 'ipaddr=myepsdevice.example.org'
                    - 'power_wait=5'
                    - 'verbose=1'
                    - 'debug=/var/log/pcsd/my_fence_eps.log'
                    - 'login=hidden'
                    - 'passwd=hoonetorg'
                - cibname: cib_for_stonith
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    stonith_create_required = False

    cibfile = None
    if isinstance(cibname, six.string_types):
        cibfile = _get_cibfile(cibname)

    is_existing_cmd = ['pcs']
    if isinstance(cibfile, six.string_types):
        is_existing_cmd += ['-f', cibfile]
    is_existing_cmd += ['stonith', 'show', stonith_id]

    is_existing = __salt__['cmd.run_all'](is_existing_cmd, output_loglevel='trace', python_shell=False)
    log.trace('Output of pcs stonith show {0}: {1}'.format(stonith_id, str(is_existing)))

    if is_existing['retcode'] in [0]:
        ret['comment'] += 'Stonith resource {0} is already existing\n'.format(stonith_id)
    else:
        stonith_create_required = True

    if not stonith_create_required:
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] += 'Stonith resource {0} is set to be created\n'.format(stonith_id)
        return ret

    if not isinstance(stonith_device_options, (list, tuple)):
        stonith_device_options = []

    stonith_create = __salt__['pcs.stonith_create'](
        stonith_id=stonith_id,
        stonith_device_type=stonith_device_type,
        stonith_device_options=stonith_device_options,
        cibfile=cibfile)

    log.trace('Output of pcs.stonith_create: ' + str(stonith_create))

    if stonith_create['retcode'] in [0]:
        ret['comment'] += 'Created stonith resource {0}\n'.format(stonith_id)
        ret['changes'].update({stonith_id: {'old': '', 'new': stonith_id}})
    else:
        ret['result'] = False
        ret['comment'] += 'Failed to create stonith resource {0}\n'.format(stonith_id)

    log.trace('ret: ' + str(ret))

    return ret


def cib_created(name, cibname, scope=None, extra_args=None):
    '''
    Ensure that a CIB-file with the content of the current live CIB is created

    Should be run on one cluster node only
    (there may be races)

    name
        Irrelevant, not used (recommended: {{formulaname}}__cib_created_{{cibname}})
    cibname
        name/path of the file containing the CIB
    scope
        specific section of the CIB (default:
    extra_args
        additional options for creating the CIB-file

    Example:

    .. code-block:: yaml
        mysql__cib_created_cib_for_galera:
            pcs.cib_created:
                - cibname: cib_for_galera
                - scope: None
                - extra_args: None
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    cib_hash_form = 'sha256'

    cib_create_required = False
    cib_cksum_required = False
    cib_required = False

    cibpath = _get_cibpath()
    cibfile = _get_cibfile(cibname)
    cibfile_tmp = _get_cibfile_tmp(cibname)
    cibfile_cksum = _get_cibfile_cksum(cibname)

    if not os.path.exists(cibpath):
        os.makedirs(cibpath)

    if not isinstance(extra_args, (list, tuple)):
        extra_args = []

    if os.path.exists(cibfile_tmp):
        __salt__['file.remove'](cibfile_tmp)

    cib_create = __salt__['pcs.cib_create'](cibfile=cibfile_tmp, scope=scope, extra_args=extra_args)
    log.trace('Output of pcs.cib_create: {0}'.format(str(cib_create)))

    if cib_create['retcode'] not in [0] or not os.path.exists(cibfile_tmp):
        ret['result'] = False
        ret['comment'] += 'Failed to get live CIB\n'
        return ret

    cib_hash_live = '{0}:{1}'.format(cib_hash_form, __salt__['file.get_hash'](path=cibfile_tmp, form=cib_hash_form))
    log.trace('cib_hash_live: {0}'.format(str(cib_hash_live)))

    cib_hash_cur = _file_read(path=cibfile_cksum)

    if cib_hash_cur not in [cib_hash_live]:
        cib_cksum_required = True

    log.trace('cib_hash_cur: {0}'.format(str(cib_hash_cur)))

    if not os.path.exists(cibfile) or not __salt__['file.check_hash'](path=cibfile, file_hash=cib_hash_live):
        cib_create_required = True

    if cib_cksum_required or cib_create_required:
        cib_required = True

    if not cib_create_required:
        __salt__['file.remove'](cibfile_tmp)
        ret['comment'] += 'CIB {0} is already equal to the live CIB\n'.format(cibname)

    if not cib_cksum_required:
        ret['comment'] += 'CIB {0} checksum is correct\n'.format(cibname)

    if not cib_required:
        return ret

    if __opts__['test']:
        __salt__['file.remove'](cibfile_tmp)
        ret['result'] = None
        if cib_create_required:
            ret['comment'] += 'CIB {0} is set to be created/updated\n'.format(cibname)
        if cib_cksum_required:
            ret['comment'] += 'CIB {0} checksum is set to be created/updated\n'.format(cibname)
        return ret

    if cib_create_required:
        __salt__['file.move'](cibfile_tmp, cibfile)

        if __salt__['file.check_hash'](path=cibfile, file_hash=cib_hash_live):
            ret['comment'] += 'Created/updated CIB {0}\n'.format(cibname)
            ret['changes'].update({'cibfile': cibfile})
        else:
            ret['result'] = False
            ret['comment'] += 'Failed to create/update CIB {0}\n'.format(cibname)

    if cib_cksum_required:
        _file_write(cibfile_cksum, cib_hash_live)

        if _file_read(cibfile_cksum) in [cib_hash_live]:
            ret['comment'] += 'Created/updated checksum {0} of CIB {1}\n'.format(cib_hash_live, cibname)
            ret['changes'].update({'cibcksum': cib_hash_live})
        else:
            ret['result'] = False
            ret['comment'] += 'Failed to create/update checksum {0} CIB {1}\n'.format(cib_hash_live, cibname)

    log.trace('ret: ' + str(ret))

    return ret


def cib_pushed(name, cibname, scope=None, extra_args=None):
    '''
    Ensure that a CIB-file is pushed if it is changed since the creation of it with pcs.cib_created

    Should be run on one cluster node only
    (there may be races)

    name
        Irrelevant, not used (recommended: {{formulaname}}__cib_pushed_{{cibname}})
    cibname
        name/path of the file containing the CIB
    scope
        specific section of the CIB
    extra_args
        additional options for creating the CIB-file

    Example:

    .. code-block:: yaml
        mysql__cib_pushed_cib_for_galera:
            pcs.cib_pushed:
                - cibname: cib_for_galera
                - scope: None
                - extra_args: None
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    cib_hash_form = 'sha256'

    cib_push_required = False

    cibfile = _get_cibfile(cibname)
    cibfile_cksum = _get_cibfile_cksum(cibname)

    if not isinstance(extra_args, (list, tuple)):
        extra_args = []

    if not os.path.exists(cibfile):
        ret['result'] = False
        ret['comment'] += 'CIB-file {0} does not exist\n'.format(cibfile)
        return ret

    cib_hash_cibfile = '{0}:{1}'.format(cib_hash_form, __salt__['file.get_hash'](path=cibfile, form=cib_hash_form))
    log.trace('cib_hash_cibfile: {0}'.format(str(cib_hash_cibfile)))

    if _file_read(cibfile_cksum) not in [cib_hash_cibfile]:
        cib_push_required = True

    if not cib_push_required:
        ret['comment'] += 'CIB {0} is not changed since creation through pcs.cib_created\n'.format(cibname)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] += 'CIB {0} is set to be pushed as the new live CIB\n'.format(cibname)
        return ret

    cib_push = __salt__['pcs.cib_push'](cibfile=cibfile, scope=scope, extra_args=extra_args)
    log.trace('Output of pcs.cib_push: {0}'.format(str(cib_push)))

    if cib_push['retcode'] in [0]:
        ret['comment'] += 'Pushed CIB {0}\n'.format(cibname)
        ret['changes'].update({'cibfile_pushed': cibfile})
    else:
        ret['result'] = False
        ret['comment'] += 'Failed to push CIB {0}\n'.format(cibname)

    log.trace('ret: ' + str(ret))

    return ret
