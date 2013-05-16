# -*- coding: utf-8 -*-

from datetime import datetime
import datetime as time
from gluon import *
import numpy as np
import random
from rank import Cost
from rank import Rank
import util

NUM_BINS = 2001
AVRG = NUM_BINS / 2
STDEV = NUM_BINS / 8

def read_db_for_get_item(venue_id):
    """ The function fills containers for get_item function.
        - subm_list - list of submissions
        - qdistr_param - list of quality distributions parameters for
            submissions such that i-th submission sub_list[i] has
            parameters qdistr_param[2*i] - quality mean,
            qdistr_param[2*i + 1] - quality standard deviation.
        - subm_to_assigned - a dictionary: subm id -> number of times it was assigned
        - subm_to_finished- a dictionary: subm id -> number of times it was
            completed + rejected
    """
    db = current.db
    # List of all submissions id for given venue.
    subm_list = []
    subm_to_assigned = {}
    subm_to_finished = {}
    subm_records = db(db.submission.venue_id == venue_id).select()
    # Fetching quality distributions parametes for each submission.
    qdistr_param = []
    for row in subm_records:
        subm_list.append(row.id)
        if row.quality is None or row.error is None:
            qdistr_param.append(AVRG)
            qdistr_param.append(STDEV)
        else:
            qdistr_param.append(row.quality)
            qdistr_param.append(row.error)
        subm_to_assigned[row.id] = row.n_assigned_reviews
        subm_to_finished[row.id] = row.n_completed_reviews + row.n_rejected_reviews
    return subm_list, qdistr_param, subm_to_assigned, subm_to_finished



def get_qdistr_param(venue_id, items_id):
    db = current.db
    if items_id == None:
        return None
    qdistr_param = []
    for x in items_id:
        quality_row = db((db.submission.venue_id == venue_id) &
                  (db.submission.id == x)).select(db.submission.quality,
                  db.submission.error).first()
        if (quality_row is None or quality_row.quality is None or
            quality_row.error is None):
            qdistr_param.append(AVRG)
            qdistr_param.append(STDEV)
        else:
            qdistr_param.append(quality_row.quality)
            qdistr_param.append(quality_row.error)
    return qdistr_param

def get_init_average_stdev():
    """ Method returns tuple with average and stdev for initializing
    field in table quality.
    """
    return AVRG, STDEV

def get_subm_assigned_to_user(venue_id, user):
    """ Method return three list:
        - old_items - submissions assigned but not rejected by the user.
        - rejected_items - submissions rejected by the user.
        - users_items - submissions authored by the user."""
    db = current.db
    old_items = []
    rejected_items = []
    users_items = []
    old_tasks = db((db.task.venue_id == venue_id) & (db.task.user == user)).select()
    for task in old_tasks:
        if task.rejected:
            rejected_items.append(task.submission_id)
        else:
            old_items.append(task.submission_id)
    # Fetching submissions authored by the user.
    rows  = db((db.submission.venue_id == venue_id) &
                        (db.submission.user == user)).select(db.submission.id)
    if rows is not None:
        users_items = [r.id for r in rows]
    return old_items, rejected_items, users_items


def none_as_zero(el):
    if el is None:
        return 0
    else:
        return el


def get_list_min_subm(subm_list, subm_to_assigned,
                      subm_to_finished, subm_to_recent):
    """Gets the list of submissions that have received the least number of reviwes,
    counting as a review also recently assigned review tasks (that are still likely
    to be completed)."""
    freq_list = []
    for subm_id in subm_list:
        count = min(subm_to_assigned[subm_id], 
                    subm_to_finished[subm_id] + none_as_zero(subm_to_recent[subm_id]) + 1)
        freq_list.append((subm_id, count))
    m = min([x[1] for x in freq_list])
    list_min_subm = [x[0] for x in freq_list if x[1] == m]
    return list_min_subm


def has_min_count(subm_id, venue_id, subm_to_assigned, subm_to_finished,
                  subm_to_recent, time_window):
    """Checks that a submission indeed has minimum number of reviews that 
    have been done or recently assigned."""
    db = current.db
    if subm_to_assigned[subm_id] == subm_to_finished[subm_id]:
        return True
    if subm_to_recent[subm_id] is not None:
        # We must have already read it.
        return True
    # We need to check how long ago has the review been assigned.
    rows = db(db.task.submission_id == subm_id).select()
    counter = 0
    t = datetime.utcnow()
    for r in rows:
        if (not r.is_completed and not r.rejected
            and t - r.assigned_date < time.timedelta(hours=time_window)):
            counter += 1
    if subm_to_recent[subm_id] == counter:
        return True
    subm_to_recent[subm_id] = counter
    return False


