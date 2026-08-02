# Resource object code (Python 3)
# Created by: object code
# Created by: The Resource Compiler for Qt version 6.11.1
# WARNING! All changes made in this file will be lost!

from PySide6 import QtCore

qt_resource_data = b"\
\x00\x00\x01!\
<\
svg xmlns=\x22http:\
//www.w3.org/200\
0/svg\x22 width=\x2236\
\x22 height=\x2236\x22 vi\
ewBox=\x220 0 24 24\
\x22 fill=\x22none\x22 st\
roke=\x22#94a3b8\x22 s\
troke-width=\x221.6\
\x22 stroke-linecap\
=\x22round\x22 stroke-\
linejoin=\x22round\x22\
><path d=\x22M7 18a\
5 5 0 0 1-.6-9.9\
6A7 7 0 0 1 20 1\
0a4 4 0 0 1-1 7.\
87\x22/><path d=\x22M1\
2 12v9m0-9-3 3m3\
-3 3 3\x22/></svg>\x0a\
\
"

qt_resource_name = b"\
\x00\x05\
\x00o\xa6S\
\x00i\
\x00c\x00o\x00n\x00s\
\x00\x0a\
\x05x\xd4\xa7\
\x00u\
\x00p\x00l\x00o\x00a\x00d\x00.\x00s\x00v\x00g\
"

qt_resource_struct = b"\
\x00\x00\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x01\
\x00\x00\x00\x00\x00\x00\x00\x00\
\x00\x00\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x02\
\x00\x00\x00\x00\x00\x00\x00\x00\
\x00\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\
\x00\x00\x01\x9f\xc34\xbd\xe0\
"


def qInitResources():
    QtCore.qRegisterResourceData(
        0x03, qt_resource_struct, qt_resource_name, qt_resource_data
    )


def qCleanupResources():
    QtCore.qUnregisterResourceData(
        0x03, qt_resource_struct, qt_resource_name, qt_resource_data
    )


qInitResources()
