
def tableGen(l,a):
  n=1
  e = [1]
  f = [None]
  g = [ [0 for col in range(256)] for row in range(256)]
  
  for i in range(1,256):
    n = gfmpy(a,n,l)
    e.append(n)
  
  for i in range(1,256):
    f.append(e.index(i))

  for i in range (0,256):
    for j in range(0,256):
      g[i][j] = gfmpy(i,j,l)

  return e, f, g

def gfmpy(x,y,l):
  r = 0
  for i in range(0,8):
    if (y & 1) == 1: r ^= x
    x, y = x << 1, y >> 1
    if (x > 0xff): x ^= l
  return r


class metaGF(type):
  poly = 285; generator = 2  # x**8 + x**4 + x**3 + x**2 + 1
  # poly = 283; generator = 3 # x**8 + x**4 + x**3 + x + 1

  def __new__(meta, name, bases,classDict):
    classDict['exptable'], classDict['logtable'], classDict['mpytable'] = tableGen(metaGF.poly,metaGF.generator)
    obj = type.__new__(meta, name, bases, classDict)
    return obj


class GF256int(int):
    """Instances of this object are elements of the field GF(2^8)
    Instances are integers in the range 0 to 255
    This field is defined using the irreducable polynomial and generator set in the metaclass
    """
    __metaclass__ = metaGF

    # Maps integers to GF256int instances
    cache = {}

    def __new__(cls, value):
        # Check cache
        # Caching sacrifices a bit of speed for less memory usage. This way,
        # there are only a max of 256 instances of this class at any time.
       
        try:
            return GF256int.cache[value]
        except KeyError:
            if value > 255 or value < 0:
                raise ValueError("Field elements of GF(2^8) are between 0 and 255. Cannot be %s" % value)

            newval = int.__new__(cls, value)
            GF256int.cache[int(value)] = newval
            return newval

    def __add__(a, b):
        "Addition in GF(2^8) is the xor of the two"
        return GF256int(a ^ b)

    __sub__ = __add__

    __radd__ = __add__

    __rsub__ = __add__

    def __neg__(self):
        return self

    def __mul__(a, b):
        return GF256int( GF256int.mpytable[a][b] )
    
    __rmul__ = __mul__

    def __pow__(self, power):
        if isinstance(power, GF256int):
            raise TypeError("Raising a Field element to another Field element is not defined. power must be a regular integer")
        x = GF256int.logtable[self]
        z = (x * power) % 255
        return GF256int(GF256int.exptable[z])

    def inverse(self):
        e = GF256int.logtable[self]
        return GF256int(GF256int.exptable[255 - e])

    def __div__(self, other):
        return self * GF256int(other).inverse()

    def __rdiv__(self, other):
        return self.inverse() * other

    def __repr__(self):
        n = self.__class__.__name__
        return "%s(%r)" % (n, int(self))

