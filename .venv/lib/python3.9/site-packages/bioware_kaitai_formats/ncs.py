# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Ncs(KaitaiStruct):
    """NCS (NWScript Compiled) files contain compiled NWScript bytecode used in KotOR and TSL.
    Scripts run inside a stack-based virtual machine shared across Aurora engine games.
    
    Format Structure:
    - Header (13 bytes): Signature "NCS ", version "V1.0", size marker (0x42), file size
    - Instruction Stream: Sequence of bytecode instructions
    
    All multi-byte values in NCS files are stored in BIG-ENDIAN byte order (network byte order).
    
    References:
    - NSS.ksy - NWScript source code that compiles to NCS
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(Ncs, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.file_type = (self._io.read_bytes(4)).decode(u"ASCII")
        if not self.file_type == u"NCS ":
            raise kaitaistruct.ValidationNotEqualError(u"NCS ", self.file_type, self._io, u"/seq/0")
        self.file_version = (self._io.read_bytes(4)).decode(u"ASCII")
        if not self.file_version == u"V1.0":
            raise kaitaistruct.ValidationNotEqualError(u"V1.0", self.file_version, self._io, u"/seq/1")
        self.size_marker = self._io.read_u1()
        if not self.size_marker == 66:
            raise kaitaistruct.ValidationNotEqualError(66, self.size_marker, self._io, u"/seq/2")
        self.file_size = self._io.read_u4be()
        self.instructions = []
        i = 0
        while True:
            _ = Ncs.Instruction(self._io, self, self._root)
            self.instructions.append(_)
            if self._io.pos() >= self.file_size:
                break
            i += 1


    def _fetch_instances(self):
        pass
        for i in range(len(self.instructions)):
            pass
            self.instructions[i]._fetch_instances()


    class Instruction(KaitaiStruct):
        """NWScript bytecode instruction.
        Format: <opcode: uint8> <qualifier: uint8> <arguments: variable>
        
        Instruction size varies by opcode:
        - Base: 2 bytes (opcode + qualifier)
        - Arguments: 0 to variable bytes depending on instruction type
        
        Common instruction types:
        - Constants: CONSTI (6B), CONSTF (6B), CONSTS (2+N B), CONSTO (6B)
        - Stack ops: CPDOWNSP, CPTOPSP, MOVSP (variable size)
        - Arithmetic: ADDxx, SUBxx, MULxx, DIVxx (2B)
        - Control flow: JMP, JSR, JZ, JNZ (6B), RETN (2B)
        - Function calls: ACTION (5B)
        - And many more (see NCS format documentation)
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(Ncs.Instruction, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.opcode = self._io.read_u1()
            self.qualifier = self._io.read_u1()
            self.arguments = []
            i = 0
            while True:
                _ = self._io.read_u1()
                self.arguments.append(_)
                if self._io.pos() >= self._io.size():
                    break
                i += 1


        def _fetch_instances(self):
            pass
            for i in range(len(self.arguments)):
                pass