def get_item(venue_id, user, can_rank_own_submissions=False,
             sample_always_randomly=False, time_window=2):
    """
    Description of a sampling method:
        We always sample item which have minimum count, where
        count = min(times assinged, times completed + times rejected + recent + 1)
        If sample_always_randomly True then sample always randomly.
        Otherwise, we sample randomly only in half cases, on other half cases
        we sample proportional to misrank error.
    """
    db = current.db
    # Reading the db.
    subm_list, qdistr_param, subm_to_assigned, subm_to_finished = read_db_for_get_item(venue_id)
    # Get submissions assigned to the user.
    old_items, rejected_items, users_items = get_subm_assigned_to_user(venue_id, user)
    if can_rank_own_submissions:
        users_items = []
    # Filter subm_list by deleting old_items, rejected_items, users_items.
    subm_list_filtered = [x for x in subm_list if x not in old_items and
                                         x not in rejected_items and
                                         x not in users_items]
    # Check whether we have items to sample from or not.
    if len(subm_list_filtered) == 0:
        return None
    # subm_to_recent is a dictionary mapping submission id to how many times
    # the submission has been assigned and has not been reviewed recently. 
    # Since this is expensive to compute for each submission, we nitialize it with zeros,
    # and we will fix it later to > 0 if we need on a per-item basis.
    subm_to_recent = dict((subm_id, None) for subm_id in subm_list_filtered)
    # List of submissions with min reviews, candidates for assignment. 
    list_min_subm = []
    # Okay, now we are trying to sample a submissions.
    while True:
        if len(list_min_subm) == 0:
            list_min_subm = get_list_min_subm(subm_list_filtered,
                                              subm_to_assigned,
                                              subm_to_finished, subm_to_recent)
        if random.random() < 0.5 or sample_always_randomly:
            # Sample randomly.
            new_subm = random.sample(list_min_subm, 1)[0]
        else:
            # Sample using quality distributions.
            # Constructing pool of items.
            pool_items = list_min_subm[:]
            pool_items.extend(old_items)
            # Fetching quality distribution parameters.
            qdistr_param_pool = []
            for subm_id in pool_items:
                idx = subm_list.index(subm_id)
                qdistr_param_pool.append(qdistr_param[2 * idx])
                qdistr_param_pool.append(qdistr_param[2 * idx + 1])
            rankobj = Rank.from_qdistr_param(pool_items, qdistr_param_pool)
            new_subm = rankobj.sample_item(old_items)
        # Okay, we have sampled a new submission, now let's check that it has
        # minimum count indeed.
        if has_min_count(new_subm, venue_id, subm_to_assigned,
                         subm_to_finished, subm_to_recent, time_window):
            return new_subm
        else:
            list_min_subm.remove(new_subm)


def process_comparison(venue_id, user, sorted_items, new_item,
                       alpha_annealing=0.6):
    """ Function updates quality distributions and rank of submissions (items).

    Arguments:
        - sorted_items is a list of submissions id sorted by user such that
        rank(sorted_items[i]) > rank(sorted_items[j]) for i > j

        - new_item is an id of a submission from sorted_items which was new
        to the user. If sorted_items contains only two elements then
        new_item is None.
    """
    db = current.db
    if sorted_items == None or len(sorted_items) <= 1:
        return None
    qdistr_param = get_qdistr_param(venue_id, sorted_items)
    # If qdistr_param is None then some submission does not have qualities yet,
    # therefore we cannot process comparison.
    if qdistr_param == None:
        return None
    rankobj = Rank.from_qdistr_param(sorted_items, qdistr_param,
                                     alpha=alpha_annealing)
    result = rankobj.update(sorted_items, new_item)
    # Updating the DB.
    for x in sorted_items:
        perc, avrg, stdev = result[x]
        # Updating submission table with its quality and error.
        db((db.submission.id == x) &
           (db.submission.venue_id == venue_id)).update(quality=avrg, error=stdev)


def get_or_0(d, k):
    r = d.get(k, None)
    if r == None:
        return 0.0
    else:
        return r


