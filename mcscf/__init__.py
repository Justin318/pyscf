#!/usr/bin/env python

'''CASCI and CASSCF

Simple usage::

    >>> from pyscf import gto, scf, mcscf
    >>> mol = gto.M(atom='N 0 0 0; N 0 0 1', basis='ccpvdz', verbose=0)
    >>> mf = scf.RHF(mol)
    >>> mf.scf()
    >>> mc = mcscf.CASCI(mf, 6, 6)
    >>> mc.kernel()[0]
    -108.980200816243354
    >>> mc = mcscf.CASSCF(mf, 6, 6)
    >>> mc.kernel()[0]
    -109.044401882238134
    >>> mc = mcscf.CASSCF(mf, 4, 4)
    >>> cas_list = [5,6,8,9] # pick orbitals for CAS space, 1-based indices
    >>> mo = mcscf.sort_mo(mc, mf.mo_coeff, cas_list)
    >>> mc.kernel(mo)[0]
    -109.007378939813691

:func:`mcscf.CASSCF` or :func:`mcscf.CASCI` returns a proper instance of CASSCF/CASCI class.
There are some parameters to control the CASSCF/CASCI method.

    verbose : int
        Print level.  Default value equals to :class:`Mole.verbose`.
    max_memory : float or int
        Allowed memory in MB.  Default value equals to :class:`Mole.max_memory`.
    ncas : int
        Active space size.
    nelecas : tuple of int
        Active (nelec_alpha, nelec_beta)
    ncore : int or tuple of int
        Core electron number.  In UHF-CASSCF, it's a tuple to indicate the different core eletron numbers.
    natorb : bool
        Whether to restore the natural orbital during CASSCF optimization. Default is not.
    canonicalization : bool
        Whether to canonicalize orbitals.  Default is True.
    fcisolver : an instance of :class:`FCISolver`
        The pyscf.fci module provides several FCISolver for different scenario.  Generally,
        fci.direct_spin1.FCISolver can be used for all RHF-CASSCF.  However, a proper FCISolver
        can provide better performance and better numerical stability.  One can either use
        :func:`fci.solver` function to pick the FCISolver by the program or manually assigen
        the FCISolver to this attribute, e.g.

        >>> from pyscf import fci
        >>> mc = mcscf.CASSCF(mf, 4, 4)
        >>> mc.fcisolver = fci.solver(mol, singlet=True)
        >>> mc.fcisolver = fci.direct_spin1.FCISolver(mol)

        You can control FCISolver by setting e.g.::

            >>> mc.fcisolver.max_cycle = 30
            >>> mc.fcisolver.conv_tol = 1e-7

        For more details of the parameter for FCISolver, See :mod:`fci`.

        By replacing this fcisolver, you can easily use the CASCI/CASSCF solver
        with other FCI replacements,  such as DMRG, QMC.  See :mod:`dmrgscf` and
        :mod:`fciqmcscf`.

The Following attributes are used for CASSCF

    conv_tol : float
        Converge threshold.  Default is 1e-7
    conv_tol_grad : float
        Converge threshold for CI gradients and orbital rotation gradients.
        Default is 1e-4
    max_stepsize : float
        The step size for orbital rotation.  Small step size is prefered.
        Default is 0.03.  
        (NOTE although the default step size is small enough for many systems,
        it happens that the orbital optimizor crosses the barriar of local
        minimum and converge to the neighbour solution, e.g. the CAS(4,4) for
        C2H4 in the test files.  In these cases, one need to fine the
        optimization by reducing max_stepsize, max_ci_stepsize and
        max_cycle_micro, max_cycle_micro_inner and ah_start_tol.)

        >>> mc = mcscf.CASSCF(mf, 6, 6)
        >>> mc.max_stepsize = .01
        >>> mc.max_cycle_micro = 1
        >>> mc.max_cycle_macro = 100
        >>> mc.max_cycle_micro_inner = 1
        >>> mc.ah_start_tol = 1e-6

    max_ci_stepsize : float
        The max size for approximate CI updates.  The approximate updates are
        used in 1-step algorithm, to estimate the change of CI wavefunction wrt
        the orbital rotation.  Small step size is prefered.  Default is 0.01.
    max_cycle_macro : int
        Max number of macro iterations.  Default is 50.
    max_cycle_micro : int
        Max number of micro iterations in each macro iteration.  Depending on
        systems, increasing this value might reduce the total macro
        iterations.  Generally, 2 - 3 steps should be enough.  Default is 2.
    max_cycle_micro_inner : int
        Max number of steps for the orbital rotations allowed for the augmented
        hessian solver.  It can affect the actual size of orbital rotation.
        Even with a small max_stepsize, a few max_cycle_micro_inner can
        accumulate the rotation and leads to a significant change of the CAS
        space.  Depending on systems, increasing this value migh reduce the
        total number of macro iterations.  The value between 2 - 8 is preferred.
        Default is 4.
    ah_level_shift : float, for AH solver.
        Level shift for the Davidson diagonalization in AH solver.  Default is 0.
    ah_conv_tol : float, for AH solver.
        converge threshold for Davidson diagonalization in AH solver.  Default is 1e-8.
    ah_max_cycle : float, for AH solver.
        Max number of iterations allowd in AH solver.  Default is 20.
    ah_lindep : float, for AH solver.
        Linear dependence threshold for AH solver.  Default is 1e-16.
    ah_start_tol : flat, for AH solver.
        In AH solver, the orbital rotation is started without completely solving the AH problem.
        This value is to control the start point. Default is 1e-4.
    ah_start_cycle : int, for AH solver.
        In AH solver, the orbital rotation is started without completely solving the AH problem.
        This value is to control the start point. Default is 3.

        ``ah_conv_tol``, ``ah_max_cycle``, ``ah_lindep``, ``ah_start_tol`` and ``ah_start_cycle``
        can affect the accuracy and performance of CASSCF solver.  Lower
        ``ah_conv_tol`` and ``ah_lindep`` can improve the accuracy of CASSCF
        optimization, but slow down the performance.
        
        >>> from pyscf import gto, scf, mcscf
        >>> mol = gto.M(atom='N 0 0 0; N 0 0 1', basis='ccpvdz', verbose=0)
        >>> mf = scf.UHF(mol)
        >>> mf.scf()
        >>> mc = mcscf.CASSCF(mf, 6, 6)
        >>> mc.conv_tol = 1e-10
        >>> mc.ah_conv_tol = 1e-5
        >>> mc.kernel()
        -109.044401898486001
        >>> mc.ah_conv_tol = 1e-10
        >>> mc.kernel()
        -109.044401887945668

    chkfile : str
        Checkpoint file to save the intermediate orbitals during the CASSCF optimization.
        Default is the checkpoint file of mean field object.


Saved results

    e_tot : float
        Total MCSCF energy (electronic energy plus nuclear repulsion)
    ci : ndarray
        CAS space FCI coefficients
    converged : bool, for CASSCF only
        It indicates CASSCF optimization converged or not.
    mo_energy: ndarray,
        Diagonal elements of general Fock matrix
    mo_coeff : ndarray, for CASSCF only
        Optimized CASSCF orbitals coefficients
        Note the orbitals are NOT natural orbitals by default.  There are two
        inbuilt methods to convert the mo_coeff to natural orbitals.
        1. Set .natorb attribute.  It can be used before calculation.
        2. call .cas_natorb_ method after the calculation to in-place convert the orbitals
'''


