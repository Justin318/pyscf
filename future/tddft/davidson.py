#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#

import sys
import tempfile
from functools import reduce
import numpy
import scipy.linalg
import h5py
from pyscf.lib import logger
from pyscf.lib import numpy_helper
from pyscf.lib import linalg_helper

def dgeev(abop, x0, precond, type=1, tol=1e-14, max_cycle=50, max_space=12,
          lindep=1e-14, max_memory=2000, dot=numpy.dot, callback=None,
          nroots=1, lessio=False, verbose=logger.WARN):
    '''Davidson diagonalization method to solve  A c = e B c.

    Args:
        abop : function([x]) => ([array_like_x], [array_like_x])
            abop applies two matrix vector multiplications and returns tuple (Ax, Bx)
        x0 : 1D array
            Initial guess
        precond : function(dx, e, x0) => array_like_dx
            Preconditioner to generate new trial vector.
            The argument dx is a residual vector ``a*x0-e*x0``; e is the current
            eigenvalue; x0 is the current eigenvector.

    Kwargs:
        tol : float
            Convergence tolerance.
        max_cycle : int
            max number of iterations.
        max_space : int
            space size to hold trial vectors.
        lindep : float
            Linear dependency threshold.  The function is terminated when the
            smallest eigenvalue of the metric of the trial vectors is lower
            than this threshold.
        max_memory : int or float
            Allowed memory in MB.
        dot : function(x, y) => scalar
            Inner product
        callback : function(envs_dict) => None
            callback function takes one dict as the argument which is
            generated by the builtin function :func:`locals`, so that the
            callback function can access all local variables in the current
            envrionment.
        nroots : int
            Number of eigenvalues to be computed.  When nroots > 1, it affects
            the shape of the return value
        lessio : bool
            How to compute a*x0 for current eigenvector x0.  There are two
            ways to compute a*x0.  One is to assemble the existed a*x.  The
            other is to call aop(x0).  The default is the first method which
            needs more IO and less computational cost.  When IO is slow, the
            second method can be considered.

    Returns:
        e : list of floats
            The lowest :attr:`nroots` eigenvalues.
        c : list of 1D arrays
            The lowest :attr:`nroots` eigenvectors.
    '''
    if isinstance(verbose, logger.Logger):
        log = verbose
    else:
        log = logger.Logger(sys.stdout, verbose)

    def qr(xs):
        #q, r = numpy.linalg.qr(numpy.asarray(xs).T)
        #q = [qi/numpy_helper.norm(qi)
        #     for i, qi in enumerate(q.T) if r[i,i] > 1e-7]
        qs = [xs[0]/numpy_helper.norm(xs[0])]
        for i in range(1, len(xs)):
            xi = xs[i].copy()
            for j in range(len(qs)):
                xi -= qs[j] * numpy.dot(qs[j], xi)
            norm = numpy_helper.norm(xi)
            if norm > 1e-7:
                qs.append(xi/norm)
        return qs

    toloose = numpy.sqrt(tol) * 1e-2

    if isinstance(x0, numpy.ndarray) and x0.ndim == 1:
        x0 = [x0]
    max_cycle = min(max_cycle, x0[0].size)
    max_space = max_space + nroots * 2
    # max_space*3 for holding ax, bx and xs, nroots*3 for holding axt, bxt and xt
    _incore = max_memory*1e6/x0[0].nbytes > max_space*3+nroots*3
    heff = numpy.empty((max_space,max_space), dtype=x0[0].dtype)
    seff = numpy.empty((max_space,max_space), dtype=x0[0].dtype)
    fresh_start = True

    for icyc in range(max_cycle):
        if fresh_start:
            if _incore:
                xs = []
                ax = []
                bx = []
            else:
                xs = linalg_helper._Xlist()
                ax = linalg_helper._Xlist()
                bx = linalg_helper._Xlist()
            space = 0
