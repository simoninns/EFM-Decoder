########################################################################
# finalize.py takes the output of bit2sec.py passes and constructs an adl
# file of 2048 byte sectors which have had Q- and P-Parity correction 
# applied. 
#    Copyright (C) 2018  Steve Dome
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.#
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    A copy of the GNU General Public License
#    may be found at <https://www.gnu.org/licenses/>.
# The author may be contacted via 'steve at xscs1 dot org dot uk'
########################################################################
import sys
import argparse as ap

#
from bitstring import *
import pycrc.pycrc as pycrc
from pycrc.crc_opt import Options
# pycrc (and crc_opt) is available under the MIT licence from 
# pycrc.org
from rscd.rscd import RSCoder
# rscd.py (possibly now rs.py) is available under the MIT license from
# Andrew Brownan on github
#----------------------------------------------------
sectorMap = {}
subcodeMap = {}
#----------------------------------------------------
optEDC = Options()
optEDC.UndefinedCrcParameters = False
optEDC.Algorithm = 4
optEDC.Width = 0x20
optEDC.Poly = 0x8001801b
optEDC.ReflectIn = True
optEDC.ReflectOut = True
optEDC.XorIn = 0
#
#
optCRC = Options()
optCRC.UndefinedCrcParameters = False
optCRC.Algorithm = 4
optCRC.Width = 0x10
optCRC.Poly = 0x1021
optCRC.ReflectIn = False
optCRC.ReflectOut = False
optCRC.XorIn = 0
#
#
P = RSCoder(26,24,2)
Q = RSCoder(45,43,2)
#
Goodsync = Bits(hex='00ffffffffffffffffffff00')
# -----------------------------------------------
def sectorFromTime(time):
  m1,m2,s1,s2,f1,f2 = time.unpack(6*'uint:4,')
  sector = (60*(10*m1+m2)+(10*s1 + s2))*75 + 10*f1+f2
  return (sector - (2*75+30) )

def sectorInSequence(a,b):
  return True
# ==============================================
def checkCRC(data,check):
  global optCRC
  optCRC.CheckString = data.bytes
  optCRC.XorOut = check.uint
  return (pycrc.check_string(optCRC) == 0xffff)
# ---------------------------------------------
def processSubcodes(sc):
  flag, qCtrl,qMode,qData,qcrc,rest = sc.unpack('bits:96,'+2*'bits:4,'+'bits:72,'+'bits:16,hex:576')
  crcOK = checkCRC(qCtrl+qMode+qData,qcrc)
  if qMode.hex == '1':
    TNO,idx,rtime,_,time = qData.unpack(2*'bits:8,'+'bits:24,'+'bytes:1,'+'bits:24')
    values = {'qCtrl':qCtrl.hex,'qMode': qMode.hex,'TNO':TNO,'idx':idx,'rtime':rtime,\
       'time':time,'Trk':TNO.hex,'Ind':idx.hex,'T':time.hex} 
    if (args.debug & 0x01) == 0x01:
      if crcOK: print('T %(qCtrl)1s %(qMode)1s %(Trk)02s %(Ind)02s %(T)06s' % values)
      else:     print('F %(qCtrl)1s %(qMode)1s %(Trk)02s %(Ind)02s %(T)06s' % values)
  elif qMode.hex == '2':
    catalogue,_,afrac = qData.unpack('hex:52,hex:12,hex:8')
    values = {'qCtrl':qCtrl.hex,'qMode':qMode.hex,'Cat':catalogue}
    if (args.debug & 0x01) == 0x01 :
      if crcOK: print('T %(qCtrl)1s %(qMode)1s Catalogue Number = %(Cat)013s' % values)
      else:     print('T %(qCtrl)1s %(qMode)1s Catalogue Number = %(Cat)013s' % values)
  else: values = {}
  return crcOK,values
# ---------------------------------------------
def writeSubcodes(no,sc):
  pass
# ==============================================

def checkEDC(data,check):
  global optEDC
  optEDC.CheckString = data.bytes
  check.byteswap()
  optEDC.XorOut = check.uint
  return pycrc.check_string(optEDC)
# ---------------------------------------------
def processSection(sn):
  global P,Q,Goodsync
  edcfield, edc = sn.unpack('bits:16512,bits:32')
  edcOK = (checkEDC(edcfield,edc) == 0)
  out = ''# for diagnostic printing
  if edcOK:
    sync,time,mode,userdata = edcfield.unpack('bytes:12,bits:24,uint:8,bits:16384')
  else:  # try error correction
    sync , field = sn.unpack('bits:96,bytes:2340')
    Qfield, QParity = bytearray(field[0:2236]), bytearray(field[2236:])
    # Process Q parity first
    for even in (0,1):
      for Nq in range(26):
        f = [Qfield[2*((44*Mq+43*Nq) % 1118) + even] for Mq in range(43)] \
               + [ QParity[2*((43*26+Nq) % 1118)+even] ] + [ QParity[2*((44*26+Nq)% 1118)+even] ]
        f, okQ, repaired = Q.process(f)
        if okQ and not repaired: out = out+'.'
        elif okQ and repaired:
          out = out + '_'
          for Mq in range(43):
            Qfield[2*((44*Mq+43*Nq) % 1118) + even] = f[Mq]
        else:  out = out + 'X'
    # Then process P parity
    out = out + '  ---  '
    for even in (0,1):
      for Np in range(43):
        f = [Qfield[2*(43*Mp+Np) + even] for Mp in range(26)]
        f, okP,repaired = P.process(f)
        if okP and not repaired:  out = out + '.'
        elif okP and repaired:
          out = out + '_'
          for Mp in range(26):
            Qfield[2*((43*Mp+Np) % 1118) + even] = f[Mp]
        else:  out = out+'X'
    #
    # Re-check EDC
    userdata, check = Goodsync + BitString(bytes=Qfield[0:2052]), BitString(bytes=Qfield[2052:2056])
    edcOK = ( checkEDC(userdata, check) == 0)
    sync,time,mode,userdata = userdata.unpack('bytes:12,bits:24,uint:8,bits:16384')
  if edcOK: out = out + ' T'
  else:     out = out + ' F'
  values = {'time':time,'mode':mode,'sector':userdata} 
  if ((args.debug & 0x02 ) == 0x02) and ( out == ' T'): print('%09i' % (sectorFromTime(time),))
  elif  ((args.debug & 0x04 ) == 0x04) and (out !=' T'): print('%09i %s' % (sectorFromTime(time),out))
  return edcOK, values

