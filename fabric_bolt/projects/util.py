import os
import re
import subprocess

from django.utils.text import slugify
from django.conf import settings
from django.contrib import messages
from django.core.cache import cache

from virtualenv import create_environment

# These options are passed to Fabric as: fab task --abort-on-prompts=True --user=root ...
fabric_special_options = ['no_agent', 'forward-agent', 'config', 'disable-known-hosts', 'keepalive',
                          'password', 'parallel', 'no-pty', 'reject-unknown-hosts', 'skip-bad-hosts', 'timeout',
                          'command-timeout', 'user', 'warn-only', 'pool-size']


def check_output_with_ssh_key(command):
    if getattr(settings, 'GIT_SSH_KEY_LOCATION', None):
        return subprocess.check_output(
            'ssh-agent bash -c "ssh-add {};{}"'.format(settings.GIT_SSH_KEY_LOCATION, command),
            shell=True
        )
    else:
        out = subprocess.check_output([command], shell=True)
        return out


def update_project_git(project, cache_dir, repo_dir):
    if not os.path.exists(repo_dir):
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        check_output_with_ssh_key('git clone {} {}'.format(project.repo_url, repo_dir))
    else:
        check_output_with_ssh_key(
            'cd {0};git stash;git pull'.format(repo_dir)
        )


def update_project_requirements(project, repo_dir):
    pip_installs = ' '.join(project.fabfile_requirements.splitlines())

    return subprocess.check_output(
        'cd {};pip install {}'.format(repo_dir, pip_installs),
        shell=True
    )


def get_fabfile_path(project):
    if project.use_repo_fabfile:
        cache_key = 'project_{}_fabfile_path'.format(project.pk)
        cached_result = cache.get(cache_key)

        if cached_result:
            return cached_result

        cache_dir = os.path.join(settings.PUBLIC_DIR, '.repo_caches')
        repo_dir = os.path.join(cache_dir, slugify(project.name))

        update_project_git(project, cache_dir, repo_dir)

        update_project_requirements(project, repo_dir)

        result = os.path.join(repo_dir, 'fabfile.py')
        cache.set(cache_key, result, settings.FABRIC_TASK_CACHE_TIMEOUT)
        return result
    else:
        return settings.FABFILE_PATH, None


def parse_task_details(name, task_output):
    lines = task_output.splitlines()
    docstring = lines[2].strip()
    arguments_line = lines[3].strip()

    if docstring == 'No docstring provided':
        docstring = None

    arguments_line = arguments_line[11:].strip()

    arguments = []

    if arguments_line:
        for arg in arguments_line.split(', '):
            m = re.match(r"^([^=]+)(='([^']*)')?$", arg)

            if m.group(2):
                arguments.append((m.group(1), m.group(3)))
            else:
                arguments.append(m.group(1))

    return name, docstring, arguments


def get_fabric_tasks(project):
    """
    Generate a list of fabric tasks that are available
    """

    cache_key = 'project_{}_fabfile_tasks'.format(project.pk)
    cached_result = cache.get(cache_key)

    if cached_result:
        return cached_result

    try:
        fabfile_path = get_fabfile_path(project)

        output = subprocess.check_output(['fab', '--list', '--list-format=short', '--fabfile={}'.format(fabfile_path)])

        lines = output.splitlines()
        tasks = []
        for line in lines:
            name = line.strip()
            # o = subprocess.check_output(
            #     ['fab', '--display={}'.format(name), '--fabfile={}'.format(fabfile_path)]
            # )

            tasks.append(name)

        cache.set(cache_key, tasks, settings.FABRIC_TASK_CACHE_TIMEOUT)
    except Exception as e:
        print e
        tasks = []
    return tasks


def get_task_details(project, task_name):
    for details in get_fabric_tasks(project):
        if details == task_name:
            return details

    return None


def clean_key_string(key):
    key = key.replace('"', '\\"')  # escape double quotes
    key = key.replace(',', '\,')  # escape commas, that would be adding a new value
    key = key.replace('=', '\=')  # escape = because that would be setting a new key

    return key


def clean_value_string(value):
    value = value.replace('"', '\\"')  # escape double quotes
    value = value.replace(',', '\,')  # escape commas, that would be adding a new value
    value = value.replace('=', '\=')  # escape = because that would be setting a new key

    return value


def clean_arg_key_string(key):
    # this has to be a valid python function argument, so we can get pretty strict here
    key = re.sub(r'[^0-9a-zA-Z_]', '', key)  # remove anything that isn't a number, letter, or underscore

    return key


def get_key_value_string(key, config):
    key = clean_key_string(key)

    if config.data_type == config.BOOLEAN_TYPE:
        return key + ('' if config.get_value() else '=')
    elif config.data_type == config.NUMBER_TYPE:
        return key + '=' + str(config.get_value())
    else:
        return '{}={}'.format(key, clean_value_string(config.get_value()))


def update_config_values_from_session(configs, session):
    configs = configs.copy()

    for key, config in configs.iteritems():
        if session.get('configuration_values', {}).get(key, None) is not None:
            config.set_value(session['configuration_values'][key])

    return configs


def build_command(deployment, session, abort_on_prompts=True):
    # Get the dictionary of configurations for this stage
    configs = deployment.stage.get_configurations()
    configs = update_config_values_from_session(configs, session)

    task_args = [key for key, config in configs.iteritems() if config.task_argument and config.task_name == deployment.task.name]
    task_configs = [key for key, config in configs.iteritems() if not config.task_argument]

    command_to_config = {x.replace('-', '_'): x for x in fabric_special_options}

    # Take the special env variables out
    normal_task_configs = list(set(task_configs) - set(command_to_config.keys()))

    # Special ones get set a different way
    special_task_configs = list(set(task_configs) & set(command_to_config.keys()))

    command = 'fab ' + deployment.task.name

    if task_args:
        key_value_strings = []
        for key in task_args:
            cleaned_key = clean_arg_key_string(key)
            value = clean_value_string(unicode(configs[key].get_value()))
            key_value_strings.append('{}="{}"'.format(cleaned_key, value))

        command += ':'
        command += ','.join(key_value_strings)

    if normal_task_configs:
        command += ' --set '
        command += '"' + ','.join(get_key_value_string(key, configs[key]) for key in normal_task_configs) + '"'

    if special_task_configs:
        for key in special_task_configs:
            command += ' --' + get_key_value_string(command_to_config[key], configs[key])

    if abort_on_prompts:
        command += ' --abort-on-prompts'

    roles = deployment.stage.roles.values_list('name', flat=True)
    if roles:
        command += ' --roles=' + ','.join(roles)

    hosts = deployment.stage.hosts.values_list('name', flat=True)
    if hosts:
        command += ' --hosts=' + ','.join(hosts)

    fabfile_path = get_fabfile_path(deployment.stage.project)
    command += ' --fabfile={}'.format(fabfile_path)

    return command
