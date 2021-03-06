#include "cint.h"
#include "vhf/cvhf.h"

#if !defined HAVE_DEFINED_NR_AO2MOENVS_H
#define HAVE_DEFINED_NR_AO2MOENVS_H
struct _AO2MOEnvs {
        int natm;
        int nbas;
        int *atm;
        int *bas;
        double *env;
        int nao;
        int klsh_start;
        int klsh_count;
        int bra_start;
        int bra_count;
        int ket_start;
        int ket_count;
        int ncomp;
        int *ao_loc;
        double *mo_coeff;
        CINTOpt *cintopt;
        CVHFOpt *vhfopt;
};
#endif

void AO2MOnr_e1fill_drv(int (*intor)(), int (*cgto_in_shell)(), void (*fill)(),
                        double *eri, int klsh_start, int klsh_count, int nkl,
                        int ncomp, CINTOpt *cintopt, CVHFOpt *vhfopt,
                        int *atm, int natm, int *bas, int nbas, double *env);

void AO2MOnr_e1_drv(int (*intor)(), int (*cgto_in_shell)(), void (*fill)(),
                    void (*ftrans)(), int (*fmmm)(),
                    double *eri, double *mo_coeff,
                    int klsh_start, int klsh_count, int nkl,
                    int i_start, int i_count, int j_start, int j_count,
                    int ncomp, CINTOpt *cintopt, CVHFOpt *vhfopt,
                    int *atm, int natm, int *bas, int nbas, double *env);

void AO2MOnr_e2_drv(void (*ftrans)(), int (*fmmm)(),
                    double *vout, double *vin, double *mo_coeff,
                    int nijcount, int nao,
                    int i_start, int i_count, int j_start, int j_count,
                    int *ao_loc, int nbas);

