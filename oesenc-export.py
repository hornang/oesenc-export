#!/usr/bin/python3

"""
This program is based on code from https://github.com/bdbcat/oesenc_pi
commit 2d40cd43b7a33276723b9f1b445b9cb49810204b dated 30 Sep 2020.

"""

import os
import argparse
import sys
import struct
import random
import oesenc
import shutil
import logging
import subprocess
import asyncio
import signal, psutil
import string
import platform
import time

if platform.system() == 'Windows':
    import win32file
    import pywintypes
    import winerror

from enum import IntEnum

logging.basicConfig(format='%(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class OeserverdCmd(IntEnum):
    CMD_READ_ESENC = 0
    CMD_TEST_AVAIL = 1
    CMD_EXIT = 2
    CMD_READ_ESENC_HDR = 3

class fifo_msg():
    cmd = OeserverdCmd.CMD_READ_ESENC
    fifo_name = ''
    senc_name = ''
    senc_key = ''

    def pack(self):
        msg = struct.Struct("=c256s256s256s")
        data = msg.pack(bytes([self.cmd]),
                        self.fifo_name.encode(),
                        self.senc_name.encode(),
                        self.senc_key.encode())
        return data

def testPipe(pipeName):
    try:
        if platform.system() == 'Windows':
            pipe = os.open(pipeName, os.O_RDWR)
        else:
            pipe = os.open(pipeName, os.O_WRONLY)
        os.close(pipe)
    except OSError as e:
        return False
    return True

async def startOeservd(pipe):
    if testPipe(pipe):
        return True

    if platform.system() == 'Windows':
        exe = shutil.which("oeserverd.exe", path='C:\\Program Files (x86)\\OpenCPN\\plugins\\oesenc_pi')

        index = pipe.rfind('\\')
        pipeName = pipe[index + 1:]
        cmd = '"{}" -p {}'.format(exe, pipeName)
    else:
        cmd = shutil.which('/usr/bin/oeserverd')

    if cmd == None:
        log.warning('Unable to find oeserverd')
        return False

    proc = await asyncio.create_subprocess_shell(cmd, stdout=subprocess.DEVNULL)

    for counter in range(0, 50):
        await asyncio.sleep(0.1)
        if testPipe(pipe):
            return True

    return False

def requestStopOeserverd(pipeName):
    pipe = os.open(pipeName, os.O_WRONLY)
    msg = fifo_msg()
    msg.cmd = OeserverdCmd.CMD_EXIT
    data = msg.pack()
    os.write(pipe, data)
    os.close(pipe)

def createPipe(pipeName):
    os.mkfifo(pipeName)

def readPipe(fifoName, outputFile):
    with open(fifoName, 'rb') as fifo, open(outputFile, 'wb') as file:
        data = b''
        while True:
            newData = fifo.read()
            if len(newData) == 0:
                break
            file.write(newData)

def writeFile(data, path):
    with open(path, 'wb') as f:
        f.write(data)

def requestReadChart(chartFile, pipe, returnPipe, key):
    with open(pipe, 'wb') as f :
        msg = fifo_msg()
        msg.cmd = OeserverdCmd.CMD_READ_ESENC
        msg.fifo_name = returnPipe
        msg.senc_name = chartFile
        msg.senc_key = key
        data = msg.pack()
        f.write(data)

def exportChartFileWindows(chartFile, pipeName, outputFile, key):
    handle = win32file.CreateFile(pipeName,
        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
        0,
        None,
        win32file.OPEN_EXISTING,
        0,
        None)

    msg = fifo_msg()
    msg.cmd = OeserverdCmd.CMD_READ_ESENC
    msg.senc_name = chartFile
    msg.senc_key = key
    data = msg.pack()
    win32file.WriteFile(handle, data)

    output = os.open(outputFile, os.O_WRONLY | os.O_CREAT | os.O_BINARY)

    while True:
        try:
            data = win32file.ReadFile(handle, 1024*1024)
            os.write(output, data[1])
        except pywintypes.error as e:
            if e.args[0] == winerror.ERROR_PIPE_NOT_CONNECTED:
                break
            raise e
    os.close(output)
    win32file.CloseHandle(handle)

def parseChartInfo(path):
    chartInfo = {}
    try:
        userKeyLine = ''
        with open(path, 'r') as file:
            for line in file:
                userKeyLine = line
                parts = userKeyLine.split(':')
                if len(parts) == 2:
                    chartInfo[parts[0].strip()] = parts[1].strip()

    except FileNotFoundError as e:
        print('Unable to open the file: {}'.format(path))
    return chartInfo

def copyFilesAndDirs(basePath, input, destination):
    for element in input:
        elementPath = os.path.join(basePath, element)
        if os.path.isdir(elementPath):
            shutil.copytree(elementPath, os.path.join(destination, element))
        else:
            shutil.copy(elementPath, destination)

def unencryptChart(path, destination):
    chartInfoFile = os.path.join(path, 'Chartinfo.txt')
    chartInfo = parseChartInfo(os.path.join(path, 'Chartinfo.txt'))

    if 'UserKey' not in chartInfo:
        log.error('Missing "UserKey" field in: {}'.format(chartInfoFile))
        return

    log.info('✔ Found UserKey in Chartinfo.txt')

    if platform.system() == 'Windows':
        pipeName = '\\\\.\\pipe\\ocpn_pipe'
    else:
        pipeName= '/tmp/OCPN_PIPE'

    if asyncio.run(startOeservd(pipeName)):
        log.info('oeserverd running')
    else:
        log.fatal("Unable to start oeserverd")
        return False

    if os.path.isdir(destination):
        log.fatal("❌ Destination exists")
        requestStopOeserverd(pipeName)
        return False

    os.mkdir(destination)
    log.info('✔ Created destination directory')

    listing = os.listdir(path)
    chartFiles = [file for file in listing if file.endswith('.oesenc')]
    otherFiles = set(listing) - set(chartFiles)

    if platform.system() != 'Windows':
        possibleLetters = string.ascii_lowercase + string.ascii_uppercase + string.digits
        returnPipeName = '/tmp/' + ''.join((random.choice(possibleLetters) for i in range(6)))
        createPipe(returnPipeName)
        log.info('✔ Created random pipe {}'.format(returnPipeName))

    totalString = '{}'.format(len(chartFiles))
    numFailed = 0

    log.info('Decrypting charts files:')

    for counter, chartFile in enumerate(chartFiles):
        fullPathToChart = os.path.abspath(os.path.join(path, chartFile))
        outputFile = os.path.join(destination, chartFile)

        if platform.system() == 'Windows':
            exportChartFileWindows(fullPathToChart, pipeName, outputFile, chartInfo['UserKey'])
        else:
            requestReadChart(fullPathToChart, pipeName, returnPipeName, chartInfo['UserKey'])
            readPipe(returnPipeName, outputFile)

        chart = oesenc.Oesenc(outputFile)

        if chart.isValid():
            text = '✔ OK'
            color = '32'
        else:
            color = '31'
            text = '❌ Failed to validate decrypted chart'
            numFailed +=1

        output = '{:>{width}} of {}: {}\x1b[{color}m {}\x1b[39m'.format(counter + 1, len(chartFiles), chartFile, text, color=color, width=len(totalString))

        if chart.isValid():
            log.info(output)
        else:
            log.warning(output)

    numFailedText = ''
    if numFailed > 0:
        numFailedText = 'and {} failed '.format(numFailed)

    requestStopOeserverd(pipeName)

    if platform.system() != 'Windows':
        os.remove(returnPipeName)

    copyFilesAndDirs(path, otherFiles, destination)
    log.info('✔ Copied other files')

    output = '│ Decrypted {} charts {}to directory: {} │'.format(len(chartFiles), numFailedText, destination)
    log.info('╭' + '─' * (len(output) - 2) + '╮')
    log.info(output)
    log.info('╰' + '─' * (len(output) - 2) + '╯')

    return True

def handleDecrypt(args):
    unencryptChart(args.input_dir, args.output_dir)

def handleInfo(args):
    chartFile = args.chart_file
    chart = oesenc.Oesenc(chartFile)
    if chart.isValid():
        chart.print()
        log.fatal('✔ Chart ok')
    else:
        log.fatal('❌ Unable to parse chart')

parser = argparse.ArgumentParser(description='')
subparsers = parser.add_subparsers(help='Command')

decryptParser = subparsers.add_parser('decrypt', help='Decrypt chart directory', description='Decrypt all charts in a chart directory and output to another directory')
decryptParser.add_argument('-i', '--input-dir', help='Input chart director', required=True, type=str)
decryptParser.add_argument("-o", '--output-dir', help="Input chart director", required=True, type=str)
decryptParser.set_defaults(func=handleDecrypt)

infoParser= subparsers.add_parser('info', help='Print info about chart', description='Reads an already decrypted chart and prints its header data to stdout')
infoParser.add_argument('-c', '--chart-file', help='The path to the oesenc chart', required=True, type=str)
infoParser.set_defaults(func=handleInfo)

args = parser.parse_args()

if hasattr(args, 'func'):
    args.func(args)
else:
    parser.print_help()
