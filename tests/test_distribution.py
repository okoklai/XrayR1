"""Offline checks: saved assets, source availability, architecture and runtime URLs."""
import hashlib
import json
from pathlib import Path
import re
import tarfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_archives_match_manifest_and_architecture(self):
        version = (ROOT / 'VERSION').read_text().strip()
        manifest = json.loads((ROOT / 'backup/provenance.json').read_text())
        self.assertEqual(version, manifest['version'])
        expected_machines = {'64': 62, 'arm64-v8a': 183, 's390x': 22}
        assets = {a['name']: a for a in manifest['assets']}
        checksums = dict(line.split()[::-1] for line in
                         (ROOT / 'dist' / version / 'SHA256SUMS').read_text().splitlines())
        self.assertEqual(set(checksums), {f'XrayR-linux-{a}.zip' for a in expected_machines})
        for arch, machine in expected_machines.items():
            name = f'XrayR-linux-{arch}.zip'
            path = ROOT / 'dist' / version / name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, checksums[name])
            self.assertEqual(digest, assets[name]['sha256'])
            self.assertEqual(path.stat().st_size, assets[name]['bytes'])
            with zipfile.ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())
                self.assertTrue({'XrayR', 'config.yml', 'geoip.dat', 'geosite.dat'}.issubset(archive.namelist()))
                self.assertTrue(all('/' not in n and '\\' not in n for n in archive.namelist()))
                with archive.open('XrayR') as binary:
                    header = binary.read(20)
                self.assertEqual(header[:5], b'\x7fELF\x02')
                self.assertEqual(int.from_bytes(header[18:20], 'little' if header[5] == 1 else 'big'), machine)

    def test_corresponding_source_is_saved(self):
        manifest = json.loads((ROOT / 'backup/provenance.json').read_text())
        path = ROOT / manifest['source_archive']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), manifest['source_sha256'])
        with tarfile.open(path) as archive:
            self.assertTrue({'XrayR/go.mod', 'XrayR/go.sum', 'XrayR/LICENSE'}.issubset(archive.getnames()))

    def test_no_upstream_runtime_fetches(self):
        for name in ['install.sh', 'XrayR.sh', 'Dockerfile', 'docker-compose.yml']:
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertNotRegex(text, r'a9086/|XrayR-project/|xrayr-project/|chiakge/|get\.acme\.sh')
            self.assertNotIn('--no-check-certificate', text)
        self.assertNotIn('curl', (ROOT / 'Dockerfile').read_text())

    def test_docker_and_installer_default_versions_match(self):
        version = (ROOT / 'VERSION').read_text().strip()
        self.assertIn('ARG XRAYR_VERSION=' + version, (ROOT / 'Dockerfile').read_text())
        self.assertIn('XRAYR_VERSION: ' + version, (ROOT / 'docker-compose.yml').read_text())

    def test_config_matches_saved_binary_distribution(self):
        version = (ROOT / 'VERSION').read_text().strip()
        with zipfile.ZipFile(ROOT / 'dist' / version / 'XrayR-linux-64.zip') as archive:
            for name in archive.namelist():
                if name != 'XrayR':
                    self.assertEqual((ROOT / 'config' / name).read_bytes().replace(b'\r\n', b'\n'),
                                     archive.read(name).replace(b'\r\n', b'\n'))


if __name__ == '__main__':
    unittest.main()
