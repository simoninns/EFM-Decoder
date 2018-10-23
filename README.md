# EFM-Decoder
A LaserDisc EFM decoder application

## Synopsis

The EFM-Decoder application is an EFM decoder for LaserDisc EFM images processed captured using a PicoScope connected to the EFM output of a Pioneer LD-V4300D LaserDisc player.  It is designed to capture EFM from Acorn AIV Domesday LaserDiscs and convert them back into Acorn VFS/ADFS images suitable for use with emulators.

## Processing EFM files

fast.py processes the .samples file produced by a picoscope. It outputs a text file where each line corresponds to an F3-frame from the disc. Each character in the line is a hex digit representing the number of zeros encoded by pits and lands. The output file could, of course, be half the size if output were binary: but one can easily visualize how good the sampling might be by - for example - opening in 'less', highlighting 'aa', and seeing how much of the two left hand columns light up. 'aa' represents the start of the F3 synchronization pattern '100000000001000000000010' and shouldn't occur elsewhere. Ideally there shouldn't be any 0,1,b,c,d,e,f hex digits (though there will be a few). This processing is fairly slow, but it shouldn't need to be run very often. I haven't (yet) got it running under pypy.

bit2sec.py processes the .frame file produced by fast.py. It outputs an 'img' file where each record consists of 8x12 bytes of subcode, followed by 2352 bytes of raw sectors (sync pattern, header, EDC & userdata (which might be 2048 bytes of 'cooked' sector, followed by P- & Q-parity bytes)).  The program is structured as a series of generators which just reverse the coding stages set out in the ECMA cd-rom standard.  It also produces a summary file with some statistics.  It incorporates efmtab.py and efmsimtab.py which map 14 bit codes to 8 bits: the first table giving the correct translation and the second giving closest match. The program also uses the bitstream package (on PyPi, MIT licence) and pycrc and rscd (reed-solomon decoding) packages (both MIT licenced) though I've included the source for these latter two as I really should incorporate more up-to-date versions.

bit2sec.py runs much faster under pypy than cpython. Examining the img file under linux using 'hd -v <img file> | less' is instructive, and searching for '00 ff ff ff ff ff ff' (the sync pattern for raw sectors) allows skipping quickly to interesting bits.

finalize.py processes one or more .img files from bit2sec, to output an '.adl' file. It does Q-parity and P-parity error correction on the userdata, throws away subcodes, headers and leading sectors (including the 'volume table'), and infills missing sectors (for example, where analogue audio occurs). It will also process multiple passes to try to correct transient errors. This also uses the external bitstream, pycrc and rscd packages.

## Author

EFM-Decoder is written by Steve Dome.

## Software License (GPLv3)

    EFM-Decoder is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    EFM-Decoder is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
