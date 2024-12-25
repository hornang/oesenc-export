# oesenc-export

oesenc-export is a command line tool to decrypt **oesu** chart files. **oesu** is one of the primary chart formats consumed by [OpenCPN](https://opencpn.org). oesenc-export does not perform the decryption itself, but communicates with the **oexserverd** service which performs the decryption. This means that oesenc-export must be used on a computer that already has a working chart installation.

The script has been developed and tested on Windows and Linux.

## Motivation

This software is provided with the following purposes in mind:

* For OpenCPN users the freedom to deploy your charts on as many devices you have onboard you vessel.
* Getting chart data to play with when creating your own chart software.
* Getting chart data for scientific research.

**Using unencrypted charts with OpenCPN requires changes to its source code.**

Please support [o-charts.org](https://o-charts.org/) by purchasing your charts there. Only use this script for the above purposes. Do not share decrypted chart data with third-parties. 

## Prerequisites

* The chart files you want to decrypt must be purchased and encrypted for your computer at o-chart.org.
* The [o-charts Plugin](https://opencpn.org/OpenCPN/plugins/ocharts.html)
* Python 3.8 or higher
* Python package `psutil`
* On Windows you also need Python package `pywin32`

Install the Python dependencies:

Debian based Linux distributions run:

```
sudo apt install python3 python3-psutil
```

Windows 10/11:

* Download and install [Python3](https://www.python.org/downloads/).
* Open a terminal and make sure Python3 is in your path:

```
pip3 install pywin32 psutil
```

## Running the script

If you acquired the charts as a zip file you need to unzip to a directory. The script needs to find the **oexserverd** executable. If you are running the old **oesenc_pi** plugin it will need to find **oeserverd**. You may need to modify the paths inside the script.

If the chart files have been unzipped to a folder `Device-XX-XXXX-XX` then the decrypt command will be something like this:

```
oesenc-export.py decrypt -i Device-XX-XXXX-XX -o exported
```
where `exported` is the desired output directory

The output of the command will look something like this:

```
Started decryption service: C:\Users\Username\AppData\Local\opencpn\plugins\oexserverd.exe
Created destination directory
Loaded chart keys from oeuSENC-XX-DEVICE.XML
Decrypting charts files:
 1 of 78: AB-01-1234A1.oesenc OK
 2 of 78: AB-02-1234B1.oesenc OK
 ...
78 of 78: AB-02-1234C1.oesenc OK
Copied other files
Decrypted 78 charts to directory: exported
```

Some older versions of OpenCPN allowed reading unencrypted chart files. Newer versions will not read unencrypted chart files without modifications to the source code.

### Displaying chart info

There is a command line switch to read the headers of a single chart file:

```
oesenc-export.py info -c exported/AB-01-1234A1.oesenc
Chart ok
Name:
Version:        201
PublishDate:    20150101
UpdateDate:     20201112
Source edition: 10:5
nativeScale:    1:12000
createDate:     20210201
soundingDate:   Approximate lowest astronomical tide
```

### How it works

Chart file reading and rendering in OpenCPN all happens inside the plugins. oesu format (and the now legacy oesenc format) are handled by the "o-charts_pi" plugin ("pi" for plugin). When you start OpenCPN a system daemon called **oexserverd** is automatically started by the plugin. o-charts_pi talks to **oexserverd** via pipes. When a chart file is to be opened o-charts_pi instructs **oexserverd** to open the file and perform an on-the-fly decryption while streaming the file via the pipe. **oexserverd** internally has calculated the decryption key based on some kind of machine identifier. **oexserverd** executable is not open source. Binaries for the most common platforms are provided in the [o-charts_pi git repository](https://github.com/bdbcat/o-charts_pi).

## Background

Many hydrographic offices do not publish nautical chart data into to the public domain. End customers must acquire charts from commercial chart distributors which is usually not in an open format. This makes it hard to get open nautical chart data.

A few likely reasons:

* The agreement between commercial chart distributor and the hydrographic offices force the commercial chart providers to provide copy-protection on the data that they distribute to end customers.
* Commercial chart distributors can make money on charts by forcing each customer to acquire charts directly from the distributor only.
* Encryption to some extent ensures that the files has not been altered by a third-party.

### oesu (OpenCPN Encrypted System Electronical Nautical Charts)

oesu charts are purchased via [o-charts.org](https://o-charts.org/). This site is an initiative to provide freshly updated charts for [OpenCPN](https://opencpn.org/). You can buy charts in the oesu format, which is a custom format supported only by OpenCPN. The oesu file format is a derived version of the S-57 data format. S-57 is an open vector format describing the chart's elements' spatial and informational properties according to an object model. S-57 is the international standard for chart exchange between hydrographic offices.

oesu charts are only distributed in an encrypted version to end customers. When you buy a chart on o-charts.org, you will be providing a target device signature which is used to encrypt the charts for a specific device. At runtime, the charts are decrypted using a hash of some kind of hardware identifier that matches the machine signature you provided when downloading the charts.

The encryption stops you from:

- Using your charts on as many devices as you want.
- Porting OpenCPN to other platforms on which the encryption scheme is not implemented.
- Writing your own chart plotter using data from oesu files.
