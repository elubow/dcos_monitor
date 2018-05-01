"""utilities library
"""

def lpad(str, int = 4):
    print("{}{}".format(" "*int, str))

def dget(item, ks, default):
    if len(ks) == 1:
        if ks[0] in item:
            return item[ks[0]]
        else:
            return default
    else:
        if ks[0] in item and item[ks[0]] is not None:
            return dget(item[ks[0]],ks[1:],default)
        else:
            return default

def print_separator(length = 80, k = '=', spaces = 0):
    print(" " * spaces + k * length)
