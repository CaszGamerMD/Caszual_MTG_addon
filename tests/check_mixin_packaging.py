"""Regression check for Mixin's reserved-package restriction; takes a built jar."""
import json
import struct
import sys
import zipfile

def class_info(data):
    assert data[:4] == b'\xca\xfe\xba\xbe'
    count = struct.unpack_from('>H', data, 8)[0]
    pool = {}; pos = 10; index = 1
    while index < count:
        tag = data[pos]; pos += 1
        if tag == 1:
            length = struct.unpack_from('>H', data, pos)[0]; pos += 2
            pool[index] = (tag, data[pos:pos+length]); pos += length
        elif tag == 7:
            pool[index] = (tag, struct.unpack_from('>H', data, pos)[0]); pos += 2
        else:
            pos += {3:4,4:4,5:8,6:8,8:2,9:4,10:4,11:4,12:4,15:3,16:2,17:4,18:4,19:2,20:2}[tag]
            if tag in (5, 6): index += 1
        index += 1
    this_class = struct.unpack_from('>H', data, pos+2)[0]
    binary_name = pool[pool[this_class][1]][1].decode()
    return binary_name, pool, data[pos:]

with zipfile.ZipFile(sys.argv[1]) as jar:
    assert jar.testzip() is None
    mod = json.loads(jar.read('fabric.mod.json'))
    reserved = []
    mixins = set()
    for item in mod['mixins']:
        name = item if isinstance(item, str) else item['config']
        config = json.loads(jar.read(name))
        prefix = config['package'].replace('.', '/') + '/'
        reserved.append(prefix)
        for key in ('mixins', 'client', 'server'):
            for entry in config.get(key, []):
                mixins.add(prefix + entry.replace('.', '/'))
    classes = set()
    for path in jar.namelist():
        if not path.endswith('.class'): continue
        name, pool, _ = class_info(jar.read(path))
        assert path == name + '.class', ('Class path/name mismatch', path, name)
        classes.add(name)
        assert not any(name.startswith(prefix) for prefix in reserved) or name in mixins, ('Ordinary class is in reserved mixin package', name)
        for tag, value in pool.values():
            if tag == 1:
                assert b'dev/casz/caszualmtg/ContainerAccess' not in value, 'Stale accessor reference'
    assert mixins <= classes, 'Mixin class missing from jar'
    for entries in mod['entrypoints'].values():
        for entry in entries:
            name = (entry if isinstance(entry, str) else entry['value']).replace('.', '/')
            assert name in classes
            assert not any(name.startswith(prefix) for prefix in reserved), 'Entrypoint in reserved package'
    print('PASS: entrypoints outside reserved packages, mixins present, class names and accessor references consistent')
