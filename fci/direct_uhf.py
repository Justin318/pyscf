#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#

'''
Different FCI solvers are implemented to support different type of symmetry.
                    Symmetry
File                Point group   Spin singlet   Real hermitian*    Alpha/beta degeneracy
direct_spin0_symm   Yes           Yes            Yes                Yes
direct_spin1_symm   Yes           No             Yes                Yes
direct_spin0        No            Yes            Yes                Yes
direct_spin1        No            No             Yes                Yes
direct_uhf          No            No             Yes                No
direct_nosym        No            No             No**               Yes

*  Real hermitian Hamiltonian implies (ij|kl) = (ji|kl) = (ij|lk) = (ji|lk)
** Hamiltonian is real but not hermitian, (ij|kl) != (ji|kl) ...
'''

import sys
import ctypes
import numpy
import pyscf.lib
import pyscf.gto
import pyscf.ao2mo
from pyscf.fci import cistring
from pyscf.fci import direct_spin1

libfci = pyscf.lib.load_library('libfci')

# When the spin-orbitals do not have the degeneracy on spacial part,
# there is only one version of FCI which is close to _spin1 solver.
# The inputs: h1e has two parts (h1e_a, h1e_b),
# h2e has three parts (h2e_aa, h2e_ab, h2e_bb)

def contract_1e(f1e, fcivec, norb, nelec, link_index=None):
    fcivec = numpy.asarray(fcivec, order='C')
    link_indexa, link_indexb = direct_spin1._unpack(norb, nelec, link_index)
    na, nlinka = link_indexa.shape[:2]
    nb, nlinkb = link_indexb.shape[:2]
    assert(fcivec.size == na*nb)
    ci1 = numpy.zeros_like(fcivec)
    f1e_tril = pyscf.lib.pack_tril(f1e[0])
    libfci.FCIcontract_a_1e(f1e_tril.ctypes.data_as(ctypes.c_void_p),
                            fcivec.ctypes.data_as(ctypes.c_void_p),
                            ci1.ctypes.data_as(ctypes.c_void_p),
                            ctypes.c_int(norb),
                            ctypes.c_int(na), ctypes.c_int(nb),
                            ctypes.c_int(nlinka), ctypes.c_int(nlinkb),
                            link_indexa.ctypes.data_as(ctypes.c_void_p),
                            link_indexb.ctypes.data_as(ctypes.c_void_p))
    f1e_tril = pyscf.lib.pack_tril(f1e[1])
    libfci.FCIcontract_b_1e(f1e_tril.ctypes.data_as(ctypes.c_void_p),
                            fcivec.ctypes.data_as(ctypes.c_void_p),
                            ci1.ctypes.data_as(ctypes.c_void_p),
                            ctypes.c_int(norb),
                            ctypes.c_int(na), ctypes.c_int(nb),
                            ctypes.c_int(nlinka), ctypes.c_int(nlinkb),
                            link_indexa.ctypes.data_as(ctypes.c_void_p),
                            link_indexb.ctypes.data_as(ctypes.c_void_p))
    return ci1

# Note eri is NOT the 2e hamiltonian matrix, the 2e hamiltonian is
# h2e = eri_{pq,rs} p^+ q r^+ s
#     = (pq|rs) p^+ r^+ s q - (pq|rs) \delta_{qr} p^+ s
# so eri is defined as
#       eri_{pq,rs} = (pq|rs) - (1/Nelec) \sum_q (pq|qs)
# to restore the symmetry between pq and rs,
#       eri_{pq,rs} = (pq|rs) - (.5/Nelec) [\sum_q (pq|qs) + \sum_p (pq|rp)]
# Please refer to the treatment in direct_spin1.absorb_h1e
def contract_2e(eri, fcivec, norb, nelec, link_index=None):
    fcivec = numpy.asarray(fcivec, order='C')
    g2e_aa = pyscf.ao2mo.restore(4, eri[0], norb)
    g2e_ab = pyscf.ao2mo.restore(4, eri[1], norb)
    g2e_bb = pyscf.ao2mo.restore(4, eri[2], norb)

    link_indexa, link_indexb = direct_spin1._unpack(norb, nelec, link_index)
    na, nlinka = link_indexa.shape[:2]
    nb, nlinkb = link_indexb.shape[:2]
    assert(fcivec.size == na*nb)
    ci1 = numpy.empty_like(fcivec)

    libfci.FCIcontract_uhf2e(g2e_aa.ctypes.data_as(ctypes.c_void_p),
                             g2e_ab.ctypes.data_as(ctypes.c_void_p),
                             g2e_bb.ctypes.data_as(ctypes.c_void_p),
                             fcivec.ctypes.data_as(ctypes.c_void_p),
                             ci1.ctypes.data_as(ctypes.c_void_p),
                             ctypes.c_int(norb),
                             ctypes.c_int(na), ctypes.c_int(nb),
                             ctypes.c_int(nlinka), ctypes.c_int(nlinkb),
                             link_indexa.ctypes.data_as(ctypes.c_void_p),
                             link_indexb.ctypes.data_as(ctypes.c_void_p))
    return ci1

