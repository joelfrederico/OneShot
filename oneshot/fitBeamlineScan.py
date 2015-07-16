#!/usr/bin/env python
import numpy as _np
import copy as _copy
import scisalt.scipy as ssc
import scisalt.matplotlib as sm
import matplotlib.pyplot as _plt
import slactrac as _sltr

import logging
loggerlevel = logging.DEBUG
logger      = logging.getLogger(__name__)


class ScanFit(ssc.LinLsqFit):
    def __init__(self, eaxis, *args, **kwargs):
        self._resetlist = _np.append(self._resetlist, ['_emit', '_Beam', '_emitn'])
        ssc.LinLsqFit.__init__(self, *args, **kwargs)
        self.eaxis = eaxis

    def _get_e_gamma(self):
        argmin = _np.argmin(self.y_fit)
        return self.eaxis[argmin]/(0.5109989e-3)
    gamma = property(_get_e_gamma)

    # ======================================
    # emit (calculated)
    # ======================================
    def _get_emit(self):
        if self._emit is None:
            self._emit = _np.sqrt( self.beta[0, 0] * self.beta[2, 0] - _np.square(self.beta[1, 0]) )
        return self._emit
    emit = property(_get_emit)

    # ======================================
    # emitn (calculated)
    # ======================================
    def _get_emitn(self):
        if self._emitn is None:
            self._emitn = self.emit * self.gamma
        return self._emitn
    emitn = property(_get_emitn)

    # ======================================
    # twiss (calculated)
    # ======================================
    def _get_Beam(self):
        if self._Beam is None:
            beta0 = self.beta[0, 0]/self.emit
            gamma0 = self.beta[2, 0]/self.emit
            alpha0 = -_np.sign(self.beta[1, 0])*_np.sqrt(beta0*gamma0-1)
            self._Beam = _sltr.BeamParams(beta=beta0, alpha=alpha0, emit=self.emit)
        return self._Beam
    Beam = property(_get_Beam)


class BeamlineScanFit(object):
    def __init__(self, fitresults, spotexpected):
        self.fitresults   = fitresults
        self.spotexpected = spotexpected


# Fit bowtie {{{
def fitBeamlineScan(beamline, y, error=None, verbose=False, plot=False, eaxis=None):
    logger.log(level=loggerlevel, msg='Fitting beamline scan...')

    beamline_manip = _copy.deepcopy(beamline)
    numsteps = beamline_manip.size
    y              = y[_np.newaxis]
    error          = error[_np.newaxis].transpose()
    X              = _np.zeros([numsteps, 3])
    spotexpected   = _np.zeros(numsteps)
    
    for i, bl in enumerate(beamline_manip):
        R11             = bl.R[0, 0]
        R12             = bl.R[0, 1]
        X[i, 0]          = R11*R11
        X[i, 1]          = 2*R11*R12
        X[i, 2]          = R12*R12
        # spotexpected[i] = _np.sqrt((R11*R11*twiss.beta - 2*R11*R12*twiss.alpha + R12*R12*twiss.gamma)*emitx)
        # twiss=beamline.twiss_x
        # spotexpected[i] = bl.twiss.transport(bl.R[0:2, 0:2]).spotsize(emitx)
        # spotexpected[i] = bl.spotsize_x_end(emitx)
        spotexpected[i] = bl.spotsize_x_end

    if plot:
        sm.figure('Expected')
        xax = _np.linspace(1, numsteps, numsteps)
        _plt.plot(xax, _np.sqrt(y.transpose()), xax, spotexpected)
        _plt.show()
        pass

    # beta is the best solution of beam parameters:
    # sig^2 = R11^2 <x^2> + 2 R11 R12 <xx'> + R12^2 <x'^2>
    # beta[0, 0] = <x^2>
    # beta[1, 0] = <xx'>
    # beta[2, 0] = <x'^2>

    myfit     = ScanFit(eaxis=eaxis, y_unweighted=y.transpose(), X_unweighted=X, y_error=error)
    beta      = myfit.beta
    covar     = myfit.covar
    # chisq_red = myfit.chisq_red
    emit      = myfit.emit

    # emit = _np.sqrt( beta[0, 0] * beta[2, 0] - _np.square(beta[1, 0]) )
    del_emit_sq = _np.power(1/(2*emit), 2) * \
        (
            _np.power(beta[2, 0] * covar[0, 0]   , 2) +
            _np.power(2*beta[1, 0] * covar[1, 1] , 2) +
            _np.power(beta[0, 0] * covar[2, 2]   , 2)  # +
            # 2 * (-beta[2, 0] * 2 * beta[1, 0]) * covar[0, 1] +
            # 2 * (beta[2, 0] * beta[0, 0]) * covar[0, 2] +
            # 2 * (-2*beta[1, 0] * beta[0, 0]) * covar[1, 2]
        )

    # chisq_red = _mt.chisquare(y.transpose(), _np.dot(X_unweighted, beta), error, ddof=3, verbose=verbose)

    # beta0 = beta[0, 0]/emit
    # gamma0 = beta[2, 0]/emit
    # alpha0 = -_np.sign(beta[1, 0])*_np.sqrt(beta0*gamma0-1)

    logger.log(level=loggerlevel, msg='Emittance error is:\t\t{}.'.format(_np.sqrt(del_emit_sq)))
    logger.log(level=loggerlevel, msg='Emittance fit:\t\t\t{}.'.format(emit))
    logger.log(level=loggerlevel, msg='Normalized emittance fit:\t{}.'.format(myfit.emitn))
    logger.log(level=loggerlevel, msg='Initial beta fit:\t\t{}.'.format(myfit.Beam.beta))
    logger.log(level=loggerlevel, msg='Initial alpha fit:\t\t{}.'.format(myfit.Beam.alpha))
    logger.log(level=loggerlevel, msg='Initial gamma fit:\t\t{}.'.format(myfit.Beam.gamma))
    logger.log(level=loggerlevel, msg='Initial spot from fit:\t\t{}.'.format(_np.sqrt(myfit.beta[0, 0])))
    logger.log(level=loggerlevel, msg='Min spot size (gauss fit): \t{}.'.format(min(_np.sqrt(y[0]))))
    logger.log(level=loggerlevel, msg='Min spot size (emit fit): \t{}.'.format(myfit.Beam.minspotsize))

    logger.log(level=loggerlevel, msg='Beta* is: \t\t\t{}.'.format(myfit.Beam.betastar))
    logger.log(level=loggerlevel, msg='s* is: \t\t\t\t{}.'.format(myfit.Beam.sstar))

    # output = _col.namedtuple('fitbowtie_output', ['emit', 'twiss', 'spotexpected', 'X', 'X_unweighted', 'beta', 'covar', 'chisq_red'])
    # out = output(emit, , spotexpected, myfit.X, myfit.X_unweighted, myfit.beta, myfit.covar, myfit.chisq_red)

    out = BeamlineScanFit(fitresults=myfit, spotexpected=spotexpected)

    return out
# }}}