# Orthogonalize xt space because the basis of subspace xs must be orthogonal
# but the eigenvectors x0 are very likely non-orthogonal when A is non-Hermitian.
            xt, x0 = qr(x0), None
            e = numpy.zeros(nroots)
            fresh_start = False
        elif len(xt) > 1:
            xt = qr(xt)
            xt = xt[:40]  # 40 trial vectors at most

        axt, bxt = abop(xt)
        if type > 1:
            axt = abop(bxt)[0]
        for k, xi in enumerate(xt):
            xs.append(xt[k])
            ax.append(axt[k])
            bx.append(bxt[k])
        rnow = len(xt)
        head, space = space, space+rnow

        if type == 1:
            for i in range(space):
                if head <= i < head+rnow:
                    for k in range(i-head+1):
                        heff[head+k,i] = dot(xt[k].conj(), axt[i-head])
                        heff[i,head+k] = heff[head+k,i].conj()
                        seff[head+k,i] = dot(xt[k].conj(), bxt[i-head])
                        seff[i,head+k] = seff[head+k,i].conj()
                else:
                    for k in range(rnow):
                        heff[head+k,i] = dot(xt[k].conj(), ax[i])
                        heff[i,head+k] = heff[head+k,i].conj()
                        seff[head+k,i] = dot(xt[k].conj(), bx[i])
                        seff[i,head+k] = seff[head+k,i].conj()
        else:
            for i in range(space):
                if head <= i < head+rnow:
                    for k in range(i-head+1):
                        heff[head+k,i] = dot(bxt[k].conj(), axt[i-head])
                        heff[i,head+k] = heff[head+k,i].conj()
                        seff[head+k,i] = dot(xt[k].conj(), bxt[i-head])
                        seff[i,head+k] = seff[head+k,i].conj()
                else:
                    for k in range(rnow):
                        heff[head+k,i] = dot(bxt[k].conj(), ax[i])
                        heff[i,head+k] = heff[head+k,i].conj()
                        seff[head+k,i] = dot(xt[k].conj(), bx[i])
                        seff[i,head+k] = seff[head+k,i].conj()

        w, v = scipy.linalg.eigh(heff[:space,:space], seff[:space,:space])
        if space < nroots or e.size != nroots:
            de = w[:nroots]
        else:
            de = w[:nroots] - e
        e = w[:nroots]

        x0 = []
        ax0 = []
        bx0 = []
        if lessio and not _incore:
            for k, ek in enumerate(e):
                x0.append(xs[space-1] * v[space-1,k])
            for i in reversed(range(space-1)):
                xsi = xs[i]
                for k, ek in enumerate(e):
                    x0[k] += v[i,k] * xsi
            ax0, bx0 = abop(x0)
            if type > 1:
                ax0 = abop(bx0)[0]
        else:
            for k, ek in enumerate(e):
                x0 .append(xs[space-1] * v[space-1,k])
                ax0.append(ax[space-1] * v[space-1,k])
                bx0.append(bx[space-1] * v[space-1,k])
            for i in reversed(range(space-1)):
                xsi = xs[i]
                axi = ax[i]
                bxi = bx[i]
                for k, ek in enumerate(e):
                    x0 [k] += v[i,k] * xsi
                    ax0[k] += v[i,k] * axi
                    bx0[k] += v[i,k] * bxi

        ide = numpy.argmax(abs(de))
        if abs(de[ide]) < tol:
            log.debug('converge %d %d  e= %s  max|de|= %4.3g',
                      icyc, space, e, de[ide])
            break

        dx_norm = []
        xt = []
        for k, ek in enumerate(e):
            if type == 1:
                dxtmp = ax0[k] - ek * bx0[k]
            else:
                dxtmp = ax0[k] - ek * x0[k]
            xt.append(dxtmp)
            dx_norm.append(numpy_helper.norm(dxtmp))

        if max(dx_norm) < toloose:
            log.debug('converge %d %d  |r|= %4.3g  e= %s  max|de|= %4.3g',
                      icyc, space, max(dx_norm), e, de[ide])
            break

        # remove subspace linear dependency
        for k, ek in enumerate(e):
            if dx_norm[k] > toloose:
                xt[k] = precond(xt[k], e[0], x0[k])
                xt[k] *= 1/numpy_helper.norm(xt[k])
            else:
                xt[k] = None
        xt = [xi for xi in xt if xi is not None]
        for i in range(space):
            for xi in xt:
                xsi = xs[i]
                xi -= xsi * numpy.dot(xi, xsi)
        norm_min = 1
        for i,xi in enumerate(xt):
            norm = numpy_helper.norm(xi)
            if norm > toloose:
                xt[i] *= 1/norm
                norm_min = min(norm_min, norm)
            else:
                xt[i] = None
        xt = [xi for xi in xt if xi is not None]
        if len(xt) == 0:
            log.debug('Linear dependency in trial subspace')
            break
        log.debug('davidson %d %d  |r|= %4.3g  e= %s  max|de|= %4.3g  lindep= %4.3g',
                  icyc, space, max(dx_norm), e, de[ide], norm)

        fresh_start = fresh_start or (space+len(xt) > max_space)

        if callable(callback):
            callback(locals())

    if type == 3:
        for k in range(nroots):
            x0[k] = abop(x0[k])[1]

    if nroots == 1:
        return e[0], x0[0]
    else:
        return e, x0