def contract_2e_hubbard(u, fcivec, norb, nelec, opt=None):
    if isinstance(nelec, (int, numpy.number)):
        nelecb = nelec//2
        neleca = nelec - nelecb
    else:
        neleca, nelecb = nelec
    u_aa, u_ab, u_bb = u

    strsa = numpy.asarray(cistring.gen_strings4orblist(range(norb), neleca))
    strsb = numpy.asarray(cistring.gen_strings4orblist(range(norb), nelecb))
    na = cistring.num_strings(norb, neleca)
    nb = cistring.num_strings(norb, nelecb)
    fcivec = fcivec.reshape(na,nb)
    fcinew = numpy.zeros_like(fcivec)

    if u_aa != 0:  # u * n_alpha^+ n_alpha
        for i in range(norb):
            maska = (strsa & (1<<i)) > 0
            fcinew[maska] += u_aa * fcivec[maska]
    if u_ab != 0:  # u * (n_alpha^+ n_beta + n_beta^+ n_alpha)
        for i in range(norb):
            maska = (strsa & (1<<i)) > 0
            maskb = (strsb & (1<<i)) > 0
            fcinew[maska[:,None]&maskb] += 2*u_ab * fcivec[maska[:,None]&maskb]
    if u_bb != 0:  # u * n_beta^+ n_beta
        for i in range(norb):
            maskb = (strsb & (1<<i)) > 0
            fcinew[:,maskb] += u_bb * fcivec[:,maskb]
    return fcinew

def make_hdiag(h1e, eri, norb, nelec):
    if isinstance(nelec, (int, numpy.number)):
        nelecb = nelec//2
        neleca = nelec - nelecb
    else:
        neleca, nelecb = nelec
    h1e_a = numpy.ascontiguousarray(h1e[0])
    h1e_b = numpy.ascontiguousarray(h1e[1])
    g2e_aa = pyscf.ao2mo.restore(1, eri[0], norb)
    g2e_ab = pyscf.ao2mo.restore(1, eri[1], norb)
    g2e_bb = pyscf.ao2mo.restore(1, eri[2], norb)

    link_indexa = cistring.gen_linkstr_index(range(norb), neleca)
    link_indexb = cistring.gen_linkstr_index(range(norb), nelecb)
    na = link_indexa.shape[0]
    nb = link_indexb.shape[0]

    occslista = numpy.asarray(link_indexa[:,:neleca,0], order='C')
    occslistb = numpy.asarray(link_indexb[:,:nelecb,0], order='C')
    hdiag = numpy.empty(na*nb)
    jdiag_aa = numpy.asarray(numpy.einsum('iijj->ij',g2e_aa), order='C')
    jdiag_ab = numpy.asarray(numpy.einsum('iijj->ij',g2e_ab), order='C')
    jdiag_bb = numpy.asarray(numpy.einsum('iijj->ij',g2e_bb), order='C')
    kdiag_aa = numpy.asarray(numpy.einsum('ijji->ij',g2e_aa), order='C')
    kdiag_bb = numpy.asarray(numpy.einsum('ijji->ij',g2e_bb), order='C')
    libfci.FCImake_hdiag_uhf(hdiag.ctypes.data_as(ctypes.c_void_p),
                             h1e_a.ctypes.data_as(ctypes.c_void_p),
                             h1e_b.ctypes.data_as(ctypes.c_void_p),
                             jdiag_aa.ctypes.data_as(ctypes.c_void_p),
                             jdiag_ab.ctypes.data_as(ctypes.c_void_p),
                             jdiag_bb.ctypes.data_as(ctypes.c_void_p),
                             kdiag_aa.ctypes.data_as(ctypes.c_void_p),
                             kdiag_bb.ctypes.data_as(ctypes.c_void_p),
                             ctypes.c_int(norb),
                             ctypes.c_int(na), ctypes.c_int(nb),
                             ctypes.c_int(neleca), ctypes.c_int(nelecb),
                             occslista.ctypes.data_as(ctypes.c_void_p),
                             occslistb.ctypes.data_as(ctypes.c_void_p))
    return numpy.asarray(hdiag)