from pyscf.mcscf import mc1step
from pyscf.mcscf import mc1step_symm
from pyscf.mcscf import casci
from pyscf.mcscf import casci_symm
from pyscf.mcscf import addons
from pyscf.mcscf import casci_uhf
from pyscf.mcscf import mc1step_uhf
from pyscf.mcscf.addons import *
from pyscf.mcscf import chkfile

def CASSCF(mf, ncas, nelecas, **kwargs):
    from pyscf import gto
    if isinstance(mf, gto.Mole):
        raise RuntimeError('''
You see this error message because of the API updates in pyscf v0.10.
In the new API, the first argument of CASSCF/CASCI class is HF objects.  e.g.
        mc = mcscf.CASSCF(mf, norb, nelec)
Please see   http://sunqm.net/pyscf/code-rule.html#api-rules   for the details
of API conventions''')

    mf = _convert_to_rhf(mf)
    if mf.mol.symmetry:
        mc = mc1step_symm.CASSCF(mf, ncas, nelecas, **kwargs)
    else:
        mc = mc1step.CASSCF(mf, ncas, nelecas, **kwargs)
    return mc

RCASSCF = CASSCF


def CASCI(mf, ncas, nelecas, **kwargs):
    from pyscf import gto
    if isinstance(mf, gto.Mole):
        raise RuntimeError('''
You see this error message because of the API updates in pyscf v0.10.
In the new API, the first argument of CASSCF/CASCI class is HF objects.  e.g.
        mc = mcscf.CASCI(mf, norb, nelec)
Please see   http://sunqm.net/pyscf/code-rule.html#api-rules   for the details
of API conventions''')

    mf = _convert_to_rhf(mf)
    if mf.mol.symmetry:
        mc = casci_symm.CASCI(mf, ncas, nelecas, **kwargs)
    else:
        mc = casci.CASCI(mf, ncas, nelecas, **kwargs)
    return mc

