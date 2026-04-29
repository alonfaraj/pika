"""
codegen.py generates pika/spec.py

The required spec json file can be found at
https://github.com/rabbitmq/rabbitmq-codegen
.

After cloning it run the following to generate a spec.py file:
python2 ./codegen.py ../../rabbitmq-codegen
"""
from __future__ import nested_scopes

import re
import sys

if sys.version_info.major != 2:
    sys.exit('Python 2 is required at this time')

RABBITMQ_CODEGEN_PATH = sys.argv[1]
PIKA_SPEC = '../pika/spec.py'
print(f'codegen-path: {RABBITMQ_CODEGEN_PATH}')
sys.path.append(RABBITMQ_CODEGEN_PATH)

import amqp_codegen

DRIVER_METHODS = {
    "Exchange.Bind": ["Exchange.BindOk"],
    "Exchange.Unbind": ["Exchange.UnbindOk"],
    "Exchange.Declare": ["Exchange.DeclareOk"],
    "Exchange.Delete": ["Exchange.DeleteOk"],
    "Queue.Declare": ["Queue.DeclareOk"],
    "Queue.Bind": ["Queue.BindOk"],
    "Queue.Purge": ["Queue.PurgeOk"],
    "Queue.Delete": ["Queue.DeleteOk"],
    "Queue.Unbind": ["Queue.UnbindOk"],
    "Basic.Qos": ["Basic.QosOk"],
    "Basic.Get": ["Basic.GetOk", "Basic.GetEmpty"],
    "Basic.Ack": [],
    "Basic.Reject": [],
    "Basic.Recover": ["Basic.RecoverOk"],
    "Basic.RecoverAsync": [],
    "Tx.Select": ["Tx.SelectOk"],
    "Tx.Commit": ["Tx.CommitOk"],
    "Tx.Rollback": ["Tx.RollbackOk"]
}


def fieldvalue(v):
    if isinstance(v, unicode):
        return repr(v.encode('ascii'))
    elif isinstance(v, dict):
        return repr(None)
    elif isinstance(v, list):
        return repr(None)
    else:
        return repr(v)


def normalize_separators(s):
    s = s.replace('-', '_')
    s = s.replace(' ', '_')
    return s


def pyize(s):
    s = normalize_separators(s)
    if s in ('global', 'class'):
        s += '_'
    if s == 'global_':
        s = 'global_qos'
    return s


def camel(s):
    return normalize_separators(s).title().replace('_', '')


amqp_codegen.AmqpMethod.structName = lambda m: camel(m.klass.name) + '.' + camel(m.name)
amqp_codegen.AmqpClass.structName = lambda c: camel(c.name) + "Properties"


def constantName(s):
    return '_'.join(re.split('[- ]', s.upper()))


def flagName(c, f):
    if c:
        return c.structName() + '.' + constantName('flag_' + f.name)
    else:
        return constantName('flag_' + f.name)