def absorb_h1e(h1e, eri, norb, nelec, fac=1):
    if not isinstance(nelec, (int, numpy.number)):
        nelec = sum(nelec)
    h1e_a, h1e_b = h1e
    h2e_aa = pyscf.ao2mo.restore(1, eri[0], norb).copy()
    h2e_ab = pyscf.ao2mo.restore(1, eri[1], norb).copy()
    h2e_bb = pyscf.ao2mo.restore(1, eri[2], norb).copy()
    f1e_a = h1e_a - numpy.einsum('jiik->jk', h2e_aa) * .5
    f1e_b = h1e_b - numpy.einsum('jiik->jk', h2e_bb) * .5
    f1e_a *= 1./(nelec+1e-100)
    f1e_b *= 1./(nelec+1e-100)
    for k in range(norb):
        h2e_aa[:,:,k,k] += f1e_a
        h2e_aa[k,k,:,:] += f1e_a
        h2e_ab[:,:,k,k] += f1e_a
        h2e_ab[k,k,:,:] += f1e_b
        h2e_bb[:,:,k,k] += f1e_b
        h2e_bb[k,k,:,:] += f1e_b
    return (pyscf.ao2mo.restore(4, h2e_aa, norb) * fac,
            pyscf.ao2mo.restore(4, h2e_ab, norb) * fac,
            pyscf.ao2mo.restore(4, h2e_bb, norb) * fac)

def pspace(h1e, eri, norb, nelec, hdiag, np=400):
    if isinstance(nelec, (int, numpy.number)):
        nelecb = nelec//2
        neleca = nelec - nelecb
    else:
        neleca, nelecb = nelec
    h1e_a = numpy.ascontiguousarray(h1e[0])
    h1e_b = numpy.ascontiguousarray(h1e[1])
    g2e_aa = pyscf.ao2mo.restore(1, eri[0], norb)
    g2e_ab = pyscf.ao2mo.restore(1, eri[1], norb)
    g2e_bb = pyscf.ao2mo.restore(1, eri[2], norb)
    link_indexa = cistring.gen_linkstr_index_trilidx(range(norb), neleca)
    link_indexb = cistring.gen_linkstr_index_trilidx(range(norb), nelecb)
    nb = link_indexb.shape[0]
    addr = numpy.argsort(hdiag)[:np]
    addra = addr // nb
    addrb = addr % nb
    stra = numpy.array([cistring.addr2str(norb,neleca,ia) for ia in addra],
                       dtype=numpy.long)
    strb = numpy.array([cistring.addr2str(norb,nelecb,ib) for ib in addrb],
                       dtype=numpy.long)
    np = len(addr)
    h0 = numpy.zeros((np,np))
    libfci.FCIpspace_h0tril_uhf(h0.ctypes.data_as(ctypes.c_void_p),
                                h1e_a.ctypes.data_as(ctypes.c_void_p),
                                h1e_b.ctypes.data_as(ctypes.c_void_p),
                                g2e_aa.ctypes.data_as(ctypes.c_void_p),
                                g2e_ab.ctypes.data_as(ctypes.c_void_p),
                                g2e_bb.ctypes.data_as(ctypes.c_void_p),
                                stra.ctypes.data_as(ctypes.c_void_p),
                                strb.ctypes.data_as(ctypes.c_void_p),
                                ctypes.c_int(norb), ctypes.c_int(np))

    for i in range(np):
        h0[i,i] = hdiag[addr[i]]
    h0 = pyscf.lib.hermi_triu(h0)
    return addr, h0


# be careful with single determinant initial guess. It may lead to the
# eigvalue of first davidson iter being equal to hdiag
def kernel(h1e, eri, norb, nelec, ci0=None, level_shift=1e-3, tol=1e-10,
           lindep=1e-14, max_cycle=50, max_space=12, nroots=1,
           davidson_only=False, pspace_size=400, orbsym=None, wfnsym=None,
           **kwargs):
    return direct_spin1._kfactory(FCISolver, h1e, eri, norb, nelec, ci0, level_shift,
                                  tol, lindep, max_cycle, max_space, nroots,
                                  davidson_only, pspace_size, **kwargs)

def energy(h1e, eri, fcivec, norb, nelec, link_index=None):
    h2e = absorb_h1e(h1e, eri, norb, nelec, .5)
    ci1 = contract_2e(h2e, fcivec, norb, nelec, link_index)
    return numpy.dot(fcivec.reshape(-1), ci1.reshape(-1))

