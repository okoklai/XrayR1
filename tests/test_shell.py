"""Run the real installer in a temporary filesystem with mocked systemd/uname.

Only root checking and absolute installation paths are redirected. No host service,
package manager or actual /etc /usr files are modified.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASH = os.environ.get('TEST_BASH') or shutil.which('bash')
NEW_BINARY = '#!/bin/sh\necho new-binary\n'


@unittest.skipUnless(BASH, 'Bash is required for shell integration tests')
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.host = self.root / 'host'
        for path in ['usr/local', 'usr/bin', 'etc/systemd/system']:
            (self.host / path).mkdir(parents=True, exist_ok=True)
        script = (ROOT / 'install.sh').read_text(encoding='utf-8')
        root_check = '[[ $EUID -eq 0 ]] || die "请使用 root 运行。"'
        self.assertIn(root_check, script)
        script = script.replace(root_check, ': # root check disabled in test sandbox')
        for path in ['/usr/local/XrayR', '/usr/bin/XrayR', '/usr/bin/xrayr',
                     '/etc/XrayR', '/etc/systemd/system/XrayR.service']:
            # Windows is case-insensitive; give the lowercase alias a distinct name.
            target = 'usr/bin/xrayr-alias' if path == '/usr/bin/xrayr' and os.name == 'nt' else path[1:]
            script = script.replace(path, (self.host / target).as_posix())
        (self.repo / 'install.sh').write_text(script, encoding='utf-8', newline='\n')
        (self.repo / 'VERSION').write_text('v0.9.5\n')
        (self.repo / 'XrayR.sh').write_text('#!/bin/bash\necho manager\n', newline='\n')
        shutil.copyfile(ROOT / 'XrayR.service', self.repo / 'XrayR.service')
        self.dist = self.repo / 'dist/v0.9.5'
        self.dist.mkdir(parents=True)
        self.archive = self.dist / 'XrayR-linux-64.zip'
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('XrayR', NEW_BINARY)
            for name in ['config.yml', 'dns.json', 'route.json', 'custom_outbound.json',
                         'custom_inbound.json', 'rulelist', 'geoip.dat', 'geosite.dat']:
                archive.writestr(name, 'bundled ' + name)
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        (self.dist / 'SHA256SUMS').write_text(self.digest + '  XrayR-linux-64.zip\n')

    def run_install(self, version='', machine='x86_64'):
        env = os.environ.copy()
        env.update(TEST_REPO=self.repo.as_posix(), TEST_LOG=(self.root / 'services.log').as_posix(),
                   TEST_VERSION=version, TEST_MACHINE=machine, MSYS_NO_PATHCONV='1')
        return subprocess.run([BASH, '-c', '''
            uname() { if [[ "$1" == -s ]]; then echo Linux; else echo "$TEST_MACHINE"; fi; }
            systemctl() { printf '%s\\n' "$*" >> "$TEST_LOG"; }
            sleep() { :; }
            export -f uname systemctl sleep
            bash "$TEST_REPO/install.sh" "$TEST_VERSION"
        '''], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')

    def installed(self):
        program = self.host / 'usr/local/XrayR/XrayR'
        program.parent.mkdir(parents=True)
        program.write_text('old binary')
        config = self.host / 'etc/XrayR/config.yml'
        config.parent.mkdir(parents=True)
        config.write_text('private existing config')
        (self.host / 'etc/systemd/system/XrayR.service').write_text('old service')
        return program, config

    def test_fresh_install_does_not_start_example_node(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.host / 'usr/local/XrayR/XrayR').read_text(), NEW_BINARY)
        calls = (self.root / 'services.log').read_text()
        self.assertIn('enable XrayR', calls)
        self.assertNotIn('restart XrayR', calls)

    def test_upgrade_preserves_existing_config(self):
        program, config = self.installed()
        result = self.run_install('0.9.5')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(program.read_text(), NEW_BINARY)
        self.assertEqual(config.read_text(), 'private existing config')
        self.assertIn('restart XrayR', (self.root / 'services.log').read_text())

    def test_bad_checksum_does_not_touch_existing_install(self):
        program, config = self.installed()
        self.archive.write_bytes(b'corrupted download')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(program.read_text(), 'old binary')
        self.assertEqual(config.read_text(), 'private existing config')
        self.assertFalse((self.root / 'services.log').exists())

    def test_missing_service_does_not_stop_existing_install(self):
        program, _ = self.installed()
        (self.repo / 'XrayR.service').unlink()
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(program.read_text(), 'old binary')
        self.assertFalse((self.root / 'services.log').exists())

    def test_incompatible_binary_does_not_stop_existing_install(self):
        program, _ = self.installed()
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('XrayR', '#!/bin/sh\nexit 126\n')
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        (self.dist / 'SHA256SUMS').write_text(digest + '  XrayR-linux-64.zip\n')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(program.read_text(), 'old binary')
        self.assertFalse((self.root / 'services.log').exists())

    def test_missing_version_and_unsupported_architecture_fail(self):
        for version, machine in [('v999.0.0', 'x86_64'), ('', 'riscv64'), ('../../foo', 'x86_64')]:
            result = self.run_install(version, machine)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.root / 'services.log').exists())


@unittest.skipUnless(BASH, 'Bash is required for shell integration tests')
class ManagerTests(unittest.TestCase):
    def test_script_update_success_and_failed_download(self):
        manager = (ROOT / 'XrayR.sh').read_text(encoding='utf-8')
        # Load the real function without running root checks or the interactive menu.
        begin = manager.index('update_shell() {')
        end = manager.index('\n# 0: running', begin)
        function = manager[begin:end]
        for mode in ['success', 'failure', 'empty', 'invalid']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'manager'
                target.write_text('original manager')
                env = os.environ.copy()
                env.update(TEST_TARGET=target.as_posix(), TEST_MODE=mode)
                script = '''
                    RAW_BASE=https://raw.githubusercontent.com/okoklai/XrayR1/master
                    curl() {
                        while [[ $# -gt 0 && "$1" != -o ]]; do shift; done
                        shift
                        case "$TEST_MODE" in
                            success) printf '#!/bin/bash\\necho updated\\n' > "$1" ;;
                            failure) return 22 ;;
                            empty) : > "$1" ;;
                            invalid) printf 'if then' > "$1" ;;
                        esac
                    }
                    # Detect accidentally calling the install menu instead of the utility.
                    install() { return 99; }
                ''' + function.replace('/usr/bin/XrayR', '"$TEST_TARGET"') + '\nupdate_shell\n'
                result = subprocess.run([BASH, '-c', script], env=env, capture_output=True)
                if mode == 'success':
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('echo updated', target.read_text())
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(target.read_text(), 'original manager')


if __name__ == '__main__':
    unittest.main()
