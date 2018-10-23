########################################################################
# fast.py takes a file of raw samples produced by a picoscope
# and outputs raw frames
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

import argparse as ap
import numpy as np
import os,sys, re, time
import mmap
import contextlib


# Streaming from the picoscope binary file of 16bit samples.
# Captures were made at 32ns sampling period.
# The main decoding issue is rotation speed variation, so we look for frame synchronization patterns
# which should be  588 bits apart, and calculate the actual bit rate from there.
# This process seems fairly robust.
# The pit/land lengths are output as hex digits in a text file so that one can get
# a quick appreciation of the quality of the decoding: ideally every line 
# (representing a frame) should start with 'aa' - 'one -ten zeroes - one - ten zeroes' !


sampleInterval = 32 # nanoseconds
bitLength = 231.3   # nanoseconds
bpf, spb = 588.0, bitLength/sampleInterval   # bits per frame, nominal samples per bit

#=================================================================
def emit(filename):
  f = open(filename,'rb')
  filesize = os.path.getsize(filename)
  with contextlib.closing(mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) ) as m:
    sync0, sync1 = yield ''
    while sync1 < filesize:
      bitrate = (sync1-sync0)/588.0
      a1 = np.frombuffer(m,np.int16,sync1-sync0,2*sync0)
      a2 = np.take(a1, [int((i+0.5)*bitrate) for i in range(588)] )
      a3 = np.where(a2 > 0,1,0).astype(np.uint8)
      trans = np.array( ( (a3[:-1] == 0) & (a3[1:] == 1) |
                          (a3[:-1] == 1) & (a3[1:] == 0)  )  )
      t = np.where(trans)[0]
      t = np.insert(t,[0,len(t)],[-1,589])
      lengths = (t[1:] - t[:-1])
      l = ['%1x' % (i-1) for i in lengths.tolist()]
      sync0, sync1 = yield "".join(l)
 
#=================================================================
def synchronize(filename):
  currentPos = 0
  record = int(bpf*spb*1.5)
  f = open(filename,'rb')
  filesize = os.path.getsize(filename)
  #
  sync_string = int(11*spb+0.5)*'1 '+int(11*spb)*'-1 '+int(spb)*'1 '
  sync_pattern = np.fromstring(sync_string,sep=' ')
  low, high = int((bpf-10)*spb), int((bpf+10+ 25)*spb)
  lowest, highest = int(22*spb), record
  threshold = 20*spb
  #
  with contextlib.closing(mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) ) as m:
    inSync = False
    poorSync = 6
    wait = True
    while 2*(currentPos + record) < filesize:  
      array = np.frombuffer(m,np.int16,record,2*currentPos)
      DCoffset, level = np.average(array), np.average(abs(array)) 
      clip = np.where(array > level/5,1,0) + np.where(array < -level/5,-1,0)
      if inSync:
        expectedSync = clip[low : high]
        f3 = abs(np.correlate(expectedSync,sync_pattern))
        mx = np.argmax(f3)
        nextSync = low+mx
        if   f3[mx] >  threshold: poorSync = 0
        else: poorSync += 1
        if poorSync > 5:
          inSync = False
          wait = False
          print('Lost sync')
      if not inSync:
        expectedSync = clip[lowest : highest]
        f3 = abs(np.correlate(expectedSync,sync_pattern))
        mx = np.argmax(f3)
        nextSync = lowest+mx
        if f3[mx] > threshold:
          inSync = True;
          wait = True
          poorSync = 0
          print('Got sync')
        else:  nextSync = record 
      #
      if inSync:
        if not wait:  yield currentPos,currentPos+nextSync
        else:  wait = False
      currentPos += nextSync
# =======================================================================
parser = ap.ArgumentParser(description='This converts a picoscope samples file to frames',add_help=True,version='0.5')
parser.add_argument('--src',action='store',default='../data',help='Source file directory')
parser.add_argument('--dst',action='store',default='../data',help='Destination file directory')
parser.add_argument('--title',action='store',default='test',help='Volume name')
parser.add_argument('--ps',action='store',default='1',help='Volume version')

args = parser.parse_args()
#
fileid = args.title+args.ps
filename = '%s/%s.samples' % (args.src,fileid)
print('Processing %s' % filename)
g = open('%s/%s.frames' % (args.dst,fileid),'w')

startTime = time.time(); print('Start at %s' % startTime)
now = startTime
perfCount = 0
secs = 0
e = emit(filename)
s = e.send(None)
for sync0,sync1 in synchronize(filename): 
  s = e.send( (sync0, sync1) )
  g.write('%s\n' % s )
  perfCount += 1
  if perfCount > 98*75: # 1 sec worth of frames
    secs += 1
    perfCount = 0
    print('%5d secs processed. Previous in %6.3f secs' % (secs,time.time()-now))
    now = time.time()

g.close()

