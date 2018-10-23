########################################################################
# bit2wav.py takes a 'frames' file produced by fast.py from digital audio
# discs and outputs a .wav file.
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
#env python
from __future__ import print_function
import string, time, cPickle
import argparse as ap
from Queue import Queue
import wave
#
from bitstring import *
from rscd import RSCoder
#


F3LENGTH = 588
DEFAULT = 'error'
BitCount = 0
ChanErr = 0
FrameCount = 0
SectorCount = 0
C1_OK, C1_Err, C2_OK, C2_Err = 0, 0, 0, 0
EvenSync, OddSync = [0,255]+8*[255]+[255,0], [255,0]+8*[255]+[0,255]

from efmtab import efm
from efmsimtab import efmsim

#=====  Utility functions ======================================================
def matchEven(s):
  global EvenSync
  count = 0
  for x, y in zip(s,EvenSync):
    if x == y: count += 1
  return count >= 9

def matchOdd(s):
  global OddSync
  count = 0
  for x, y in zip(s,OddSync):
    if x == y: count += 1
  return count >= 9

#=================================================================================
def bin():
  global inputFile
  global BitCount
  xlate = {
     '0': Bits('0b1'), '1': Bits('0b1'+'0'), '2': Bits('0b1'+2*'0'), '3': Bits('0b1'+3*'0'),
     '4': Bits('0b1'+4*'0'), '5': Bits('0b1'+5*'0'), '6': Bits('0b1'+6*'0'), '7': Bits('0b1'+7*'0'),
     '8': Bits('0b1'+8*'0'), '9': Bits('0b1'+9*'0'), 'a': Bits('0b1'+10*'0'), 'b': Bits('0b1'+11*'0'),
     'c': Bits('0b1'+12*'0'), 'd': Bits('0b1'+13*'0'), 'e': Bits('0b1'+14*'0'), 'f': Bits('0b1'+15*'0'),
     }
  linecount, limit, maxcount = 0, False, 0
  if args.count > 0:
    limit = True
    maxcount = args.count
  with inputFile as g:
    if args.skip > 0:
      for i in range(args.skip): g.readline() # skip initial frames if required
    for s in g:                     # process rest of input
      b = Bits('')
      ss = s.strip()
      linecount += 1
      if limit and (linecount > maxcount): return # stop early if required
      if len(ss) > 0: 
        for c in ss: b += xlate[c]
        BitCount += 588
        yield b
#================================================================================
def GetSubCodes():
  subcode = BitString(8*96)
  sync0, sync1 = Bits('0b00100000000001'), Bits('0b00000000010010')
  binProc = bin()
  currentFrame = binProc.next()
  CB0 = currentFrame[27:41]
  index = 0
  for nextFrame in binProc:
    CB1 = nextFrame[27:41]
    sc = None
    if ((CB0 == sync0) and (CB1 == sync1)) or index >=96:
      sc = subcode
      subcode = BitString(8*96)
      index = 0
      CB1 = sync1
    elif (CB0 == sync1): pass
    else:
      cb = Bits(uint=efmsim[CB0],length=8)
      for i in range(8): subcode[index+96*i:index+96*i + 1] = cb[i:i+1]
      index += 1
    yield sc, currentFrame[44:]
    currentFrame, CB0 = nextFrame, CB1
#================================================================================
def ChannelFrame():
  global FrameCount, Sections
  global ChanErr

  for sc, x in GetSubCodes():
    FrameCount += 1  
    F2 = []
    for j in range(0,32*17,17):
      channelWord = x[j: 14 + j]
      code = efm.get(channelWord, DEFAULT)
      if code == DEFAULT:
        code = efmsim.get(channelWord,0)
        ChanErr += 1
      F2.append(code)
    yield sc, F2
#================================================================================
def DelayInv():
  i = ChannelFrame()
  sc, G = i.next()
  for sc, x in i:
    F = x
    H = [ 
      F[0],G[1],F[2],G[3],F[4],G[5],F[6],G[7],  
      F[8],G[9],F[10],G[11],F[12],G[13],F[14],G[15], 
      F[16],G[17],F[18],G[19],F[20],G[21],F[22],G[23], 
      F[24],G[25],F[26],G[27],F[28],G[29],F[30],G[31] 
        ]