def compute_final_grades_helper(list_of_users, user_to_subm_grade,
                                user_to_rev_grade, review_percentage=25):
    """This function computes the final grades.  We assume that every user has only one submission.

    Arguments:
        - list_of_users contains all users who submitted or reviewed submissions
    """
    # Review percentage as a [0, 1] float.
    review_percentage_01 = review_percentage / 100.0
    # Computes the final grade.
    user_to_final_grade = {}
    for u in list_of_users:
        g = (get_or_0(user_to_subm_grade, u) * (1.0 - review_percentage_01) +
             get_or_0(user_to_rev_grade,  u) * review_percentage_01)
        user_to_final_grade[u] = g
    # Computes the final grade percentiles.
    l = []
    for u, g in user_to_final_grade.iteritems():
        l.append((u, g))
    sorted_l = sorted(l, key = lambda x: x[1], reverse=True)
    user_to_perc = {}
    n_users = float(len(sorted_l))
    for i, el in enumerate(sorted_l):
        user_to_perc[el[0]] = 100.0 * (n_users - float(i)) / n_users
    return user_to_perc, user_to_final_grade


def read_db_for_rep_sys(venue_id):
    db = current.db
    logger = current.logger
    # Containers to fill.
    # Lists have l suffix, dictionaries user -> val have d suffix.
    user_l = [] # This list contains submitters and reviewers.
    subm_l = []
    subm_d = {}
    ordering_l = []
    ordering_d = {}
    qdist_param = []
    # Reading submission table.
    rows = db(db.submission.venue_id == venue_id).select()
    for r in rows:
        subm_l.append(r.id)
        subm_d[r.user] = r.id
        user_l.append(r.user)
        qdist_param.append(r.quality)
        qdist_param.append(r.error)
    # Reading comparisons table.
    rows = db((db.comparison.venue_id == venue_id) & (db.comparison.is_valid == True)).select()
    
    for r in rows:
        # Reverses the ordering.
        sorted_items = util.get_list(r.ordering)[::-1]
        if len(sorted_items) < 2:
            continue
        ordering_d[r.user] = sorted_items
        # Initializing reviewers reputation and accuracy.
        ordering_l.append((sorted_items, r.user))
    # Adding reviewers to user_l.
    for user in ordering_d.iterkeys():
        if user not in user_l:
            user_l.append(user)
    return user_l, subm_l, ordering_l, subm_d, ordering_d, qdist_param


def read_reputations(venue_id, publish, run_id):
    """This returns rep_d."""
    db = current.db
    if publish:
        rows = db(db.grades.venue_id == venue_id).select()
    else:
        rows = db((db.grades_exp.venue_id == venue_id ) &
                  (db.grades_exp.run_id == run_id)).select()
    rep_d = {}
    for r in rows:
        rep_d[r.user] = r.reputation
    return rep_d


def get_list_of_all_students(venue_id):
    """ Gets the users that participate in the class."""
    db = current.db
    logger = current.logger
    c = db.venue(venue_id)
    ul = []
    r = db.user_list(c.submit_constraint)
    if r is not None:
        ul = util.get_list(r.user_list)
    if not c.raters_equal_submitters:
        ulr = []
        r = db.user_list(c.rate_constraint)
        if r is not None:
            ulr = util.get_list(r.user_list)
        ul = util.union_list(ul, ulr)
    return ul


def write_to_db_iteration(venue_id, rankobj_result, subm_l, user_l,
                            ordering_d, accuracy_d, rep_d, subm_d,
                            publish, run_id):
    """Writes to the db the result of an iteration."""
    db = current.db
    logger = current.logger
    # Gets the users that participate in the class.
    ul = get_list_of_all_students(venue_id)
    if len(ul) == 0:
        # Nothing to write.
        if publish:
            db(db.grades.venue_id == venue_id).delete()
            db.commit()
            return
        else:
            db((db.grades_exp.venue_id == venue_id) &
               (db.grades_exp.run_id == run)).delete()
            db.commit()
            return
    # Writes to the submission.
    for u in ul:
        subm_id = subm_d.get(u)
        if subm_id is not None:
            perc, avrg, stdev = rankobj_result[subm_id]
            db(db.submission.id == subm_id).update(quality=avrg, error=stdev, percentile=perc)

    if publish:
        # Writes to db.grades table.
        for u in ul:
            if ordering_d.has_key(u):
                n_ratings = len(ordering_d[u])
            else:
                n_ratings = 0
            db.grades.update_or_insert((db.grades.venue_id == venue_id) &
                                      (db.grades.user == u),
                                       venue_id = venue_id,
                                       user = u,
                                       accuracy = accuracy_d.get(u),
                                       reputation = rep_d.get(u),
                                       )
    else:
        # Writes the grades for each user.
        for u in ul:
            db.grades_exp.update_or_insert((db.grades_exp.venue_id == venue_id) &
                                      (db.grades_exp.user == u) &
                                      (db.grades_exp.run_id == run_id),
                                       venue_id = venue_id,
                                       user = u,
                                       run_id = run_id,
                                       review_grade = accuracy_d.get(u),
                                       reputation = rep_d.get(u),
                                       )
    db.commit()


