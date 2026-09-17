"""Pinned Echo Show ROMs sharing one font payload and recovery layout."""

TARGETS = {
    'cronos': {
        'model': 'Echo Show 5 (2021)',
        'file': 'lineage-18.1-20260904-UNOFFICIAL-cronos.zip',
        'tag': 'lineage-18.1-cronos-v0.4',
        'sha256': '4c355998061a454792128d4b730932b47ed05a3d2a6d2628599218f44cc84678',
        'fingerprint': 'google/lineage_cronos/cronos:11/RQ3A.211001.001/r0rt1z209050214:userdebug/test-keys',
    },
    'checkers': {
        'model': 'Echo Show 5 (2019)',
        'file': 'lineage-18.1-20260904-UNOFFICIAL-checkers.zip',
        'tag': 'lineage-18.1-checkers-v0.7',
        'sha256': '785fa643fd68b2e6f6f02d96a2da58373c6a577b92a27cf6cec69603bb94068e',
        'fingerprint': 'google/lineage_checkers/checkers:11/RQ3A.211001.001/r0rt1z209050219:userdebug/test-keys',
    },
    'crown': {
        'model': 'Echo Show 8 (2019)',
        'file': 'lineage-18.1-20260904-UNOFFICIAL-crown.zip',
        'tag': 'lineage-18.1-crown-v0.5',
        'sha256': 'a01359a5e13dad8ac24c5507e8a747163b992012410b14d2ca9a8711ec4a1491',
        'fingerprint': 'google/lineage_crown/crown:11/RQ3A.211001.001/r0rt1z209050223:userdebug/test-keys',
    },
}
SYSTEM_BLOCKS = (
    '/dev/block/platform/soc/by-name/system',
    '/dev/block/platform/soc/11230000.mmc/by-name/system',
)


def rom_url(target):
    return f'https://github.com/amazon-oss/releases/releases/download/{target["tag"]}/{target["file"]}'