def pickeig(w, v, nroots):
    realidx = numpy.where((w.imag == 0))[0]
    return realidx[w[realidx].real.argsort()[:nroots]]

def eig(aop, x0, precond, tol=1e-14, max_cycle=50, max_space=12,
        lindep=1e-14, max_memory=2000, dot=numpy.dot, callback=None,
        nroots=1, lessio=False, left=False, pick=pickeig,
        verbose=logger.WARN):
    ''' A X = X w
    '''
    assert(not left)
    if isinstance(verbose, logger.Logger):
        log = verbose
    else:
        log = logger.Logger(sys.stdout, verbose)

    def qr(xs):
        #q, r = numpy.linalg.qr(numpy.asarray(xs).T)
        #q = [qi/numpy_helper.norm(qi)
        #     for i, qi in enumerate(q.T) if r[i,i] > 1e-7]
        qs = [xs[0]/numpy_helper.norm(xs[0])]
        for i in range(1, len(xs)):
            xi = xs[i].copy()
            for j in range(len(qs)):
                xi -= qs[j] * numpy.dot(qs[j], xi)
            norm = numpy_helper.norm(xi)
            if norm > 1e-7:
                qs.append(xi/norm)
        return qs

    toloose = numpy.sqrt(tol) * 1e-2

    if isinstance(x0, numpy.ndarray) and x0.ndim == 1:
        x0 = [x0]
    max_cycle = min(max_cycle, x0[0].size)
    max_space = max_space + nroots * 2
    # max_space*2 for holding ax and xs, nroots*2 for holding axt and xt
    _incore = max_memory*1e6/x0[0].nbytes > max_space*2+nroots*2
    heff = numpy.empty((max_space,max_space), dtype=x0[0].dtype)
    fresh_start = True

    for icyc in range(max_cycle):
        if fresh_start:
            if _incore:
                xs = []
                ax = []
            else:
                xs = linalg_helper._Xlist()
                ax = linalg_helper._Xlist()
            space = 0
