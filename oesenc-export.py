#!/usr/bin/python3

import os
import argparse
import enum
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
import xml.dom.pulldom

if platform.system() == 'Windows':
    import win32file
    import pywintypes
    import winerror

logging.basicConfig(format='%(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class OeserverdCmd(enum.IntEnum):
    CMD_READ_ESENC = 0
    CMD_TEST_AVAIL = 1
    CMD_EXIT = 2
    CMD_READ_ESENC_HDR = 3
    CMD_READ_OESU = 8

class ServiceType(enum.Enum):
    Oeserver = 1
    Oexserver = 2

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

class fifo_msg_oexserverd():
    cmd = OeserverdCmd.CMD_READ_ESENC
    fifo_name = ''
    senc_name = ''
    senc_key = ''

    def pack(self):
        msg = struct.Struct("=c256s256s512s")
        data = msg.pack(bytes([self.cmd]),
                        self.fifo_name.encode(),
                        self.senc_name.encode(),
                        self.senc_key.encode())
        return data

def parseXmlList(path : str):
    chartLevel = 0
    fileName = ''
    installKey = ''
    charts = {}
    xmlPath = []

    doc = xml.dom.pulldom.parse(path)

    for event, node in doc:
        if event == xml.dom.pulldom.START_ELEMENT:
            chartLevel += 1
            xmlPath.append(node.tagName)

        elif event == xml.dom.pulldom.END_ELEMENT:
            if xmlPath == ['keyList', 'Chart']:
                charts[fileName] = installKey
                installKey = ''
                fileName = ''
            chartLevel -= 1
            xmlPath.pop()

        elif event == xml.dom.pulldom.CHARACTERS:
            if xmlPath == ['keyList', 'Chart', 'FileName']:
                fileName += node.data
            elif xmlPath == ['keyList', 'Chart', 'RInstallKey']:
                installKey += node.data

    return charts

def locateService():
    if platform.system() == 'Windows':
        oexserverdDir = os.path.expandvars(r'%LOCALAPPDATA%\opencpn\plugins')
        exe = shutil.which("oexserverd.exe", path=oexserverdDir)

        if exe != None:
            return exe
        else:
            return shutil.which("oeserverd.exe", path=r'C:\Program Files (x86)\OpenCPN\plugins\oesenc_pi')

    else:
        oexserverdDirs = [os.path.expandvars('$HOME/.var/app/org.opencpn.OpenCPN/bin'),
                          os.path.expandvars('$HOME/.local/bin'),
                          '/usr/local/bin',
                          '/usr/bin',
                          '/usr/lib/avnav/plugins/ocharts/bin/',
                          '/usr/lib/avnav/plugins/ochartsng']

        for dir in oexserverdDirs:
            exe = shutil.which('oexserverd', path=dir)
            if exe != None:
                return exe

        oeserverDirs = ['/usr/local/bin/', '/usr/bin/']

        for dir in oeserverDirs:
            exe = shutil.which('oeserverd', path=dir)
            if exe != None:
                return exe

    return None

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

async def startOeservd(path, pipe):
    if testPipe(pipe):
        log.info("Decryption service already running")
        return True

    if platform.system() == 'Windows':
        index = pipe.rfind('\\')
        pipeName = pipe[index + 1:]
        cmd = '"{}" -p {}'.format(path, pipeName)
    else:
        cmd = path

    proc = await asyncio.create_subprocess_shell(cmd, stdout=subprocess.DEVNULL)

    for counter in range(0, 50):
        await asyncio.sleep(0.1)
        if testPipe(pipe):
            log.info('Started decryption service: {}'.format(path))
            return True

    return False

def requestStopOeserverd(pipeName, serviceType):
    pipe = os.open(pipeName, os.O_WRONLY)

    if serviceType == ServiceType.Oexserver:
        msg = fifo_msg_oexserverd()
    elif serviceType == ServiceType.Oeserver:
        msg = fifo_msg()

    msg.cmd = OeserverdCmd.CMD_EXIT
    data = msg.pack()
    os.write(pipe, data)
    os.close(pipe)

def createPipe(pipeName):
    os.mkfifo(pipeName)

def readPipe(fifoName, outputFile):
    readSize = 0
    with open(fifoName, 'rb') as fifo, open(outputFile, 'wb') as file:
        data = b''
        while True:
            newData = fifo.read()
            if len(newData) == 0:
                break
            readSize += len(newData)
            file.write(newData)
    return readSize > 0

def writeFile(data, path):
    with open(path, 'wb') as f:
        f.write(data)

def requestReadChart(chartFile, pipe, returnPipe, key, serviceType):
    with open(pipe, 'wb') as f :
        extension = os.path.splitext(chartFile)[1]
        if extension == ".oesu":
            cmd = OeserverdCmd.CMD_READ_OESU
        elif extension == ".oesenc":
            cmd = OeserverdCmd.CMD_READ_ESENC
        else:
            log.error('Unknown file extension: {}'.format(chartFile))
            return False

        if serviceType == ServiceType.Oexserver:
            msg = fifo_msg_oexserverd()
        elif serviceType == ServiceType.Oeserver:
            if extension == ".oesu":
                log.error('Cannot decrypt oesu format with oeserverd')
                return False
            msg = fifo_msg()

        msg.cmd = cmd
        msg.fifo_name = returnPipe
        msg.senc_name = chartFile
        msg.senc_key = key
        data = msg.pack()
        f.write(data)
        return True

    return False

def exportChartFileWindows(chartFile, pipeName, outputFile, key, serviceType):
    extension = os.path.splitext(chartFile)[1]

    if extension == ".oesu":
        cmd = OeserverdCmd.CMD_READ_OESU
    elif extension == ".oesenc":
        cmd = OeserverdCmd.CMD_READ_ESENC
    else:
        log.error('Unknown file extension: {}'.format(chartFile))
        return False

    if serviceType == ServiceType.Oexserver:
        msg = fifo_msg_oexserverd()
        msg.cmd = cmd
        msg.senc_name = chartFile
        msg.senc_key = key
    elif serviceType == ServiceType.Oeserver:
        if extension == ".oesu":
            log.error('Cannot decrypt oesu format with oeserver')
            return False

        msg = fifo_msg()
        msg.cmd = cmd
        msg.senc_name = chartFile
        msg.senc_key = key

    data = msg.pack()

    handle = win32file.CreateFile(pipeName,
        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
        0,
        None,
        win32file.OPEN_EXISTING,
        0,
        None)

    win32file.WriteFile(handle, data)

    output = os.open(outputFile, os.O_WRONLY | os.O_CREAT | os.O_BINARY)

    readAnyData = False
    while True:
        try:
            data = win32file.ReadFile(handle, 1024*1024)
            os.write(output, data[1])
            readAnyData = True
        except pywintypes.error as e:
            if e.args[0] == winerror.ERROR_PIPE_NOT_CONNECTED:
                break
            raise e
    os.close(output)
    win32file.CloseHandle(handle)

    if not readAnyData:
        return False

    return True

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
    servicePath = locateService()

    if servicePath == None:
        log.fatal('Unable to locate decryption service')
        return False

    if 'oexserver' in servicePath:
        serviceType = ServiceType.Oexserver
    else:
        serviceType = ServiceType.Oeserver

    if platform.system() == 'Windows':
        pipeName = '\\\\.\\pipe\\ocpn_pipe'
    else:
        if serviceType == ServiceType.Oexserver:
            pipeName= '/tmp/OCPN_PIPEX'
        else:
            pipeName= '/tmp/OCPN_PIPE'

    if not asyncio.run(startOeservd(servicePath, pipeName)):
        log.fatal("Unable to start {}".format(servicePath))
        return False

    if os.path.isdir(destination):
        log.fatal("Destination exists")
        requestStopOeserverd(pipeName, serviceType)
        return False

    os.mkdir(destination)
    log.info('Created destination directory')

    listing = os.listdir(path)
    chartFiles = [file for file in listing if file.endswith('.oesu') or file.endswith(".oesenc")]
    otherFiles = set(listing) - set(chartFiles)

    if not chartFiles:
        log.warning('No oeseu or oesenc chart files in dir: {}'.format(path))
        return False

    if platform.system() != 'Windows':
        possibleLetters = string.ascii_lowercase + string.ascii_uppercase + string.digits
        returnPipeName = '/tmp/' + ''.join((random.choice(possibleLetters) for i in range(6)))
        createPipe(returnPipeName)
        log.info('Created random pipe {}'.format(returnPipeName))

    totalString = '{}'.format(len(chartFiles))
    numFailed = 0

    chartInfoFile = os.path.join(path, 'Chartinfo.txt')

    userKey = ''

    if os.path.isfile(chartInfoFile):
        chartInfo = parseChartInfo(os.path.join(path, 'Chartinfo.txt'))
        if 'UserKey' in chartInfo:
            log.info('Found UserKey in Chartinfo.txt')
            userKey = chartInfo['UserKey']

    xmlFiles = [file for file in listing if file.lower().endswith('.xml')]

    chartKeys = {}
    for xmlFile in xmlFiles:
        chartKeys = parseXmlList(os.path.join(path, xmlFile))
        if chartKeys:
            log.info('Loaded chart keys from {}'.format(xmlFile))
            break

    log.info('Decrypting charts files:')

    oesuFileFailed = False

    for counter, chartFile in enumerate(chartFiles):
        fullPathToChart = os.path.abspath(os.path.join(path, chartFile))
        outputFile = os.path.join(destination, chartFile)

        if chartFile.endswith('.oesu'):
            baseName = os.path.splitext(chartFile)[0]
            if baseName not in chartKeys:
                log.warning('No key found for chart {}'.format(chartFile))
                numFailed += 1
                continue
            chartKey = chartKeys[baseName]
        elif chartFile.endswith('.oesenc'):
            chartKey = userKey
        else:
            continue

        if platform.system() == 'Windows':
            if not exportChartFileWindows(fullPathToChart, pipeName, outputFile, chartKey, serviceType):
                log.warning('{}: No data from encryption service'.format(chartFile))
                oesuFileFailed |= fullPathToChart.endswith('.oesu')
                numFailed += 1
                continue
        else:
            if not requestReadChart(fullPathToChart, pipeName, returnPipeName, chartKey, serviceType):
                log.warning('{}: No data from encryption service'.format(chartFile))
                oesuFileFailed |= fullPathToChart.endswith('.oesu')
                numFailed += 1
                continue

            if not readPipe(returnPipeName, outputFile):
                numFailed += 1
                continue

        chart = oesenc.Oesenc(outputFile)

        if chart.isValid():
            text = 'OK'
        else:
            text = 'Failed to validate decrypted chart'
            numFailed +=1

        output = '{:>{width}} of {}: {} {}'.format(counter + 1, len(chartFiles), chartFile, text, width=len(totalString))

        if chart.isValid():
            log.info(output)
        else:
            log.warning(output)

    numFailedText = ''
    if numFailed > 0:
        numFailedText = 'and {} failed '.format(numFailed)

    if oesuFileFailed:
        log.warning('Please ensure oeserverd is not running and try again')
        requestStopOeserverd(pipeName, ServiceType.Oeserver)
    else:
        requestStopOeserverd(pipeName, serviceType)

    if platform.system() != 'Windows':
        os.remove(returnPipeName)

    if numFailed == len(chartFiles):
        log.warning('Failed to decrypt any chart')
        return False

    copyFilesAndDirs(path, otherFiles, destination)
    log.info('Copied other files')
    log.info('Decrypted {} charts {}to directory: {}'.format(len(chartFiles), numFailedText, destination))

    return True

def handleDecrypt(args):
    unencryptChart(args.input_dir, args.output_dir)

def handleInfo(args):
    chartFile = args.chart_file
    chart = oesenc.Oesenc(chartFile)
    if chart.isValid():
        chart.print()
        log.info('Chart ok')
    else:
        log.fatal('Unable to parse chart')

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