#----------------------------------------------
def writeSector(no,crcOK,edcOK,sr):
  global adlImage, sectorMap
  if (no >= 0) and (no < args.maxsector):
    pos = no * 2048 * 8
    if (sectorMap[no]['source'] == 'Init'):
      adlImage[pos:pos+2048*8] = sr
      sectorMap[no] = {'source': 'pass','edcOK' : edcOK}
      if not edcOK: print('EDC error at sector %i ' % no) 
    elif (sectorMap[no]['edcOK'] == False):
      adlImage[pos:pos+2048*8] = sr
      sectorMap[no] = {'source': 'pass','edcOK' : edcOK}
      if edcOK: print('EDC repaired at sector %i ' % no) 
      else:
        if crcOK:
          print('EDC hard(?) error at sector %i ' % no)
        else:
          print('EDC hard(?) error at sector %i  '\
                '- *** possible write to incorrect sector ***' % no) 

# ==============================================
def processImage(image):
  global adlImage,subcodeImage
  global sectorMap, subcodeMap
  sectionLength = 8*2352
  subcodeLength = 8*96
  readlength = subcodeLength + sectionLength
  finalpos = image.len-readlength
  # Skip over pre-gap
  pregap = True
  while pregap:
    subcodes, section = image.readlist('bits:%i,bits:%i'% (subcodeLength,sectionLength))
    p,_ = subcodes.unpack('bits:96,bytes:84')
    if p.count(1) > 48: pregap = False
  # Find start of info track
  inInfoTrk = False
  while not inInfoTrk:
    subcodes, section = image.readlist('bits:%i,bits:%i'% (subcodeLength,sectionLength))
    p,_ = subcodes.unpack('bits:96,bytes:84')
    if p.count(0) > 48: inInfoTrk = True
  # process pre-sectors
  prevSector=-30
  while prevSector < 0:
    subcodes, section = image.readlist('bits:%i,bits:%i'% (subcodeLength,sectionLength))
    crcOK, subValues = processSubcodes(subcodes)
    edcOK, secValues = processSection(section)
    if edcOK:
      sectorNumber = sectorFromTime(secValues['time'])
    else:
      sectorNumber = prevSector + 1
    prevSector = sectorNumber
    # write sector if reqd  
  # process 'adl' image
  writeSector(0,crcOK,edcOK,secValues['sector'])
  prevSector = 0
  while image.pos  < finalpos:
    subcodes, section = image.readlist('bits:%i,bits:%i'% (subcodeLength,sectionLength))
    crcOK, subValues = processSubcodes(subcodes)
    edcOK, secValues = processSection(section)
    if edcOK:
      sectorNumber = sectorFromTime(secValues['time'])
    elif crcOK:
      if subValues['qMode'] == 1:
        sectorNumber = sectorFromTime(subValues['time'])
      else:
        sectorNumber = prevSector + 1
    else: # include this to write uncorrected sectors - may be in wrong sector location!
      sectorNumber = sectorFromTime(secValues['time'])
      if sectorNumber != prevSector + 1:
        sectorNumber = prevSector + 1
    writeSector(sectorNumber,crcOK,edcOK,secValues['sector'])
    prevSector = sectorNumber
      

  
#======================================================================
def InitializeImages(volname):
  global adlImage
  global sectorMap 
  sector = b'\x00'*2048
  adlImage = BitStream(bytes=args.maxsector*sector)
  sectorMap = {}
  for i in range(args.maxsector):
    sectorMap[i] = {'source': 'Init', 'edcOK' : True}
#----------------------------------------------
def processVolume(v,w):
  global adlImage
  global args
  try:
    image = BitStream(filename='%s/%s%s.img' % (args.src,v,w))
    processImage(image)
  finally:
    # save adl image
    f = open('%s/%s.adl' % (args.dst,v),'wb');  adlImage.tofile(f); f.close()
#======================================================================
if __name__ == "__main__":
  # process options
  parser = ap.ArgumentParser(description='This converts raw subcodes and sectors to an .adl file',add_help=True,version='0.6')
  parser.add_argument('--src',action='store',default='../data',help='Source file directory')
  parser.add_argument('--dst',action='store',default='../data',help='Destination file directory')
  parser.add_argument('--title',action='append',default=[],help='Volume name - repeat for multiple')
  parser.add_argument('--ps',action='append',default=['1'],help='Versions of each file to process - repeat for multiple')
  #
  parser.add_argument('--maxsector',action='store',type=int,default=0x20000,help='no. of sectors reqd in adl image')
  parser.add_argument('--debug',action='store',type=int,default=0,help='debug print level')
  #
  args = parser.parse_args()
  for volume in args.title:
    InitializeImages(volume)
    for version in args.ps:
      print('Processing volume %s%s' % (volume,version))
      processVolume(volume, version)



