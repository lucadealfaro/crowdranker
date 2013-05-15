# -*- coding: utf-8 -*-

import access
import ranker
import grades_rank

@auth.requires_signature()
def run_rep_sys():
    """Runs the reputation system."""
    c = db.venue(request.vars[REPUTATION_SYSTEM_PARAM_VENUE_ID])
    if c is None:
        logger.warning("Invalid call to reputation system computation: " + str(request))
        return redirect(URL('venues', 'managed_index'))
    try:
        current.num_iterations = int(request.vars[REPUTATION_SYSTEM_PARAM_NUM_ITERATIONS])
    except Exception:
        logger.warning("Missing number of iterations in specification.")
        current.num_iterations = 4
    try:
        current.review_percentage = float(request.vars[REPUTATION_SYSTEM_PARAM_REVIEW_PERCENTAGE])
    except Exception:
        current.review_percentage = 25
    startover = False
    try:
        startover = request.vars[REPUTATION_SYSTEM_STARTOVER] == 'True'
    except Exception:
        pass
    run_id = request.vars[REPUTATION_SYSTEM_RUN_ID]
    publish = request.vars[REPUTATION_SYSTEM_PUBLISH] == 'True'
    algo = request.vars[REPUTATION_SYSTEM_ALGO]
    current.cost_type = request.vars[REPUTATION_SYSTEM_COST_TYPE]
    if current.cost_type is None:
        current.cost_type = ALGO_DEFAULT_COST_TYPE
    try:
        current.pos_slope = float(request.vars[REPUTATION_SYSTEM_POS_SLOPE])
    except Exception:
        current.pos_slope = ALGO_DEFAULT_POS_SLOPE
    try:
        current.neg_slope = float(request.vars[REPUTATION_SYSTEM_NEG_SLOPE])
    except Exception:
        current.neg_slope = ALGO_DEFAULT_NEG_SLOPE
     
    current.normalize_grades = request.vars[REPUTATION_SYSTEM_NORMALIZE_GRADES] == 'True'
    try:
        current.normalization_scale = float(request.vars[REPUTATION_SYSTEM_NORMALIZATION_SCALE])
    except Exception:
        current.normalization_scale = ALGO_DEFAULT_NORMALIZATION_SCALE
    
    current.use_submission_rank_in_rep = request.vars[REPUTATION_SYSTEM_USE_SUBMISSION_RANK_IN_REP] == 'True'
    try:
        current.submission_rank_exp = float(request.vars[REPUTATION_SYSTEM_SUBMISSION_RANK_REP_EXP])
    except Exception:
        current.submission_rank_exp = ALGO_DEFAULT_RANK_REP_EXP
        
    current.reputation_method = request.vars[REPUTATION_SYSTEM_REPUTATION_METHOD]
    try:
        current.prec_coefficient = float(request.vars[REPUTATION_SYSTEM_PREC_COEFF])
    except Exception:
        current.prec_coefficient = ALGO_DEFAULT_PREC_COEFF
    
    # Fix
    current.cost_coefficient = 1.0
    logger.info("Reputation system request: %r" % request.vars)
    logger.info("Starting reputation system run for venue: " + c.name)
    logger.info("Requested number of iterations: %d" % current.num_iterations)
    logger.info("Review percentage: %f" % current.review_percentage)
    logger.info("Using algo: %r" % algo)
    logger.info("Run id: %r" % run_id)
    logger.info("Publish: %s" % publish)
    logger.info("Number of iterations: %s" % current.num_iterations)
    logger.info("Pos slope: %r" % current.pos_slope)
    logger.info("Neg slope: %r" % current.neg_slope)
    logger.info("Normalize grades: %r" % current.normalize_grades)
    logger.info("Normalization scale: %r" % current.normalization_scale)
    logger.info("Use submission rank in rep: %r" % current.use_submission_rank_in_rep)
    logger.info("Submission rank exponent for reputation: %r" % current.submission_rank_exp)
    logger.info("Reputation method: %r" % current.reputation_method)
    logger.info("Precision coefficient: %r" % current.prec_coefficient)
    
    # Stores the run parameters.
    db.run_parameters.update_or_insert(
        (db.run_parameters.venue_id == c.id) & (db.run_parameters.run_id == run_id),
        venue_id = c.id, 
        run_id = run_id,
        params = repr(request.vars))
    
    if algo == ALGO_OPT:
        grades_rank.rank_by_grades(c.id, run_id=run_id, publish=publish)
    else:
        # DEPRECATED
        ranker.run_reputation_system(c.id, num_of_iterations=current.num_iterations, 
                                     review_percentage=current.review_percentage,
                                     startover=startover, publish=publish,
                                     run_id=run_id)
    logger.info("Completed reputation system run for venue: " + c.name)
    return redirect(URL('ranking', 'view_grades', args=[c.id]))

