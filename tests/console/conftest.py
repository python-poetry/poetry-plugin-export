from pathlib import Path

import pytest

from cleo.testers.command_tester import CommandTester
from poetry.installation import Installer
from poetry.utils.env import MockEnv

from tests.helpers import TestApplication
from tests.helpers import TestExecutor


@pytest.fixture
def app(poetry):
    app_ = TestApplication(poetry)

    return app_


@pytest.fixture
def env(tmp_dir):
    path = Path(tmp_dir) / ".venv"
    path.mkdir(parents=True)
    return MockEnv(path=path, is_venv=True)


@pytest.fixture
def command_tester_factory(app, env):
    def _tester(command, poetry=None, installer=None, executor=None, environment=None):
        command = app.find(command)
        tester = CommandTester(command)

        # Setting the formatter from the application
        # TODO: Find a better way to do this in Cleo
        app_io = app.create_io()
        formatter = app_io.output.formatter
        tester.io.output.set_formatter(formatter)
        tester.io.error_output.set_formatter(formatter)

        if poetry:
            app._poetry = poetry

        poetry = app.poetry
        command._pool = poetry.pool

        if hasattr(command, "set_env"):
            command.set_env(environment or env)

        if hasattr(command, "set_installer"):
            installer = installer or Installer(
                tester.io,
                env,
                poetry.package,
                poetry.locker,
                poetry.pool,
                poetry.config,
                executor=executor
                or TestExecutor(env, poetry.pool, poetry.config, tester.io),
            )
            installer.use_executor(True)
            command.set_installer(installer)

        return tester

    return _tester


@pytest.fixture
def do_lock(command_tester_factory, poetry):
    command_tester_factory("lock").execute()
    assert poetry.locker.lock.exists()