def write_to_db_final_result(venue_id, rankobj_result, subm_l, user_l,
                             ordering_d, accuracy_d, rep_d, perc_final_d,
                             final_grade_d, subm_d, ranking_algo_description,
                             publish, run_id):
    db = current.db
    logger = current.logger
    accuracy_perc_d = util.compute_percentile(accuracy_d)
    # Gets the users that participate in the class.
    ul = get_list_of_all_students(venue_id)
    if len(ul) == 0:
        # Nothing to write.
        if publish:
            db(db.grades.venue_id == venue_id).delete()
            db.commit()
            return
        else:
            db((db.grades_exp.venue_id == venue_id) &
               (db.grades_exp.run_id == run)).delete()
            db.commit()
            return
    # Writes to the submission.
    user_to_subm_perc = {}
    for u in ul:
        subm_id = subm_d.get(u)
        if subm_id is not None:
            perc, avrg, stdev = rankobj_result[subm_id]
            db(db.submission.id == subm_id).update(quality=avrg, error=stdev, percentile=perc)
            submission_percentile = perc
        else:
            submission_percentile = None
        user_to_subm_perc[u] = submission_percentile

    if publish:
        # Write grades to db.grades.
        for u in ul:
            if ordering_d.has_key(u):
                n_ratings = len(ordering_d[u])
            else:
                n_ratings = 0
            db.grades.update_or_insert((db.grades.venue_id == venue_id) &
                                      (db.grades.user == u),
                                       venue_id = venue_id,
                                       user = u,
                                       submission_percentile = user_to_subm_perc[u],
                                       grade = None,
                                       accuracy = accuracy_d.get(u),
                                       accuracy_percentile = accuracy_perc_d.get(u),
                                       reputation = rep_d.get(u),
                                       n_ratings = n_ratings,
                                       percentile = perc_final_d.get(u),
                                       )
        # Saving evaluation date.
        t = datetime.utcnow()
        db(db.venue.id == venue_id).update(latest_grades_date = t,
                                           ranking_algo_description = ranking_algo_description)
    else:
        for u in ul:
            # Write grades to db.grades_exp.
            db.grades_exp.update_or_insert((db.grades_exp.venue_id == venue_id) &
                                      (db.grades_exp.user == u) &
                                      (db.grades_exp.run_id == run_id),
                                       venue_id = venue_id,
                                       user = u,
                                       run_id = run_id,
                                       subm_grade = None,
                                       submission_percent = user_to_subm_perc[u],
                                       review_grade = accuracy_d.get(u),
                                       review_percent = accuracy_perc_d.get(u),
                                       reputation = rep_d.get(u),
                                       grade = perc_final_d.get(u),
                                       )
    db.commit()


