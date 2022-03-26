# oesenc-export

A python script to export decrypted data from oesenc chart files. The script pretends to be the oesenc_pi plugin and talks with the decryption service **oeserverd**.

The script has been tested on Windows and Linux.

## Motivation

This software is provided with the following purposes in mind:

* Freedom to deploy your oesenc charts on as many devices you have onboard you vessel.
* Getting chart data to play with when creating your own charting software.
* Getting chart data for scientific research.

Please support o-charts.org by purchasing your charts there. Only use this script for the above purposes. Do not share unencrypted chart data with third-parties.

## Prerequisites

* The [oeSENC Charts Plugin](https://opencpn.org/OpenCPN/plugins/oesenc.html)
* Python 3.8 or higher
* Python package `psutil`
* On Windows you also need Python package `pywin32`

Install the Python dependencies:

Debian based Linux distributions run:

```
sudo apt install python3 python3-psutil
```

Windows 10:

* Download and install [Python3](https://www.python.org/downloads/).
* Open a terminal and make sure Python3 is in your path:

```
pip3 install pywin32 psutil
```

## Running the script

Unzip the oesenc chart archive. The script needs to find **oeserverd** exectuable. You may need to modify the path inside the script.

If the chart files have been unzipped to a folder `Device-XX-XXXX-XX` then the decrypt command will along the following line:

```
oesenc-export.py decrypt -i Device-XX-XXXX-XX -o exported
```
where `exported` is the desired output directory

The output of the command will look something like this:

```
✔ Found UserKey in Chartinfo.txt
oeserverd running
✔ Created destination directory
✔ Created random pipe /tmp/DIDXYT
Decrypting charts files:
 1 of 78: AB-01-1234A1.oesenc ✔ OK
 2 of 78: AB-02-1234B1.oesenc ✔ OK
 ...
78 of 78: AB-02-1234B1.oesenc ✔ OK
✔ Copied other files
╭────────────────────────────────────────────╮
│ Decrypted 78 charts to directory: exported │
╰────────────────────────────────────────────╯
```

You can then add the unencrypted folder to OpenCPN as you would with the encrypted variant.

In some cases the oesenc_pi plugin may not accept reading unencrypted chart files. If that happens you will need to modify the source code of oesenc_pi slightly and build your own version.

### Displaying chart info

There is a command line switch to read the headers of a single chart file:

```
oesenc-export.py info -c exported/AB-01-1234A1.oesenc
╭────────────────────────────────────────────────────────╮
│ Name:                                                  │
│ Version:        201                                    │
│ PublishDate:    20150101                               │
│ UpdateDate:     20201112                               │
│ Source edition: 10:5                                   │
│ nativeScale:    1:12000                                │
│ createDate:     20210201                               │
│ soundingDate:   Approximate lowest astronomical tide   │
╰────────────────────────────────────────────────────────╯
✔ Chart ok
```

### How it works

Chart file reading and rendering in OpenCPN all happens inside the plugins. oesenc files are handled by the "oesenc_pi" plugin ("pi" for plugin). When you start OpenCPN a system daemon called **oeserverd** is automatically started by the plugin. oesenc_pi talks to **oeserverd** via pipes. When a chart file is to be opened oesenc_pi instructs **oeserverd** to open the file and perform an on-the-fly decryption while streaming the file via the pipe. **oeserverd** internally has calculated the decryption key based on some kind of machine identifier. **oeserverd** executable is not open source. Binaries for the most common platforms are provided in the [oesenc_pi git repository](https://github.com/bdbcat/oesenc_pi).

## Background

Many hydrological offices do not publish nautical chart data into to the public domain. End customers must acquire charts from commercial chart distributors which is usually not in an open format. This makes it hard to get open nautical chart data.

A few likely reasons:

* The agreement between commercial chart distributor and the hydrological offices force the commercial chart providers to provide copy-protection on the data that they distribute to end customers.
* Commercial chart distributors can make money on charts by forcing each customer to acquire charts directly from the distributor only.
* Encryption to some extent ensures that the files has not been altered by a third-party.

### oesenc (OpenCPN Encrypted System Electronical Nautical Charts)

oesenc charts are purchased via [o-charts.org](https://o-charts.org/). This site is an initiative to provide freshly updated charts for [OpenCPN](https://opencpn.org/). You can buy charts in the oesenc format which is a custom format supported only by OpenCPN. The oesenc file format is a derived version of the S-57 data format. S-57 is an open vector format describing the chart's elements' spatial and informational properties according to an object model. S-57 is the international standard for chart exchange between hydrological offices.

oesenc charts are only distributed in an encrypted version to end customers. When you buy a chart on o-charts.org you will be providing a target device signature which is used to encrypt the charts for a specific device. At runtime the charts are decrypted using a hash of some kind of hardware identifier that matches the machine signature you provided when downloading the charts.

The encryption stops you from:

- Using your charts on as many devices you want.
- Porting OpenCPN to to other platforms on which the encryption scheme is not implemented.
- Writing your own chart plotter using data from oesenc files.
