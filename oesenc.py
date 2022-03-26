#!/usr/bin/python3

import os
import struct
from enum import IntEnum

class RecordType(IntEnum):
    HEADER_SENC_VERSION = 1
    HEADER_CELL_NAME = 2
    HEADER_CELL_PUBLISHDATE = 3
    HEADER_CELL_EDITION = 4
    HEADER_CELL_UPDATEDATE = 5
    HEADER_CELL_UPDATE = 6
    HEADER_CELL_NATIVESCALE = 7
    HEADER_CELL_SENCCREATEDATE = 8
    HEADER_CELL_SOUNDINGDATUM = 9

    FEATURE_ID_RECORD = 64
    FEATURE_ATTRIBUTE_RECORD = 65
    FEATURE_GEOMETRY_RECORD_POINT = 80
    FEATURE_GEOMETRY_RECORD_LINE = 81
    FEATURE_GEOMETRY_RECORD_AREA = 82
    FEATURE_GEOMETRY_RECORD_MULTIPOINT = 83
    FEATURE_GEOMETRY_RECORD_AREA_EXT = 84

    VECTOR_EDGE_NODE_TABLE_EXT_RECORD = 85
    VECTOR_CONNECTED_NODE_TABLE_EXT_RECORD = 86
    VECTOR_EDGE_NODE_TABLE_RECORD = 96
    VECTOR_CONNECTED_NODE_TABLE_RECORD = 97

    CELL_COVR_RECORD = 98
    CELL_NOCOVR_RECORD = 99
    CELL_EXTENT_RECORD  = 100
    CELL_TXTDSC_INFO_FILE_RECORD = 101

    SERVER_STATUS_RECORD = 200

class OSENC_Record_Base:
    _type = 0
    _recordLength = 0
    _unpackObject = struct.Struct("=HI")

    def __init__(self):
        return

    def size(self):
        return self._unpackObject.size

    def type(self):
        return self._type

    def recordLength(self):
        return self._recordLength

    def unpack(self, data):
        (self._type, self._recordLength) =  self._unpackObject.unpack(data)

class Oesenc:
    _fileName = ''
    _version = 0
    _name = ''
    _publishDate = ''
    _edition = 0
    _updateDate = ''
    _update = ''
    _nativeScale = ''
    _createDate = ''
    _soundingDatum = ''
    _valid = False

    def __init__(self, file):
        with open(file, "rb") as f:
            self._fileName = file

            firstRecord = OSENC_Record_Base()
            firstRecord.unpack(f.read(firstRecord.size()))

            # https://github.com/bdbcat/o-charts_pi/commit/a58b0556f68b38ce69379d7e41bc50804c45104f
            if firstRecord.type() == RecordType.SERVER_STATUS_RECORD and firstRecord.recordLength() < 20:
                data = f.read(firstRecord.recordLength() - firstRecord.size())
            elif firstRecord.type() == RecordType.HEADER_SENC_VERSION and firstRecord.recordLength() >= 6 and firstRecord.recordLength() < 16:
                data = f.read(firstRecord.recordLength() - firstRecord.size())
                self._version = struct.unpack("=H", data)[0]
            else:
                return

            self._valid = True

            while(True):
                recordBase = OSENC_Record_Base()
                data = f.read(recordBase.size())

                if data == b"":
                    break

                recordBase.unpack(data)
                data = f.read(recordBase.recordLength() - recordBase.size())

                type = recordBase.type()

                if type == RecordType.HEADER_SENC_VERSION:
                    self._version = struct.unpack("=H", data)[0]

                elif type == RecordType.HEADER_CELL_NAME:
                    self._name = data.decode()

                elif type == RecordType.HEADER_CELL_PUBLISHDATE:
                    self._publishDate = data.decode()

                elif type == RecordType.HEADER_CELL_EDITION:
                    self._edition = struct.unpack("=H", data)[0]

                elif type == RecordType.HEADER_CELL_UPDATEDATE:
                    self._updateDate = data.decode()

                elif type == RecordType.HEADER_CELL_UPDATE:
                    self._update = struct.unpack("=H", data)[0]

                elif type == RecordType.HEADER_CELL_NATIVESCALE:
                    self._nativeScale = struct.unpack("=I", data)[0]

                elif type == RecordType.HEADER_CELL_SENCCREATEDATE:
                    self._createDate = data.decode()

                elif type == RecordType.HEADER_CELL_SOUNDINGDATUM:
                    self._soundingDatum = data.decode()

                else:
                    return
    def isValid(self):
        return self._valid

    def name(self):
        return self._name

    def nativeScale(self):
        return self._nativeScale

    def publishDate(self):
        return self._publishDate

    def print(self):
        if not self._valid:
            print("Not valid")
            return
        outputLeft = ('│ Name:           {:<40}│\n'
                      '│ Version:        {:<39}│\n'
                      '│ PublishDate:    {:<40}│\n'
                      '│ UpdateDate:     {:<40}│\n'
                      '│ Source edition: {:<39}│\n'
                      '│ nativeScale:    {:<39}│\n'
                      '│ createDate:     {:<40}│\n'
                      '│ soundingDate:   {:<40}│\n').format(self._name,
                                              self._version,
                                              self._publishDate,
                                              self._updateDate,
                                              '{}:{}'.format(self._edition, self._update),
                                              '1:{}'.format(self._nativeScale),
                                              self._createDate,
                                              self._soundingDatum)

        length = 0

        for line in outputLeft.splitlines():
            if len(line) > length:
                length = len(line)

        topLine = '╭' + '─' * (length - 3) + '╮'
        bottomLine = '╰' + '─' * (length - 3) + '╯'
        print(topLine + '\n' + outputLeft + bottomLine)
