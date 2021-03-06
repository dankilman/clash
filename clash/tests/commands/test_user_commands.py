########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import os
import sys
import json

from clash import tests


class TestUserCommands(tests.BaseTest):

    def test_basic_command(self):
        self._test_command(verbose=False, command=['command1'])

    def test_verbose_basic_command(self):
        self._test_command(verbose=True, command=['command1'])

    def test_nested_command(self):
        self._test_command(verbose=False, command=['nested', 'command2'])

    def _test_command(self, verbose, command):
        config_path = 'end_to_end.yaml'
        output_path = self.workdir / 'output.json'
        self.dispatch(config_path, 'env', 'create')
        self.dispatch(config_path, 'init')
        args = [config_path] + command + ['arg1_value']
        output = self.dispatch(*args, a='arg3_value', output_path=output_path,
                               verbose=verbose).stdout
        self.assertEqual(json.loads(output_path.text()), {
            'param1': 'arg1_value',
            'param2': 'arg2_default',
            'param3': 'arg3_value'
        })
        self.assertIn('from workflow1', output)
        assertion = self.assertIn if verbose else self.assertNotIn
        assertion("Starting 'workflow1'", output)

    def test_task_config_default(self):
        config_path = 'task_config_default.yaml'
        counts = (0, 1, 1)
        self._test_task_config(config_path, counts)

    def test_task_config_global(self):
        config_path = 'task_config_global.yaml'
        counts = (4, 4, 4)
        self._test_task_config(config_path, counts)

    def test_task_config_command(self):
        config_path = 'task_config_command.yaml'
        counts = (3, 3, 3)
        self._test_task_config(config_path, counts)

    def _test_task_config(self, config_path, counts):
        output_path = self.workdir / 'output.json'
        self.dispatch(config_path, 'env', 'create')
        self.dispatch(config_path, 'init')
        self.dispatch(config_path, 'command1', output_path)
        self.assertEqual(json.loads(output_path.text()), {
            'retries': counts[0],
            'retry_interval': counts[1],
            'thread_pool_size': counts[2]
        })

    def test_update_python_path(self):
        config_path = 'pythonpath.yaml'
        storage_dir_functions = self.workdir / 'storage_dir_functions'
        storage_dir_functions.mkdir_p()
        (storage_dir_functions / '__init__.py').touch()
        script_path = storage_dir_functions / 'functions.py'
        script_path.write_text('def func2(**_): return 2')
        self.dispatch(config_path, 'env', 'create')
        self.dispatch(config_path, 'init')
        output = self.dispatch(config_path, 'command1').stdout
        self.assertIn('all good', output)
        self.assertIn('param1: 1, param2: 2', output)

    def test_env_path(self):
        config_path = 'envpath.yaml'
        self.dispatch(config_path, 'env', 'create')
        self.dispatch(config_path, 'init')
        output = self.dispatch(config_path, 'command1').stdout
        self.assertIn('all good', output)
        self.assertIn(os.path.dirname(sys.executable), output)

    def test_event_cls(self):
        config_path = 'event_cls.yaml'
        self.dispatch(config_path, 'env', 'create')
        self.dispatch(config_path, 'init')
        output1 = self.dispatch(config_path, 'command1').stdout
        output2 = self.dispatch(config_path, 'command2').stdout
        output3 = self.dispatch(config_path, 'command3',
                                verbose=True).stdout
        self.assertIn('EVENT1', output1)
        self.assertIn('EVENT2', output2)
        self.assertIn('EVENT3 env: .local, verbose: True, '
                      'workflow: workflow4', output3)

    def test_functions(self):
        config_path = 'functions.yaml'
        self.dispatch(config_path, 'env', 'create')
        self.dispatch(config_path, 'init')
        for command in [['command1'], ['nested', 'command2']]:
            args = ['val1', '--arg2', 'val2']
            command += args
            output = self.dispatch(config_path, *command).stdout.strip()
            self.assertEqual('val1 val2 functions', output)
