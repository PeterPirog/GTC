"""
The proper way to create an uncertain array is by calling uarray(...)

This module was written so that numpy >= 1.13.0
does not have to be installed in order for someone to use GTC.
"""
from __future__ import division

import warnings

from numbers import Number, Real, Complex
from math import isnan, isinf
from cmath import isnan as cisnan
from cmath import isinf as cisinf
try:
    from itertools import izip  # Python 2
except ImportError:
    izip = zip
    xrange = range

from GTC import is_sequence 

from GTC.core import (
    value,
    uncertainty,
    variance,
    dof,
    cos,
    sin,
    tan,
    acos,
    asin,
    atan,
    atan2,
    exp,
    log,
    log10,
    sqrt,
    sinh,
    cosh,
    tanh,
    acosh,
    asinh,
    atanh,
    mag_squared,
    magnitude,
    phase,
    result,
)

from GTC.lib import (
    UncertainReal,
    UncertainComplex
)

try:
    import numpy as np
except ImportError:
    UncertainArray = None
else:
    if np.__version__ < '1.13.0':
        # The __array_ufunc__ method was not introduced until v1.13.0
        UncertainArray = None
    else:
        def _isnan(number):
            val = value(number)
            if isinstance(val, Real):
                return isnan(val)
            elif isinstance(val, Complex):
                return cisnan(val)
            else:
                raise TypeError('cannot calculate isnan of type {}'.format(type(number)))

        def _isinf(number):
            val = value(number)
            if isinstance(val, Real):
                return isinf(val)
            elif isinstance(val, Complex):
                return cisinf(val)
            else:
                raise TypeError('cannot calculate isinf of type {}'.format(type(number)))

        # Note numpy defines its own numeric types, instead of bool, int,
        # float, complex, that have additional attributes. These are assumed by  
        # functions like `numpy.average`. (Uses `dtype` and `.size` attributes 
        # on the result returned by `mean`, as defined in a subclass if available.) 

        # One way to fix this is to add the required attributes 
        # to all the return values from `UncertainArray` methods.
        
        # Another option is to ensure that array elements of 
        # are always numpy-compatible. We need all uncertain 
        # number objects to be initialised with  
        #           a.dtype = np.dtype('O')
        #           a.size = 1
        #           a.shape = ()
        # 
        # However, our use of dtype==object for the arrays means that numeric  
        # elements are not cast to numpy types when they are loaded into an array. 
        # To fix this would require iteration through all arrays as they 
        # are being created!        

        #--------------------------------------------------------------------
        class UncertainArray(np.ndarray):
            """Base: :class:`numpy.ndarray`

            An :class:`UncertainArray` can contain elements that are of type
            :class:`int`, :class:`float`, :class:`complex`,
            :class:`.UncertainReal` or :class:`.UncertainComplex`.

            Do not instantiate this class directly. Use :func:`~.uarray` instead.

            """
            def __new__(cls, array, dtype=None, label=None):
                # The first case allows users to create uarray instances 
                # with a definite numpy number type. This could be done 
                # by wrapping a call to uarray() around an ndarray.
                # Without this, the type gets converted back to Python.
                if type(array) == np.ndarray: 
                    dtype = array.dtype
                elif dtype is None: 
                    dtype = np.dtype('O')
                    
                obj = np.asarray(array, dtype=dtype).view(cls)
                obj._label = label
                return obj

            def __array_finalize__(self, obj):
                if obj is None: return
                self._label = getattr(obj, 'label', None)
                
                # numpy looks at type().__name__ when preparing
                # a string representation of the object. This 
                # change means we see `uarray` not `UncertainArray`.
                self.__class__.__name__ = 'uarray'

                self._broadcasted_shape = None

            def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
                try:
                    attr = getattr(self, '_' + ufunc.__name__)
                except AttributeError:
                    # Want to raise a NotImplementedError without nested exceptions
                    # In Python 3 this could be achieved by "raise Exception('...') from None"
                    attr = None

                if attr is None:
                    raise NotImplementedError(
                        'The {} function has not been implemented'.format(ufunc)
                    )

                if kwargs:
                    warnings.warn('**kwargs, {}, are currently not supported'
                                  .format(kwargs), stacklevel=2)

                case = len(inputs)
                if case == 1:
                    pass  # Must be an UncertainArray
                elif case == 2:
                    # At least 1 of the inputs must be an UncertainArray
                    # If an input is not an ndarray then convert it to be an ndarray
                    not0 = not isinstance(inputs[0], np.ndarray)
                    if not0 or not isinstance(inputs[1], np.ndarray):
                        # A tuple cannot be modified
                        # This does not create a copy of the items
                        inputs = list(inputs)
                        # convert the input that is not an ndarray
                        convert, keep = (0, 1) if not0 else (1, 0)
                        if isinstance(inputs[convert], (Number, UncertainReal, UncertainComplex)):
                            inputs[convert] = np.full(inputs[keep].shape, inputs[convert], dtype=object)
                        else:
                            inputs[convert] = np.asarray(inputs[convert], dtype=object)

                    self._broadcasted_shape = None
                    if inputs[0].shape != inputs[1].shape:
                        broadcasted = np.broadcast(*inputs)
                        inputs = broadcasted.iters
                        self._broadcasted_shape = broadcasted.shape

                else:
                    assert False, 'Should not occur: __array_ufunc__ received {} inputs'.format(case)

                return attr(*inputs)

            def __repr__(self):
                # Use the numpy formatting but hide the default dtype
                np_array_repr = np.array_repr(self)
                
                if self.dtype == np.object:
                    # Truncate string from trailing ',' 
                    i = np_array_repr.rfind(',')  
                    return np_array_repr[:i] + ')'                    
                else:
                    return np_array_repr

            def __matmul__(self, other):
                # Implements the protocol used by the '@' operator defined in PEP 465.
                # import here to avoid circular imports
                from GTC.linear_algebra import matmul
                return matmul(self, other)

            def __rmatmul__(self, other):
                # Implements the protocol used by the '@' operator defined in PEP 465.
                # import here to avoid circular imports
                from GTC.linear_algebra import matmul
                return matmul(other, self)

            def _create_empty(self, inputs=None, dtype=None, order='C'):
                if dtype is None:
                    dtype = object
                shape = self.shape if self._broadcasted_shape is None else self._broadcasted_shape
                a = np.empty(shape, dtype=dtype, order=order)
                if inputs is None:
                    return a, a.itemset, self.flat
                if len(inputs) == 1:
                    return a, a.itemset, inputs[0].flat
                if isinstance(inputs[0], np.ndarray):
                    return a, a.itemset, izip(inputs[0].flat, inputs[1].flat)
                # then the inputs are already broadcasted iterators
                return a, a.itemset, izip(*inputs)

            @property
            def label(self):
                """The label that was assigned to the array when it was created.

                **Example**::

                    >>> current = la.uarray([ureal(0.57, 0.18), ureal(0.45, 0.12), ureal(0.68, 0.19)], label='amps')
                    >>> current.label
                    'amps'

                :rtype: :class:`str`
                """
                return self._label
            
            @property
            def real(self):
                """The result of applying the attribute ``real`` to each
                element in the array.

                **Example**::

                    >>> a = la.uarray([ucomplex(1.2-0.5j, 0.6), ucomplex(3.2+1.2j, (1.4, 0.2)), ucomplex(1.5j, 0.9)])
                    >>> a.real
                    uarray([ureal(1.2,0.6,inf), ureal(3.2,1.4,inf),
                            ureal(0.0,0.9,inf)])

                :rtype: :class:`UncertainArray`
                """
                if self.shape == ():
                    return self.item(0).real
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, item.real)
                return UncertainArray(arr)

            @property
            def imag(self):
                """The result of applying the attribute ``imag`` to each
                element in the array.

                **Example**::

                    >>> a = la.uarray([ucomplex(1.2-0.5j, 0.6), ucomplex(3.2+1.2j, (1.4, 0.2)), ucomplex(1.5j, 0.9)])
                    >>> a.imag
                    uarray([ureal(-0.5,0.6,inf), ureal(1.2,0.2,inf),
                            ureal(1.5,0.9,inf)])

                :rtype: :class:`UncertainArray`
                """
                if self.shape == ():
                    return self.item(0).imag
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, item.imag)
                return UncertainArray(arr)

            @property
            def r(self):
                """The result of applying the attribute ``r`` to  each element in the array.

                **Example**::

                    >>> a = la.uarray([ucomplex(1.2-0.5j, (1.2, 0.7, 0.7, 2.2)),
                    ...                ucomplex(-0.2+1.2j, (0.9, 0.4, 0.4, 1.5))])
                    >>> a.r
                    uarray([0.26515152, 0.2962963 ])

                :rtype: :class:`UncertainArray`
                """
                if self.shape == ():
                    return self.item(0).r
                    
                arr, itemset, iterator = self._create_empty(dtype=float)
                for i, item in enumerate(iterator):
                    itemset(i, item.r)
                return UncertainArray(arr)

            @property
            def x(self):
                """The result of :func:`~.core.value` for each element in the array.

                **Example**::

                    >>> a = la.uarray([0.57, ureal(0.45, 0.12), ucomplex(1.1+0.68j, 0.19)])
                    >>> a.x
                    uarray([0.57, 0.45, (1.1+0.68j)])
                
                :rtype: :class:`UncertainArray`
                
                """
                return self.value()
                
            def value(self, dtype=None):
                """The result of :func:`~.core.value` for each element in the array.

                **Example**::

                    >>> a = la.uarray([0.57, ureal(0.45, 0.12), ucomplex(1.1+0.68j, 0.19)])
                    >>> a.value()
                    uarray([0.57, 0.45, (1.1+0.68j)])
                    >>> a.value(complex)
                    uarray([0.57+0.j  , 0.45+0.j  , 1.1 +0.68j])

                :param dtype: The data type of the returned array.
                :type dtype: :class:`numpy.dtype`
                :rtype: :class:`numpy.ndarray`
                """
                if self.shape == ():
                    return value(self.item(0)) 
                    
                arr, itemset, iterator = self._create_empty(dtype=dtype)
                for i, item in enumerate(iterator):
                    itemset(i, value(item) )
                return UncertainArray(arr)

            @property
            def u(self):
                """The result of :func:`~.core.uncertainty` for each element in the array.

                **Example**::

                    >>> r = la.uarray([ureal(0.57, 0.18), ureal(0.45, 0.12), ureal(0.68, 0.19)])
                    >>> r.u
                    uarray([0.18, 0.12, 0.19])
                    >>> c = la.uarray([ucomplex(1.2-0.5j, 0.6), ucomplex(3.2+1.2j, (1.4, 0.2)), ucomplex(1.5j, 0.9)])
                    >>> c.u
                    uarray([StandardUncertainty(real=0.6, imag=0.6),
                           StandardUncertainty(real=1.4, imag=0.2),
                           StandardUncertainty(real=0.9, imag=0.9)])

                :rtype: :class:`UncertainArray`
                """
                return self.uncertainty()
                
            def uncertainty(self, dtype=None):
                """The result of :func:`~.core.uncertainty` for each element in the array.

                **Example**::

                    >>> r = la.uarray([ureal(0.57, 0.18), ureal(0.45, 0.12), ureal(0.68, 0.19)])
                    >>> r.uncertainty(float)
                    uarray([0.18, 0.12, 0.19])
                    >>> c = la.uarray([ucomplex(1.2-0.5j, 0.6), ucomplex(3.2+1.2j, (1.4, 0.2)), ucomplex(1.5j, 0.9)])
                    >>> c.uncertainty()
                    uarray([StandardUncertainty(real=0.6, imag=0.6),
                           StandardUncertainty(real=1.4, imag=0.2),
                           StandardUncertainty(real=0.9, imag=0.9)])

                :param dtype: The data type of the returned array.
                :type dtype: :class:`numpy.dtype`
                :rtype: :class:`numpy.ndarray`
                """
                if self.shape == ():
                    return uncertainty(self.item(0))
                    
                arr, itemset, iterator = self._create_empty(dtype=dtype)
                for i, item in enumerate(iterator):
                    itemset(i, uncertainty(item))
                return UncertainArray(arr)

            @property
            def v(self):
                """The result of :func:`~.core.variance` for each element in the array.

                **Example**::

                    >>> r = la.uarray([ureal(0.57, 0.18), ureal(0.45, 0.12), ureal(0.68, 0.19)])
                    >>> r.v
                    uarray([0.0324, 0.0144, 0.0361])
                    >>> c = la.uarray([ucomplex(1.2-0.5j, 0.6), ucomplex(3.2+1.2j, (1.5, 0.5)), ucomplex(1.5j, 0.9)])
                    >>> c.v
                    uarray([VarianceCovariance(rr=0.36, ri=0.0, ir=0.0, ii=0.36),
                            VarianceCovariance(rr=2.25, ri=0.0, ir=0.0, ii=0.25),
                            VarianceCovariance(rr=0.81, ri=0.0, ir=0.0, ii=0.81)])

                :rtype: :class:`UncertainArray`
                """
                return self.variance()
                
            def variance(self, dtype=None):
                """The result of :func:`~.core.variance` for each element in the array.

                **Example**::

                    >>> r = la.uarray([ureal(0.57, 0.18), ureal(0.45, 0.12), ureal(0.68, 0.19)])
                    >>> r.variance(float)
                    uarray([0.0324, 0.0144, 0.0361])
                    >>> c = la.uarray([ucomplex(1.2-0.5j, 0.6), ucomplex(3.2+1.2j, (1.5, 0.5)), ucomplex(1.5j, 0.9)])
                    >>> c.variance()
                    uarray([VarianceCovariance(rr=0.36, ri=0.0, ir=0.0, ii=0.36),
                            VarianceCovariance(rr=2.25, ri=0.0, ir=0.0, ii=0.25),
                            VarianceCovariance(rr=0.81, ri=0.0, ir=0.0, ii=0.81)])

                :param dtype: The data type of the returned array.
                :type dtype: :class:`numpy.dtype`
                :rtype: :class:`numpy.ndarray`
                """
                if self.shape == ():
                    return variance(self.item(0))
                    
                arr, itemset, iterator = self._create_empty(dtype=dtype)
                for i, item in enumerate(iterator):
                    itemset(i, variance(item))
                return UncertainArray(arr)

            @property
            def df(self):
                """The result of :func:`~.core.dof` for each element in the array.

                **Example**::

                    >>> a = la.uarray([ureal(6, 2, df=3), ureal(4, 1, df=4), ureal(5, 3, df=7), ureal(1, 1)])
                    >>> a.df
                    uarray([3.0, 4.0, 7.0, inf])

                :rtype: :class:`UncertainArray`
                
                """
                return self.dof()
                
            def dof(self,dtype=None):
                """The result of :func:`~.core.dof` for each element in the array.

                **Example**::

                    >>> a = la.uarray([ureal(6, 2, df=3), ureal(4, 1, df=4), ureal(5, 3, df=7), ureal(1, 1)])
                    >>> a.dof()
                    uarray([3.0, 4.0, 7.0, inf])

                :rtype: :class:`numpy.ndarray`
                """
                if self.shape == ():
                    return dof(self.item(0))
                    
                arr, itemset, iterator = self._create_empty(dtype=dtype)
                for i, item in enumerate(iterator):
                    itemset(i, dof(item))
                return UncertainArray(arr)

            def sensitivity(self, x):
                """The result of :func:`~.reporting.sensitivity` for each element in the array.
                
                """
                if self.shape == ():
                    if hasattr(x,'item'):
                        return self.item(0).sensitivity(x.item(0))
                    else:
                        return self.item(0).sensitivity(x)
                    
                # `_create_empty()` handles only ndarray-like sequences
                if not isinstance(x,np.ndarray):
                    x = np.asarray(x)
                    
                arr, itemset, iterator = self._create_empty((self, x))
                for i, (y, x) in enumerate(iterator):
                    itemset(i, y.sensitivity(x)) 
                return UncertainArray(arr)

            def u_component(self, x):
                """The result of :func:`~.reporting.u_component` for each element in the array.
                
                """
                if self.shape == ():
                    if hasattr(x,'item'):
                        return self.item(0).u_component(x.item(0))
                    else:
                        return self.item(0).u_component(x)
                    
                # `_create_empty()` handles only ndarray-like sequences
                if not isinstance(x,np.ndarray):
                    x = np.asarray(x)
                    
                arr, itemset, iterator = self._create_empty((self, x))
                for i, (y, x) in enumerate(iterator):
                    itemset(i, y.u_component(x)) 
                return UncertainArray(arr)
                
            def conjugate(self):
                """The result of applying the attribute ``conjugate`` to each element in the array.

                **Example**::

                    >>> a = la.uarray([ucomplex(1.2-0.5j, 0.6), ucomplex(3.2+1.2j, (1.4, 0.2)), ucomplex(1.5j, 0.9)])
                    >>> a.conjugate()
                    uarray([ucomplex((1.2+0.5j), u=[0.6,0.6], r=0.0, df=inf),
                            ucomplex((3.2-1.2j), u=[1.4,0.2], r=0.0, df=inf),
                            ucomplex((0-1.5j), u=[0.9,0.9], r=0.0, df=inf)])

                :rtype: :class:`UncertainArray`
                """
                # override this method because I wanted to create a custom __doc__
                return self._conjugate()

            def _conjugate(self, *ignore):
                if self.shape == ():
                    return self.item(0).conjugate()

                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, item.conjugate()) 
                return UncertainArray(arr)

            def _positive(self, *ignore):
                if self.shape == ():
                    return +self.item(0)

                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, +item) 
                return UncertainArray(arr)

            def _negative(self, *ignore):
                if self.shape == ():
                    return -self.item(0)
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, -item)
                return UncertainArray(arr)

            def _add(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) + inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a + b )
                return UncertainArray(arr)

            def _subtract(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) - inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a - b)
                return UncertainArray(arr)

            def _multiply(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) * inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a * b)
                return UncertainArray(arr)

            def _divide(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) / inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a / b)
                return UncertainArray(arr)

            def _true_divide(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) / inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a / b)
                return UncertainArray(arr)

            def _power(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) ** inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a ** b) 
                return UncertainArray(arr)

            def _exp(self, *ignore):
                if self.shape == ():
                    return exp( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, exp(item))
                return UncertainArray(arr)

            def _log(self, *ignore):
                if self.shape == ():
                    return log( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, log(item))
                return UncertainArray(arr)

            def _log10(self, *ignore):
                if self.shape == ():
                    return log10( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, log10(item))
                return UncertainArray(arr)

            def _sqrt(self, *ignore):
                if self.shape == ():
                    return sqrt( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, sqrt(item))
                return UncertainArray(arr)

            def _cos(self, *ignore):
                if self.shape == ():
                    return cos( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, cos(item))
                return UncertainArray(arr)

            def _sin(self, *ignore):
                if self.shape == ():
                    return sin( self.item(0)) 
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, sin(item))
                return UncertainArray(arr)

            def _tan(self, *ignore):
                if self.shape == ():
                    return tan( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, tan(item)) 
                return UncertainArray(arr)

            def _arccos(self, *ignore):
                return self._acos()

            def _acos(self):
                if self.shape == ():
                    return acos( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, acos(item))
                return UncertainArray(arr)

            def _arcsin(self, *ignore):
                return self._asin()

            def _asin(self):
                if self.shape == ():
                    return asin( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, asin(item))
                return UncertainArray(arr)

            def _arctan(self, *ignore):
                return self._atan()

            def _atan(self):
                if self.shape == ():
                    return atan( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, atan(item))
                return UncertainArray(arr)

            def _arctan2(self, *inputs):
                return self._atan2(inputs[1])
                
            def _atan2(self, *inputs):
                if self.ndim ==0:
                    return atan2(self.item(0),inputs[0].item(0))
                    
                arr, itemset, iterator = self._create_empty((self, inputs[0]))
                for i, (a, b) in enumerate(iterator):
                    itemset(i, atan2(a, b))
                return UncertainArray(arr)
               
            def _sinh(self, *ignore):
                if self.shape == ():
                    return sinh( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, sinh(item))
                return UncertainArray(arr)

            def _cosh(self, *ignore):
                if self.shape == ():
                    return cosh( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, cosh(item))
                return UncertainArray(arr)

            def _tanh(self, *ignore):
                if self.shape == ():
                    return tanh( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, tanh(item))
                return UncertainArray(arr)

            def _arccosh(self, *ignore):
                return self._acosh()

            def _acosh(self):
                if self.shape == ():
                    return acosh( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, acosh(item))
                return UncertainArray(arr)

            def _arcsinh(self, *ignore):
                return self._asinh()

            def _asinh(self):
                if self.shape == ():
                    return asinh( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, asinh(item))
                return UncertainArray(arr)

            def _arctanh(self, *ignore):
                return self._atanh()

            def _atanh(self):
                if self.shape == ():
                    return atanh( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, atanh(item))
                return UncertainArray(arr)

            def _square(self, *ignore):
                return self._mag_squared()

            def _mag_squared(self):
                if self.shape == ():
                    return mag_squared( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, mag_squared(item))
                return UncertainArray(arr)

            def _magnitude(self):
                if self.shape == ():
                    return magnitude( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, magnitude(item))
                return UncertainArray(arr)

            def _phase(self):
                if self.shape == ():
                    return phase( self.item(0) )
            
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    itemset(i, phase(item))
                return UncertainArray(arr)

            def _intermediate(self,labels):
                # Default second argument of calling function is `None`
                if labels is None: 
                    if self.shape == ():
                        return result( self.item(0) )
            
                    arr, itemset, iterator = self._create_empty()
                    for i, x in enumerate(iterator):
                        itemset( i, result(x)) 
                else:
                    # `_create_empty()` handles only ndarray-like sequences
                    if self.size>1 and not is_sequence(labels):
                        # Add index notation to the label base 
                        labels = [
                            "{}[{}]".format(labels,i) 
                                for i in range(self.size)
                        ]
                        labels = np.asarray(labels)
                    else:   
                        labels = np.asarray(labels)
                                            
                    if self.shape == ():
                        return result( self.item(0), labels.item(0) )
            
                    arr, itemset, iterator = self._create_empty((self, labels))
                    for i, (x, lbl) in enumerate(iterator):
                        itemset(i, result(x,lbl))
                    
                return UncertainArray(arr)

            def _equal(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) == inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a == b)
                return arr

            def _not_equal(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) != inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a != b)
                return arr

            def _less(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) < inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a < b)
                return arr

            def _less_equal(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) <= inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a <= b)
                return arr

            def _greater(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) > inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a > b)
                return arr

            def _greater_equal(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) >= inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a >= b)
                return arr

            def _maximum(self, *inputs):
                if self.ndim ==0:
                    a = inputs[0].item(0)
                    b = inputs[1].item(0) 
                    return a if a > b else b
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, (a, b) in enumerate(iterator):
                    if _isnan(a):
                        itemset(i, a)
                    elif _isnan(b):
                        itemset(i, b)
                    elif a > b:
                        itemset(i, a)
                    else:
                        itemset(i, b)
                return UncertainArray(arr)

            def _minimum(self, *inputs):
                if self.ndim ==0:
                    a = inputs[0].item(0)
                    b = inputs[1].item(0) 
                    return a if a < b else b
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, (a, b) in enumerate(iterator):
                    if _isnan(a):
                        itemset(i, a)
                    elif _isnan(b):
                        itemset(i, b)
                    elif a < b:
                        itemset(i, a)
                    else:
                        itemset(i, b)
                return UncertainArray(arr)

            def _logical_and(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) and inputs[1].item(0)
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=object)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a and b )
                return UncertainArray(arr)

            def _logical_or(self, *inputs):
                if self.ndim ==0:
                    return inputs[0].item(0) or inputs[1].item(0) 
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=object)
                for i, (a, b) in enumerate(iterator):
                    itemset(i, a or b )
                return UncertainArray(arr)

            def _logical_xor(self, *inputs):
                raise TypeError(
                    "Boolean bitwise operations are not defined for `UncertainArray`"
                )
                # arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                # for i, (a, b) in enumerate(iterator):
                    # itemset(i, bool(a) ^ bool(b))
                # return arr

            def _logical_not(self, *inputs):
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, item in enumerate(iterator):
                    itemset(i, not bool(item))
                return arr

            def _isinf(self, *inputs):
                if self.ndim ==0:
                    return _isinf(self.item(0))
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, item in enumerate(iterator):
                    itemset(i, _isinf(item))
                return arr

            def _isnan(self, *inputs):
                if self.ndim ==0:
                    return _isnan( self.item(0) )
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, item in enumerate(iterator):
                    itemset(i, _isnan(item))
                return arr

            def _isfinite(self, *inputs):
                # TODO: is this correct? It doesn't match the array case below.
                if self.ndim ==0:
                    return _isinf( self.item(0) )
                    
                arr, itemset, iterator = self._create_empty(inputs, dtype=bool)
                for i, item in enumerate(iterator):
                    itemset(i, not (_isnan(item) or _isinf(item)))
                return arr

            def _reciprocal(self, *inputs):
                if self.ndim ==0:
                    return 1.0 / ( self.item(0) )
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, item in enumerate(iterator):
                    itemset(i, 1.0/item)
                return UncertainArray(arr)

            def _absolute(self, *inputs):
                if self.ndim ==0:
                    return abs( self.item(0) )
                    
                arr, itemset, iterator = self._create_empty(inputs)
                for i, item in enumerate(iterator):
                    itemset(i, abs(item))
                return UncertainArray(arr)

            def copy(self, order='C'):
                arr, itemset, iterator = self._create_empty(order=order)
                for i, item in enumerate(iterator):
                    itemset(i, +item)
                return UncertainArray(arr, label=self.label)

            def round(self, decimals=0, **kwargs):
                digits = kwargs.get('digits', decimals)
                df_decimals = kwargs.get('df_decimals', digits)
                arr, itemset, iterator = self._create_empty()
                for i, item in enumerate(iterator):
                    try:
                        itemset(i, item._round(digits, df_decimals))
                    except AttributeError:
                        itemset(i, round(item, digits))
                return UncertainArray(arr)

            def sum(self, *args, **kwargs):
                result = np.asarray(self).sum(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result

            def mean(self, *args, **kwargs):
                result = np.asarray(self).mean(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result
            
            def std(self, *args, **kwargs):
                raise TypeError(
                    "`std` is not defined for `UncertainArray`"
                )
                # return UncertainArray(np.asarray(self).std(*args, **kwargs))

            def var(self, *args, **kwargs):
                raise TypeError(
                    "`var` is not defined for `UncertainArray`"
                )
                # return UncertainArray(np.asarray(self).var(*args, **kwargs))

            def max(self, *args, **kwargs):
                result = np.asarray(self).max(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result

            def min(self, *args, **kwargs):
                result = np.asarray(self).min(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result

            def trace(self, *args, **kwargs):
                result = np.asarray(self).trace(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result

            def cumprod(self, *args, **kwargs):
                result = np.asarray(self).cumprod(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result

            def cumsum(self, *args, **kwargs):
                result = np.asarray(self).cumsum(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result

            def prod(self, *args, **kwargs):
                result = np.asarray(self).prod(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result

            def ptp(self, *args, **kwargs):
                result = np.asarray(self).ptp(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result

            def any(self, *args, **kwargs):
                result = np.asarray(self, dtype=bool).any(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result

            def all(self, *args, **kwargs):
                result = np.asarray(self, dtype=bool).all(*args, **kwargs)
                if hasattr(result,'shape') and result.shape != ():
                    return UncertainArray(result)
                else: 
                    return result
                
        # Allows pickle to understand the class name 'uarray'         
        uarray = UncertainArray