RCASCI = CASCI


def UCASCI(mf, ncas, nelecas, **kwargs):
    from pyscf import scf
    if isinstance(mf, scf.uhf.UHF):
        mc = casci_uhf.CASCI(mf, ncas, nelecas, **kwargs)
    else:
        raise RuntimeError('First argument needs to be UHF object')
    return mc


def UCASSCF(mf, ncas, nelecas, **kwargs):
    from pyscf import scf
    if isinstance(mf, scf.uhf.UHF):
        mc = mc1step_uhf.CASSCF(mf, ncas, nelecas, **kwargs)
    else:
        raise RuntimeError('First argument needs to be UHF object')
    return mc


def _convert_to_rhf(mf, convert_df=True):
    import copy
    import numpy
    from pyscf.lib import logger
    import pyscf.df
    if isinstance(mf, scf.uhf.UHF):
        # convert to RHF
        mf = copy.copy(mf)
        if mf.mo_energy is not None: mf.mo_energy = mf.mo_energy[0]
        if mf.mo_coeff is not None:  mf.mo_coeff  = mf.mo_coeff[0]
        if mf.mo_occ is not None:    mf.mo_occ    = mf.mo_occ[0]

    # Avoid doing density fitting
    if (convert_df and hasattr(mf, 'with_df') and
        isinstance(mf.with_df, (pyscf.df.DF, pyscf.df.XDF))):
        mf = copy.copy(mf)
        logger.warn(mf, 'CASSCF: The first argument is a density-fitting SCF object. '
                    'Its orbitals are taken as the initial guess of CASSCF.\n'
                    'The CASSCF object is the normal solver (no approximated integrals). '
                    'mcscf.DFCASSCF is the function to create density fitting CASSCF '
                    '(with approximate 2e integrals).')
        mf.with_df = False
    return mf


try:
    from pyscf.mcscf import df
    def DFCASSCF(mf, ncas, nelecas, auxbasis=None, **kwargs):
        mf = _convert_to_rhf(mf, False)
        if mf.mol.symmetry:
            mc = mc1step_symm.CASSCF(mf, ncas, nelecas, **kwargs)
        else:
            mc = mc1step.CASSCF(mf, ncas, nelecas, **kwargs)
        return df.density_fit(mc, auxbasis)

    def DFCASCI(mf, ncas, nelecas, auxbasis=None, **kwargs):
        mf = _convert_to_rhf(mf, False)
        if mf.mol.symmetry:
            mc = casci_symm.CASCI(mf, ncas, nelecas, **kwargs)
        else:
            mc = casci.CASCI(mf, ncas, nelecas, **kwargs)
        return df.density_fit(mc, auxbasis)

    approx_hessian = df.approx_hessian

    def density_fit(mc, auxbasis=None, with_df=None):
        if hasattr(mc._scf, 'with_df') and mc._scf.with_df:
            return df.density_fit(mc, auxbasis, with_df)
        else:
            from pyscf.lib import logger
            logger.warn(mc, 'NOTE: approx_hessian function is available for DF orbital hessian!\n'
                        'The CASSCF object is built on normal SCF object %s '
                        '(without density fitting).  Currently, this density_fit '
                        'function will call approx_hessian to approximate orbital '
                        'hessian for backward compatibility.\n'
                        'In the future release, it will be removed and the '
                        'density_fit function will only generate DF-CASSCF method.',
                        mc._scf.__class__)
            return approx_hessian(mc, auxbasis, with_df)
except ImportError:
    pass