# Orthogonalize xt space because the basis of subspace xs must be orthogonal
# but the eigenvectors x0 are very likely non-orthogonal when A is non-Hermitian.
            xt, x0 = qr(x0), None
            e = numpy.zeros(nroots)
            fresh_start = False
        elif len(xt) > 1:
            xt = qr(xt)
            xt = xt[:40]  # 40 trial vectors at most

        axt = aop(xt)
        for k, xi in enumerate(xt):
            xs.append(xt[k])
            ax.append(axt[k])
        rnow = len(xt)
        head, space = space, space+rnow

        for i in range(rnow):
            for k in range(rnow):
                heff[head+k,head+i] = dot(xt[k].conj(), axt[i])
        for i in range(head):
            axi = ax[i]
            xi = xs[i]
            for k in range(rnow):
                heff[head+k,i] = dot(xt[k].conj(), axi)
                heff[i,head+k] = dot(xi.conj(), axt[k])

        w, v = scipy.linalg.eig(heff[:space,:space])
        idx = pick(w, v, nroots)

        if idx.size < nroots or e.size != nroots:
            de = w[idx].real
        else:
            de = w[idx].real - e
        e = w[idx].real
        v = v[:,idx].real

        x0 = []
        ax0 = []
        if lessio and not _incore:
            for k, ek in enumerate(e):
                x0.append(xs[space-1] * v[space-1,k])
            for i in reversed(range(space-1)):
                xsi = xs[i]
                for k, ek in enumerate(e):
                    x0[k] += v[i,k] * xsi
            ax0 = aop(x0)
        else:
            for k, ek in enumerate(e):
                x0 .append(xs[space-1] * v[space-1,k])
                ax0.append(ax[space-1] * v[space-1,k])
            for i in reversed(range(space-1)):
                xsi = xs[i]
                axi = ax[i]
                for k, ek in enumerate(e):
                    x0 [k] += v[i,k] * xsi
                    ax0[k] += v[i,k] * axi

        ide = numpy.argmax(abs(de))
        if abs(de[ide]) < tol:
            log.debug('converge %d %d  e= %s  max|de|= %4.3g',
                      icyc, space, e, de[ide])
            break

        dx_norm = []
        xt = []
        for k, ek in enumerate(e):
            dxtmp = ax0[k] - ek * x0[k]
            xt.append(dxtmp)
            dx_norm.append(numpy_helper.norm(dxtmp))

        if max(dx_norm) < toloose:
            log.debug('converge %d %d  |r|= %4.3g  e= %s  max|de|= %4.3g',
                      icyc, space, max(dx_norm), e, de[ide])
            break

        # remove subspace linear dependency
        for k, ek in enumerate(e):
            if dx_norm[k] > toloose:
                xt[k] = precond(xt[k], e[0], x0[k])
                xt[k] *= 1/numpy_helper.norm(xt[k])
            else:
                xt[k] = None
        xt = [xi for xi in xt if xi is not None]
        for i in range(space):
            xsi = xs[i]
            for xi in xt:
                xi -= xsi * numpy.dot(xi, xsi)
        norm_min = 1
        for i,xi in enumerate(xt):
            norm = numpy_helper.norm(xi)
            if norm > toloose:
                xt[i] *= 1/norm
                norm_min = min(norm_min, norm)
            else:
                xt[i] = None
        xt = [xi for xi in xt if xi is not None]
        if len(xt) == 0:
            log.debug('Linear dependency in trial subspace')
            break
        log.debug('davidson %d %d  |r|= %4.3g  e= %s  max|de|= %4.3g  lindep= %4.3g',
                  icyc, space, max(dx_norm), e, de[ide], norm_min)

        fresh_start = fresh_start or (space+len(xt) > max_space)

        if callable(callback):
            callback(locals())

    if nroots == 1:
        return e[0], x0[0]
    else:
        return e, x0


if __name__ == '__main__':
    numpy.random.seed(12)
    n = 500
    #a = numpy.random.random((n,n))
    a = numpy.arange(n*n).reshape(n,n)
    a = numpy.sin(numpy.sin(a))
    a = a + a.T + numpy.diag(numpy.random.random(n))*10
    b = numpy.random.random((n,n))
    b = numpy.dot(b,b.T) + numpy.eye(n)*5

    def abop(x):
        return numpy.dot(numpy.asarray(x), a.T), numpy.dot(numpy.asarray(x), b.T)

    def precond(r, e0, x0):
        return r / (a.diagonal() - e0)

    e,u = scipy.linalg.eigh(a, b)
    x0 = [a[0]/numpy.linalg.norm(a[0]),
          a[1]/numpy.linalg.norm(a[1]),]
    e0,x0 = dgeev(abop, x0, precond, type=1, max_cycle=100, max_space=18,
                  verbose=5, nroots=4)
    print(e0[0] - e[0])
    print(e0[1] - e[1])
    print(e0[2] - e[2])
    print(e0[3] - e[3])


    e,u = scipy.linalg.eigh(a, b, type=2)
    x0 = [a[0]/numpy.linalg.norm(a[0]),
          a[1]/numpy.linalg.norm(a[1]),]
    e0,x0 = dgeev(abop, x0, precond, type=2, max_cycle=100, max_space=18,
                  verbose=5, nroots=4)
    print(e0[0] - e[0])
    print(e0[1] - e[1])
    print(e0[2] - e[2])
    print(e0[3] - e[3])


    e,u = scipy.linalg.eigh(a, b, type=2)
    x0 = [a[0]/numpy.linalg.norm(a[0]),
          a[1]/numpy.linalg.norm(a[1]),]
    abdiag = numpy.dot(a,b).diagonal().copy()
    def abop(x):
        x = numpy.asarray(x).T
        return numpy.dot(a, numpy.dot(b, x)).T.copy()
    def precond(r, e0, x0):
        return r / (abdiag-e0)
    e0, x0 = eig(abop, x0, precond, max_cycle=100, max_space=30, verbose=5,
                 nroots=4, pick=pickeig)
    print(e0[0] - e[0])
    print(e0[1] - e[1])
    print(e0[2] - e[2])
    print(e0[3] - e[3])