# dm_pq = <|p^+ q|>
def make_rdm1s(fcivec, norb, nelec, link_index=None):
    return direct_spin1.make_rdm1s(fcivec, norb, nelec, link_index)

# spacial part of DM, dm_pq = <|p^+ q|>
def make_rdm1(fcivec, norb, nelec, link_index=None):
    return direct_spin1.make_rdm1(fcivec, norb, nelec, link_index)

def make_rdm12s(fcivec, norb, nelec, link_index=None, reorder=True):
    return direct_spin1.make_rdm12s(fcivec, norb, nelec, link_index, reorder)

def trans_rdm1s(cibra, ciket, norb, nelec, link_index=None):
    return direct_spin1.trans_rdm1s(cibra, ciket, norb, nelec, link_index)

# spacial part of DM
def trans_rdm1(cibra, ciket, norb, nelec, link_index=None):
    return direct_spin1.trans_rdm1(cibra, ciket, norb, nelec, link_index)

def trans_rdm12s(cibra, ciket, norb, nelec, link_index=None, reorder=True):
    return direct_spin1.trans_rdm12s(cibra, ciket, norb, nelec, link_index, reorder)


###############################################################
# uhf-integral direct-CI driver
###############################################################

class FCISolver(direct_spin1.FCISolver):

    def absorb_h1e(self, h1e, eri, norb, nelec, fac=1):
        return absorb_h1e(h1e, eri, norb, nelec, fac)

    def make_hdiag(self, h1e, eri, norb, nelec):
        return make_hdiag(h1e, eri, norb, nelec)

    def pspace(self, h1e, eri, norb, nelec, hdiag, np=400):
        return pspace(h1e, eri, norb, nelec, hdiag, np)

    def contract_1e(self, f1e, fcivec, norb, nelec, link_index=None, **kwargs):
        return contract_1e(f1e, fcivec, norb, nelec, link_index, **kwargs)

    def contract_2e(self, eri, fcivec, norb, nelec, link_index=None, **kwargs):
        return contract_2e(eri, fcivec, norb, nelec, link_index, **kwargs)

    def spin_square(self, fcivec, norb, nelec):
        from pyscf.fci import spin_op
        return spin_op.spin_square(fcivec, norb, nelec)

if __name__ == '__main__':
    from functools import reduce
    from pyscf import gto
    from pyscf import scf
    from pyscf import ao2mo

    mol = gto.Mole()
    mol.verbose = 0
    mol.output = None#"out_h2o"
    mol.atom = [
        ['H', ( 1.,-1.    , 0.   )],
        ['H', ( 0.,-1.    ,-1.   )],
        ['H', ( 1.,-0.5   ,-1.   )],
        #['H', ( 0.,-0.5   ,-1.   )],
        #['H', ( 0.,-0.5   ,-0.   )],
        ['H', ( 0.,-0.    ,-1.   )],
        ['H', ( 1.,-0.5   , 0.   )],
        ['H', ( 0., 1.    , 1.   )],
    ]

    mol.basis = {'H': 'sto-3g'}
    mol.charge = 1
    mol.spin = 1
    mol.build()

    m = scf.UHF(mol)
    ehf = m.scf()

    cis = FCISolver(mol)
    norb = m.mo_energy[0].size
    nea = (mol.nelectron+1) // 2
    neb = (mol.nelectron-1) // 2
    nelec = (nea, neb)
    mo_a = m.mo_coeff[0]
    mo_b = m.mo_coeff[1]
    h1e_a = reduce(numpy.dot, (mo_a.T, m.get_hcore(), mo_a))
    h1e_b = reduce(numpy.dot, (mo_b.T, m.get_hcore(), mo_b))
    g2e_aa = ao2mo.incore.general(m._eri, (mo_a,)*4, compact=False)
    g2e_aa = g2e_aa.reshape(norb,norb,norb,norb)
    g2e_ab = ao2mo.incore.general(m._eri, (mo_a,mo_a,mo_b,mo_b), compact=False)
    g2e_ab = g2e_ab.reshape(norb,norb,norb,norb)
    g2e_bb = ao2mo.incore.general(m._eri, (mo_b,)*4, compact=False)
    g2e_bb = g2e_bb.reshape(norb,norb,norb,norb)
    h1e = (h1e_a, h1e_b)
    eri = (g2e_aa, g2e_ab, g2e_bb)
    na = cistring.num_strings(norb, nea)
    nb = cistring.num_strings(norb, neb)
    numpy.random.seed(15)
    fcivec = numpy.random.random((na,nb))

    e = kernel(h1e, eri, norb, nelec)[0]
    print(e, e - -8.65159903476)
