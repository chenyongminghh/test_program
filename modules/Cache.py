#!/usr/local/bin/python35
import weakref
from abc import ABC, abstractmethod

class Cache:
    def __init__(self, factory):
        """! Create a cache that will keep track of references to any items collected

             When the object referencing the stored item is garbage collected, the item 
             is closed and then removed

             @param factory   When the get() method is called with parameters not seen 
                              before (not including the 'who'), then a new object is created
                              with those parameters by calling 'factory'.   The factory
                              must return an object to store and function for closing the
                              object that is called prior to removing it.  The closing function
                              will be called with the object as the only parameter.
        """
        self._cache = {}
        self.factory = factory
        
    def key(self, *bares, **kw):
        return str((bares, [(k, kw[k]) for k in sorted(kw.keys())]))

    def get(self, who, *bares, **kw):
        key = self.key(*bares, **kw)
        if key not in self._cache:
            o, closer  = self.factory(*bares, **kw)
            self._cache[key] = [o, {}, closer]
        weakref.finalize(who, self.dec, key, id(who))
        self._cache[key][1][id(who)] = 1
        return self._cache[key][0]

    def delete(self, *bares, **kw):
        key = self.key(*bares, **kw)
        if key in self._cache:
            del self._cache[key]
        
    def dec(self, key, who_id):
        if key in self._cache:
            if who_id in self._cache[key][1]:
                del self._cache[key][1][who_id]
                if not self._cache[key][1]:
                    self._cache[key][2](self._cache[key][0])
                    del self._cache[key]


if __name__ == '__main__':
    def factory(*bares, **keys):
        return {bares[0]:1}, print

    _cache = Cache(factory)        

    class MyObj:
        def __init__(self, key):
            self.expensive_object = _cache.get(self, key)


    o1 = MyObj('hello')
    o2 = MyObj('hello')
    o3 = MyObj('world')



    print('delete o3')
    del o3
    print('delete o1')
    del o1
    print('delete o2')
    del o2