#  now invert parity
    for i in [12,13,14,15,28,29,30,31]:
      H[i] = 0xFF ^ H[i]
    yield sc, H
    G = F
# ===============================================================================
def C1():
  global C1_OK, C1_Err
  c = RSCoder(32,28,2)
  for sc, x in DelayInv():
    z, ok, _ = c.process(x)
    if ok: C1_OK += 1
    else:  C1_Err += 1
    yield sc, z[0:28]
#=============================================================================
def Delay():
  i = C1()
  d = []
  alignQ = Queue()
  for j in range(109): # re-align absolute times of subcode & sector
    sc, y = i.next()
    alignQ.put(sc)
  for j in range(109):
    sc, y = i.next()
    alignQ.put(sc)
    d.append(y)
  e = []
  for sc, x in i:
    alignQ.put(sc)
    for j in range(0,28):
      e.append(d[4*j][j])
    yield alignQ.get(), e
    e = []
    del d[0]
    d.append(x)
#=============================================================================
def C2():
  global C2_Err, C2_OK
  c = RSCoder(28,24,2)
  for sc, x in Delay():
    z, ok, _ = c.process(x)
    if ok: C2_OK += 1
    else:  C2_Err += 1
    yield sc, z[0:28]
#==============================================================================
def DeInt():
  i = C2()
  sch, H = i.next()
  scg, G = i.next()
  for scf, F in i:
    e = [
        F[0],F[1],F[6],F[7],H[16],H[17],H[22],H[23],
        F[2],F[3],F[8],F[9],H[18],H[19],H[24],H[25],
        F[4],F[5],F[10],F[11],H[20],H[21],H[26],H[27]
        ]
    H, G = G, F
    sch, scg = scg, scf
    yield scf, e

#=================================================================================
def GetSamples():
  for sc, e in DeInt():
    f = [ e[i+j] for i in (0,4,8,12,16,20) for j in (1,0,3,2)]
    yield sc, f
# =======================================================================
parser = ap.ArgumentParser(description='This converts a frames file from audio discs to a wav file',add_help=True,version='0.5')
parser.add_argument('--src',action='store',default='../data',help='Source file directory')
parser.add_argument('--dst',action='store',default='../data',help='Destination file directory')
parser.add_argument('--title',action='store',default='test',help='Volume name')
parser.add_argument('--ps',action='store',default='1',help='Volume version')
#
parser.add_argument('--skip',action='store',type=int, default=0, help='Skip first N frames')
parser.add_argument('--count',action='store',type=int, default=-1,help='Process N frames (default: all)')
args = parser.parse_args()
#
inputFile = open('%s/%s%s.frames'    % (args.src,args.title,args.ps),'r')
outputFile = wave.open('%s/%s%s.wav'      % (args.dst,args.title,args.ps),'wb')
summaryFile = open('%s/%s%s.summary' % (args.dst,args.title,args.ps),'w')
#
t1 = time.time()
saved_C2 = 0
outputFile.setnchannels(2)
outputFile.setsampwidth(2)
outputFile.setframerate(44100)
outputFile.setnframes(60*44000)
framecount = 0
secs_count = 0
try:
  for subcodes,f in GetSamples():
    outputFile.writeframes(bytearray(f))
    framecount += 1
    if framecount >= 96*75: # 1 secs worth
      framecount = 0
      secs_count += 1
      print('%s secs processed' % secs_count)
finally:
  outputFile.close()
  t2 = time.time()
  d = t2-t1
  s = \
'''
Total Bits     = %6i
Chan Errors    = %6i
Total Frames   = %6i
C1 Errors      = %6i
C1 OK          = %6i
C2 Errors      = %6i
C2 OK          = %6i
Time taken      = %10s
'''  % (BitCount,ChanErr,FrameCount,C1_Err,C1_OK,C2_Err,C2_OK,d)
  print(s)
  summaryFile.write(s)
  summaryFile.close()