def generate(specPath):
    spec = amqp_codegen.AmqpSpec(specPath)

    def genSingleDecode(prefix, cLvalue, unresolved_domain):
        type = spec.resolveDomain(unresolved_domain)
        if type == 'shortstr':
            print(prefix +
                  f"{cLvalue}, offset = data.decode_short_string(encoded, offset)")
        elif type == 'longstr':
            print(prefix +
                  "length = struct.unpack_from('>I', encoded, offset)[0]")
            print(prefix + "offset += 4")
            print(prefix + f"{cLvalue} = encoded[offset:offset + length]")
            print(prefix + "try:")
            print(prefix + f"    {cLvalue} = str({cLvalue})")
            print(prefix + "except UnicodeEncodeError:")
            print(prefix + "    pass")
            print(prefix + "offset += length")
        elif type == 'octet':
            print(prefix +
                  f"{cLvalue} = struct.unpack_from('B', encoded, offset)[0]")
            print(prefix + "offset += 1")
        elif type == 'short':
            print(prefix +
                  f"{cLvalue} = struct.unpack_from('>H', encoded, offset)[0]")
            print(prefix + "offset += 2")
        elif type == 'long':
            print(prefix +
                  f"{cLvalue} = struct.unpack_from('>I', encoded, offset)[0]")
            print(prefix + "offset += 4")
        elif type == 'longlong':
            print(prefix +
                  f"{cLvalue} = struct.unpack_from('>Q', encoded, offset)[0]")
            print(prefix + "offset += 8")
        elif type == 'timestamp':
            print(prefix +
                  f"{cLvalue} = struct.unpack_from('>Q', encoded, offset)[0]")
            print(prefix + "offset += 8")
        elif type == 'bit':
            raise Exception("Can't decode bit in genSingleDecode")
        elif type == 'table':
            print(
                Exception(prefix +
                          f"({cLvalue}, offset) = data.decode_table(encoded, offset)"))
        else:
            raise Exception("Illegal domain in genSingleDecode", type)

    def genSingleEncode(prefix, cValue, unresolved_domain):
        type = spec.resolveDomain(unresolved_domain)
        if type == 'shortstr':
            print(
                prefix +
                f"assert isinstance({cValue}, str_or_bytes),\\\n{prefix}       'A non-string value was supplied for {cValue}'")
            print(prefix + f"data.encode_short_string(pieces, {cValue})")
        elif type == 'longstr':
            print(
                prefix +
                f"assert isinstance({cValue}, str_or_bytes),\\\n{prefix}       'A non-string value was supplied for {cValue}'")
            print(
                prefix +
                f"value = {cValue}.encode('utf-8') if isinstance({cValue}, unicode_type) else {cValue}")
            print(prefix + "pieces.append(struct.pack('>I', len(value)))")
            print(prefix + "pieces.append(value)")
        elif type == 'octet':
            print(prefix + f"pieces.append(struct.pack('B', {cValue}))")
        elif type == 'short':
            print(prefix + f"pieces.append(struct.pack('>H', {cValue}))")
        elif type == 'long':
            print(prefix + f"pieces.append(struct.pack('>I', {cValue}))")
        elif type == 'longlong':
            print(prefix + f"pieces.append(struct.pack('>Q', {cValue}))")
        elif type == 'timestamp':
            print(prefix + f"pieces.append(struct.pack('>Q', {cValue}))")
        elif type == 'bit':
            raise Exception("Can't encode bit in genSingleEncode")
        elif type == 'table':
            print(Exception(prefix + f"data.encode_table(pieces, {cValue})"))
        else:
            raise Exception("Illegal domain in genSingleEncode", type)

    def genDecodeMethodFields(m):
        print("        def decode(self, encoded, offset=0):")
        bitindex = None
        for f in m.arguments:
            if spec.resolveDomain(f.domain) == 'bit':
                if bitindex is None:
                    bitindex = 0
                if bitindex >= 8:
                    bitindex = 0
                if not bitindex:
                    print(
                        "            bit_buffer = struct.unpack_from('B', encoded, offset)[0]"
                    )
                    print("            offset += 1")
                print("            self.%s = (bit_buffer & (1 << %d)) != 0" %
                      (pyize(f.name), bitindex))
                bitindex += 1
            else:
                bitindex = None
                genSingleDecode("            ", f"self.{pyize(f.name)}",
                                f.domain)
        print("            return self")
        print('')

    def genDecodeProperties(c):
        print("    def decode(self, encoded, offset=0):")
        print("        flags = 0")
        print("        flagword_index = 0")
        print("        while True:")
        print(
            "            partial_flags = struct.unpack_from('>H', encoded, offset)[0]"
        )
        print("            offset += 2")
        print(
            "            flags = flags | (partial_flags << (flagword_index * 16))"
        )
        print("            if not (partial_flags & 1):")
        print("                break")
        print("            flagword_index += 1")
        for f in c.fields:
            if spec.resolveDomain(f.domain) == 'bit':
                print(f"        self.{pyize(f.name)} = (flags & {flagName(c, f)}) != 0")
            else:
                print(f"        if flags & {flagName(c, f)}:")
                genSingleDecode("            ", f"self.{pyize(f.name)}",
                                f.domain)
                print("        else:")
                print(f"            self.{pyize(f.name)} = None")
        print("        return self")
        print('')

    def genEncodeMethodFields(m):
        print("        def encode(self):")
        print("            pieces = []")
        bitindex = None

        def finishBits():
            if bitindex is not None:
                print("            pieces.append(struct.pack('B', bit_buffer))")

        for f in m.arguments:
            if spec.resolveDomain(f.domain) == 'bit':
                if bitindex is None:
                    bitindex = 0
                    print("            bit_buffer = 0")
                if bitindex >= 8:
                    finishBits()
                    print("            bit_buffer = 0")
                    bitindex = 0
                print(f"            if self.{pyize(f.name)}:")
                print("                bit_buffer |= 1 << %d" % bitindex)
                bitindex += 1
            else:
                finishBits()
                bitindex = None
                genSingleEncode("            ", f"self.{pyize(f.name)}",
                                f.domain)
        finishBits()
        print("            return pieces")
        print('')

    def genEncodeProperties(c):
        print("    def encode(self):")
        print("        pieces = []")
        print("        flags = 0")
        for f in c.fields:
            if spec.resolveDomain(f.domain) == 'bit':
                print("        if self.{}: flags = flags | {}".format(pyize(
                    f.name), flagName(c, f)))
            else:
                print(f"        if self.{pyize(f.name)} is not None:")
                print(f"            flags = flags | {flagName(c, f)}")
                genSingleEncode("            ", f"self.{pyize(f.name)}",
                                f.domain)
        print("        flag_pieces = []")
        print("        while True:")
        print("            remainder = flags >> 16")
        print("            partial_flags = flags & 0xFFFE")
        print("            if remainder != 0:")
        print("                partial_flags |= 1")
        print(
            "            flag_pieces.append(struct.pack('>H', partial_flags))")
        print("            flags = remainder")
        print("            if not flags:")
        print("                break")
        print("        return flag_pieces + pieces")
        print('')

    def fieldDeclList(fields):
        return ''.join([
            f", {pyize(f.name)}={fieldvalue(f.defaultvalue)}"
            for f in fields
        ])

    def fieldInitList(prefix, fields):
        if fields:
            return ''.join([f"{prefix}self.{pyize(f.name)} = {pyize(f.name)}\n" \
                            for f in fields])
        else:
            return f'{prefix}pass\n'

    print("""\"\"\"
AMQP Specification
==================
This module implements the constants and classes that comprise AMQP protocol
level constructs. It should rarely be directly referenced outside of Pika's
own internal use.

.. note:: Auto-generated code by codegen.py, do not edit directly. Pull
requests to this file without accompanying ``utils/codegen.py`` changes will be
rejected.

\"\"\"

import struct
from pika import amqp_object
from pika import data
from pika.compat import str_or_bytes, unicode_type

# Python 3 support for str object
str = bytes
""")

    print("PROTOCOL_VERSION = (%d, %d, %d)" % (spec.major, spec.minor,
                                               spec.revision))
    print("PORT = %d" % spec.port)
    print('')

    # Append some constants that arent in the spec json file
    spec.constants.append(('FRAME_MAX_SIZE', 131072, ''))
    spec.constants.append(('FRAME_HEADER_SIZE', 7, ''))
    spec.constants.append(('FRAME_END_SIZE', 1, ''))
    spec.constants.append(('TRANSIENT_DELIVERY_MODE', 1, ''))
    spec.constants.append(('PERSISTENT_DELIVERY_MODE', 2, ''))

    constants = {}
    for c, v, cls in spec.constants:
        constants[constantName(c)] = v

    for key in sorted(constants.keys()):
        print(f"{key} = {constants[key]}")
    print('')

    for c in spec.allClasses():
        print('')
        print(f'class {camel(c.name)}(amqp_object.Class):')
        print('')
        print("    INDEX = 0x%.04X  # %d" % (c.index, c.index))
        print(f"    NAME = {fieldvalue(camel(c.name))}")
        print('')

        for m in c.allMethods():
            print(f'    class {camel(m.name)}(amqp_object.Method):')
            print('')
            methodid = m.klass.index << 16 | m.index
            print("        INDEX = 0x%.08X  # %d, %d; %d" %
                  (methodid, m.klass.index, m.index, methodid))
            print(f"        NAME = {fieldvalue(m.structName(),)}")
            print('')
            print(
                f"        def __init__(self{fieldDeclList(m.arguments)}):")
            print(fieldInitList('            ', m.arguments))
            print("        @property")
            print("        def synchronous(self):")
            print(f"            return {m.isSynchronous}")
            print('')
            genDecodeMethodFields(m)
            genEncodeMethodFields(m)

    for c in spec.allClasses():
        if c.fields:
            print('')
            print(f'class {c.structName()}(amqp_object.Properties):')
            print('')
            print(f"    CLASS = {camel(c.name)}")
            print("    INDEX = 0x%.04X  # %d" % (c.index, c.index))
            print(f"    NAME = {fieldvalue(c.structName(),)}")
            print('')

            index = 0
            if c.fields:
                for f in c.fields:
                    if index % 16 == 15:
                        index += 1
                    shortnum = index / 16
                    partialindex = 15 - (index % 16)
                    bitindex = shortnum * 16 + partialindex
                    print('    %s = (1 << %d)' % (flagName(None, f), bitindex))
                    index += 1
                print('')

            print(f"    def __init__(self{fieldDeclList(c.fields)}):")
            print(fieldInitList('        ', c.fields))
            genDecodeProperties(c)
            genEncodeProperties(c)

    print("methods = {")
    print(',\n'.join([
        f"    0x{m.klass.index << 16 | m.index:08X}: {m.structName()}"
        for m in spec.allMethods()
    ]))
    print("}")
    print('')

    print("props = {")
    print(',\n'.join([
        f"    0x{c.index:04X}: {c.structName()}"
        for c in spec.allClasses()
        if c.fields
    ]))
    print("}")
    print('')
    print('')

    print("def has_content(methodNumber):")
    print('    return methodNumber in (')
    for m in spec.allMethods():
        if m.hasContent:
            print(f'        {m.structName()}.INDEX,')
    print('    )')


if __name__ == "__main__":
    with open(PIKA_SPEC, 'w') as handle:
        sys.stdout = handle
        generate([f'{RABBITMQ_CODEGEN_PATH}/amqp-rabbitmq-0.9.1.json'])
