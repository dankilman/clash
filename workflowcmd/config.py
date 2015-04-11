import importlib
import sys
import os
import shutil

import yaml
import argh
from path import path
from cloudify_cli import utils as cli_utils
from cloudify.workflows import local
from dsl_parser import functions as dsl_functions


class Loader(object):

    def __init__(self, package, config_path, storage_dir, blueprint_path):
        package = importlib.import_module(package)
        package_path = path(package.__file__).dirname()
        config_path = package_path / config_path
        self._config = yaml.load(config_path.text())
        self._blueprint_path = package_path / blueprint_path
        self._blueprint_dir = self._blueprint_path.dirname()
        self._storage_dir = path(os.path.expanduser(storage_dir))
        self._parser = argh.ArghParser()
        self._parse_commands(commands=self._config['commands'])
        self._parser.add_commands(functions=[self._init_command])

    def _parse_commands(self, commands, namespace=None):
        functions = []
        for name, command in commands.items():
            if 'workflow' not in command:
                self._parse_commands(commands=command, namespace=name)
                continue
            functions.append(self._parse_command(name=name, command=command))
        self._parser.add_commands(functions=functions, namespace=namespace)

    def _parse_command(self, name, command):
        @argh.expects_obj
        @argh.named(name)
        def func(args):
            args = vars(args)
            parameters = _parse_parameters(command.get('parameters', {}), args)
            task_config = {
                'retries': 0,
                'retry_interval': 1,
                'thread_pool_size': 1
            }
            global_task_config = self._config.get('task', {})
            command_task_config = command.get('task', {})
            task_config.update(global_task_config)
            task_config.update(command_task_config)
            sys.path.append(self._storage_dir / 'local' / 'resources')
            env = local.load_env(name='local',
                                 storage=self._storage())
            env.execute(workflow=command['workflow'],
                        parameters=parameters,
                        task_retries=task_config['retries'],
                        task_retry_interval=task_config['retry_interval'],
                        task_thread_pool_size=task_config['thread_pool_size'])

        for arg in reversed(command.get('args', [])):
            name = arg.pop('name')
            if not isinstance(name, list):
                name = [name]
            argh.arg(*name, **arg)(func)

        return func

    def _storage(self):
        return local.FileStorage(storage_dir=self._storage_dir)

    @argh.named('init')
    def _init_command(self, inputs=None, reset=False):
        name = 'local'
        local_dir = self._storage_dir / name
        if local_dir.exists() and reset:
            shutil.rmtree(local_dir)
        inputs = cli_utils.inputs_to_dict(inputs, 'inputs')
        sys.path.append(self._blueprint_dir)
        local.init_env(blueprint_path=self._blueprint_path,
                       inputs=inputs,
                       name=name,
                       storage=self._storage())

    def dispatch(self):
        self._parser.dispatch()


def dispatch(package, config_path, storage_dir, blueprint_path):
    loader = Loader(package=package,
                    config_path=config_path,
                    storage_dir=storage_dir,
                    blueprint_path=blueprint_path)
    loader.dispatch()


def _parse_parameters(parameters, args):
    def process_arg(function_args):
        return args[function_args]

    def process_env(function_args):
        return os.environ[function_args]

    functions = {'arg': process_arg, 'env': process_env}
    for name, process in functions.items():
        dsl_functions.register(_function(process), name)
    try:
        return dsl_functions.evaluate_functions(parameters,
                                                None, None, None, None)
    finally:
        for name in functions.keys():
            dsl_functions.unregister(name)


def _function(process):
    class Function(dsl_functions.Function):
        def validate(self, **_):
            pass

        def evaluate(self, **_):
            pass

        def parse_args(self, args):
            self.function_args = args

        def evaluate_runtime(self, **_):
            return process(self.function_args)
    return Function