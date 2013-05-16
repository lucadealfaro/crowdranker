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
        num_iterations = int(request.vars[REPUTATION_SYSTEM_PARAM_NUM_ITERATIONS])
    except Exception:
        logger.warning("Missing number of iterations in specification.")
        num_iterations = 4
    try:
        review_percentage = float(request.vars[REPUTATION_SYSTEM_PARAM_REVIEW_PERCENTAGE])
    except Exception:
        review_percentage = 25
    startover = False
    try:
        startover = request.vars[REPUTATION_SYSTEM_STARTOVER] == 'True'
    except Exception:
        pass
    run_id = request.vars[REPUTATION_SYSTEM_RUN_ID]
    publish = request.vars[REPUTATION_SYSTEM_PUBLISH] == 'True'
    algo = request.vars[REPUTATION_SYSTEM_ALGO]
    cost_type = request.vars[REPUTATION_SYSTEM_COST_TYPE]
    if cost_type is None:
        cost_type = ALGO_DEFAULT_COST_TYPE
    try:
        pos_slope = float(request.vars[REPUTATION_SYSTEM_POS_SLOPE])
    except Exception:
        pos_slope = ALGO_DEFAULT_POS_SLOPE
    try:
        neg_slope = float(request.vars[REPUTATION_SYSTEM_NEG_SLOPE])
    except Exception:
        neg_slope = ALGO_DEFAULT_NEG_SLOPE
     
    normalize_grades = request.vars[REPUTATION_SYSTEM_NORMALIZE_GRADES] == 'True'
    try:
        normalization_scale = float(request.vars[REPUTATION_SYSTEM_NORMALIZATION_SCALE])
    except Exception:
        normalization_scale = ALGO_DEFAULT_NORMALIZATION_SCALE
    
    use_submission_rank_in_rep = request.vars[REPUTATION_SYSTEM_USE_SUBMISSION_RANK_IN_REP] == 'True'
    try:
        submission_rank_exp = float(request.vars[REPUTATION_SYSTEM_SUBMISSION_RANK_REP_EXP])
    except Exception:
        submission_rank_exp = ALGO_DEFAULT_RANK_REP_EXP
    
    logger.info("Reputation system request: %r" % request.vars)
    logger.info("Starting reputation system run for venue: " + c.name)
    logger.info("Requested number of iterations: %d" % num_iterations)
    logger.info("Review percentage: %f" % review_percentage)
    logger.info("Using algo: %r" % algo)
    logger.info("Run id: %r" % run_id)
    logger.info("Publish: %s" % publish)
    logger.info("Number of iterations: %s" % num_iterations)
    logger.info("Pos slope: %r" % pos_slope)
    logger.info("Neg slope: %r" % neg_slope)
    logger.info("Normalize grades: %r" % normalize_grades)
    logger.info("Normalization scale: %r" % normalization_scale)
    logger.info("Use submission rank in rep: %r" % use_submission_rank_in_rep)
    logger.info("Submission rank exponent for reputation: %r" % submission_rank_exp)
    
    # Stores the run parameters.
    db.run_parameters.update_or_insert(
        (db.run_parameters.venue_id == c.id) & (db.run_parameters.run_id == run_id),
        venue_id = c.id, 
        run_id = run_id,
        params = repr(request.vars))
    
    if algo == ALGO_OPT:
        grades_rank.rank_by_grades(
            c.id, run_id=run_id, publish=publish, 
            cost_type=cost_type, pos_slope=pos_slope, neg_slope=neg_slope,
            normalize=normalize_grades, normalization_scale=normalization_scale,
            use_submission_rank_for_reputation=use_submission_rank_in_rep,
            submission_rank_exponent=submission_rank_exp
            )
    else:
        ranker.run_reputation_system(c.id, num_of_iterations=num_iterations, 
                                     review_percentage=review_percentage,
                                     startover=startover, publish=publish,
                                     run_id=run_id)
    logger.info("Completed reputation system run for venue: " + c.name)
    return redirect(URL('ranking', 'view_grades', args=[c.id]))

