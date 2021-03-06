#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#

import numpy
from pyscf import gto, scf, mcscf

'''
Use callback interface to save CASSCF orbitals for each iteration.
'''

mol = gto.M(
    atom = [
        ["F", (0., 0., 0.)],
        ["H", (0., 0., 1.6)],],
    basis = 'cc-pvdz')
mf = scf.RHF(mol)
mf.kernel()

# 6 active orbitals, 4 alpha, 2 beta electrons
mc = mcscf.CASSCF(mf, 6, (4,2))
def save_mo_coeff(envs):
    imacro = envs['imacro']
    imicro = envs['imicro']
    if imacro % 3 == 2:
        fname = 'mcscf-mo-%d-%d.npy' % (imacro+1, imicro+1)
        print('Save MO of step %d-%d in file %s' % (imacro+1, imicro+1, fname))
        numpy.save(fname, envs['mo_coeff'])
mc.callback = save_mo_coeff
mc.kernel()

# Read one of the saved orbitals for the initial guess for new calculation
mc = mcscf.CASSCF(mf, 6, (4,2))
mo = numpy.load('mcscf-mo-6-1.npy')
mc.kernel(mo)