def run_reputation_system(venue_id,
                          review_percentage=25, 
                          alpha_annealing=0.5,
                          num_of_iterations=4, 
                          num_small_iterations=14, 
                          base_reputation=1.0,
                          startover=False,
                          publish=False,
                          run_id='default'):
    """ Function calculates submission qualities, user's reputation, reviewer's
    quality and final grades.
    Arguments:
        - num_small_iterations works as a switch between two types of reputation system
        If the argument is None then we update using all comparisons one time in chronological order.
        Otherwise we use "small alpha" approach, where num_small_iterations is
        number of iterations.
    """
    db = current.db
    logger = current.logger
    # Reading the DB to get submission and user information.
    # Lists have l suffix, dictionaries user -> val have d suffix.
    logger.info("Reading information for venue %d" % venue_id)
    user_l, subm_l, ordering_l, subm_d, ordering_d, qdist_param = read_db_for_rep_sys(venue_id)
    logger.info("Finished reading.")

    logger.info("Starting iteration number %d" % num_of_iterations)
    # Okay, now we are ready to run main iterations.
    result = None
    if startover:
        logger.info("Starting the computation from defaults.")
        # Initializing the rest of containers.
        qdist_param_default = []
        for subm in subm_l:
            qdist_param_default.append(AVRG)
            qdist_param_default.append(STDEV)
        rep_d = {user: alpha_annealing for user in user_l}
        rankobj = Rank.from_qdistr_param(subm_l, qdist_param_default,
                                         alpha=alpha_annealing)
    else:
        logger.info("Using results from previous iteration.")
        rep_d = read_reputations(venue_id, publish, run_id)
        rankobj = Rank.from_qdistr_param(subm_l, qdist_param,
                                         alpha=alpha_annealing)

    logger.info("Doing small iterations")
    for i in xrange(num_small_iterations):
        # Genarating random permutation.
        idxs = range(len(ordering_l))
        random.shuffle(idxs)
        for idx in idxs:
            ordering, user = ordering_l[idx]
            alpha = rep_d[user]
            alpha = 1 - (1 - alpha) ** (1.0/(num_small_iterations))
            # This processes one comparison.
            result = rankobj.update(ordering, alpha_annealing=alpha,
                        annealing_type='after_normalization')

    if result is None:
        # Too few submissions; let's just say that they are all good.
        result = {}
        accuracy_d = {}
        for u in subm_d:
            result[subm_d[u]] = (100.0, 1.0, 1.0)
        for u in rep_d:
            accuracy_d[u] = 1.0
            rep_d[u] = 1.0
    else:
        # Computing reputation.
        logger.info("Computing user reputations")
        accuracy_d = {}
        rep_d = {}
        for user in user_l:
            if subm_d.has_key(user):
                perc, avrg, stdev = result[subm_d[user]]
                rank = perc / 100.0
            else:
                rank = 0.5
            if ordering_d.has_key(user):
                ordering = ordering_d[user]
                accuracy = rankobj.evaluate_ordering_using_dirichlet(ordering)
            else:
                accuracy = 0.0
            accuracy_d[user] = accuracy
            # Computer user's reputation.
            rep_d[user] = 0.1 + 0.9 * (accuracy * (rank ** 0.5))
            # rep_d[user] = ((rank + base_reputation) * (accuracy + base_reputation)) ** 0.5 - base_reputation

    if num_of_iterations == 1:
        # Computing submission grades.
        subm_grade_d = {}
        for user, subm in subm_d.iteritems():
            perc, avrg, stdev = result[subm]
            subm_grade_d[user] = perc / 100.0
        # Computing final grades.
        logger.info("Computing final grade")
        perc_final_d, final_grade_d = compute_final_grades_helper(user_l, subm_grade_d, rep_d, 
                                                                  review_percentage=review_percentage)
        if num_small_iterations is None:
            description = "Reputation system on all comparisons in chronological order"
            if num_of_iterations == 1:
                description = "Ranking without reputation system. All comparisons are used in chronological order"
        else:
            description = "Reputation system with small alpha and only last comparisons"
            if num_of_iterations == 1:
                description = "No reputation system and small alpha !?!?"
        # Writing to the BD.
        logger.info("Writing grades to db")
        write_to_db_final_result(venue_id, result, subm_l, user_l, ordering_d,
                                 accuracy_d, rep_d, perc_final_d,
                                 final_grade_d, subm_d,
                                 description, publish, run_id)
        logger.info("Written grades to db")
        return None
    else:
        # Writes the results of the iteration.
        write_to_db_iteration(venue_id, result, subm_l, user_l, ordering_d,
                              accuracy_d, rep_d, subm_d, publish, run_id)
        # Spawns one more iteration.
        return URL('queues', 'run_rep_sys', vars={
                    current.REPUTATION_SYSTEM_PARAM_NUM_ITERATIONS: num_of_iterations - 1,
                    current.REPUTATION_SYSTEM_PARAM_VENUE_ID: venue_id,
                    current.REPUTATION_SYSTEM_RUN_ID: run_id,
                    current.REPUTATION_SYSTEM_PARAM_REVIEW_PERCENTAGE: review_percentage,
                    current.REPUTATION_SYSTEM_STARTOVER: 'False',
                    current.REPUTATION_SYSTEM_PUBLISH: publish,
                    })
