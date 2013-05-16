# -*- coding: utf-8 -*-

import convopt
from gluon import *
from rank import Rank
from rank import Cost
import util
from datetime import datetime
import numpy as np
import random
import math
import gluon.contrib.simplejson as simplejson


class MinimizationObjective:
    """ Class contains methods for computing objective function Q for
    main optimization problem, its gradient and hessian matrix. """
    def __init__(self, D, delta_vec):
        """
        Let g_m^i be a grade for submission i assigned by author of comparison
        m.
        Comparison is a tuple of grades assigned to two sumbssions, i.e.
        comparison m is (g_m^i, g_m^j) where g_m^i > g_m^j.
        Arguments:
            - D is matrix of size KxL, where K is a number of
            comparisons and L is a number of submissions.
            Row D_m corresponds to a comparison m:(g_m^i, g_m^j).
            D_m has everywhere zeros except two positions i and j.
            D_m^i = 1 and D_m^j = -1, where g_m^i > g_m^j.
            - delta_vec is a vector of values (g_m^i - g_m^j), i.e.
            delta_vec[m] = (g_m^i - g_m^j).
            Matrix D and vector delta_vec are syncronized so that row D_m and
            element delta_vec[m] corresponds to the same
            comparison m:(g_m^i, g_m^j).
            x is an arguemnt for some methods of the class (x supposed to be
            true grades). x is syncronized with matrix D in a way that
            i-th column corresponds to x[i] - grade of submission i.
            - current.cost_type  defines possible cost types:
            'linear' - uses cost of type slope * y * y/(1 + |y|) on both sides
            in all other cases cost fuction is y*y when y < 0, and y*y/(1+y)
            when y >= 0.
            - current.pos_slope and current.neg_slope are coefficients for 'linear' cost function
        """
        self.D = D
        self.D_T = D.transpose()
        # TODO(michael): if pseudoinverse takes too much time then
        # get rid of next two lines (matrix D can be huge).
        self.D_pinv = np.linalg.pinv(D) # Moore-Penrose pseudoinverse
        self.D_pinv_T = self.D_pinv.transpose()
        self.delta_vec = delta_vec

    def compute_f(self, x):
        """ About argumetns please look at function compute_Q. """
        y = np.dot(self.D, x) - self.delta_vec
        if current.cost_type == 'linear':
            # Cost function is current.neg_slope * y * y/(1 - y) when y < 0, and
            # current.pos_slope * y * y/(1 + y) when y >= 0.
            f_neg = current.neg_slope * y ** 2 / (1 + np.abs(y))
            f_pos = current.pos_slope * y ** 2 / (1 + np.abs(y))
        else:
            # Cost fuction is y*y when y < 0, and y*y/(1+y) when y >= 0.
            f_neg = 1.0 * y ** 2
            f_pos = 1.0 * y ** 2 / (1 + np.abs(y))
        idx = y > 0
        f_neg[idx] = f_pos[idx]
        return f_neg

    def compute_f_prime(self, x):
        y = np.dot(self.D, x) - self.delta_vec
        if current.cost_type == 'linear':
            f_neg = 2.0 * y / (1 + np.abs(y)) + 1.0 * y ** 2 / (1 + np.abs(y)) ** 2
            f_neg = current.neg_slope * f_neg
            f_pos = 2.0 * y / (1 + np.abs(y)) - 1.0 * y ** 2 / (1 + np.abs(y)) ** 2
            f_pos = current.pos_slope * f_pos
        else:
            f_neg = 2.0 * y
            f_pos = 2.0 * y / (1 + np.abs(y)) - 1.0 * y ** 2 / (1 + np.abs(y)) ** 2
        idx = y > 0
        f_neg[idx] = f_pos[idx]
        return f_neg

    def compute_f_dbl_prime(self, x):
        y = np.dot(self.D, x) - self.delta_vec
        if current.cost_type == 'linear':
            f_neg = (2.0 / (1 + np.abs(y)) + 4.0 * y / (1 + np.abs(y)) ** 2 +
                     2.0 * y ** 2 / (1 + np.abs(y)) ** 3)
            f_neg = current.neg_slope * f_neg
            f_pos = (2.0 / (1 + np.abs(y)) - 4.0 * y / (1 + np.abs(y)) ** 2 +
                     2.0 * y ** 2 / (1 + np.abs(y)) ** 3)
            f_pos = current.pos_slope * f_pos
        else:
            f_neg = 2.0 * (np.zeros(len(y)) + 1)
            f_pos = (2.0 / (1 + np.abs(y)) - 4.0 * y / (1 + np.abs(y)) ** 2 +
                     2.0 * y ** 2 / (1 + np.abs(y)) ** 3)
        idx = y > 0
        f_neg[idx] = f_pos[idx]
        return f_neg

    def compute_Q(self, x, r):
        """ Method computes value of the objective function Q at the point x.
        Arguments:
            -x is vector of lenght L (number of submissions).
            Vector x should by syncronized with matrix D in a sense that
            i-th column of matrix D correspond to i-th item of vector x.
            -r is vector of reputation such that r[m] is a reputation of author
            of comparison m."""
        f = self.compute_f(x)
        f = f * r
        return np.sum(f)

    def get_Q(self, r):
        """ Note that it is imprtant that matrix D and vector delta_vec
        don't get modified in a life span of the function Q."""
        r = r[:] # to get rid of dependency on r.
        def Q(x):
            return self.compute_Q(x, r)
        return Q

    def compute_grad_Q(self, x, r):
        f1 = self.compute_f_prime(x)
        grad_Q = np.dot(self.D_T, f1 * r)
        return grad_Q

    def get_grad_Q(self, r):
        r = r[:]
        def grad_Q(x):
            return self.compute_grad_Q(x, r)
        return grad_Q

    def compute_hessian_Q(self, x, r):
        f1 = self.compute_f_dbl_prime(x)
        f1 = f1 * r
        H = f1[..., np.newaxis] * self.D
        H = np.dot(self.D_T, H)
        return H

    def get_hessian_Q(self, r):
        r = r[:]
        def hessian_Q(x):
            return self.compute_hessian_Q(x, r)
        return hessian_Q

    def compute_inverse_hessian_Q(self, x, r):
        precision = 0.0001 # TODO(michael): what it should really be?
        f1 = self.compute_f_dbl_prime(x)
        y = f1 * r
        y_abs = np.abs(y)
        # Inverting each nonzero element of y.
        idx_nonzero = y > precision
        y[idx_nonzero] = 1.0 / y[idx_nonzero]
        # Now calculating D_pinv * diag(y) * D_pinv_T
        H_inv = y[..., np.newaxis] * self.D_pinv_T
        H_inv = np.dot(self.D_pinv, H_inv)
        return H_inv

    def get_inverse_hessian_Q(self, r):
        r = r[:]
        def inverse_hessian_Q(x):
            return self.compute_inverse_hessian_Q(x, r)
        return inverse_hessian_Q

def decode_json_grades(dict_grades_json):
    """ dict_grades_json is a json serialized dictionary subm_id -> grade.
    """
    current.logger
    # Getting grades.
    try:
        subm_id_to_grade_raw = simplejson.loads(dict_grades_json)
    except Exception, e:
        logger.debug("Error in reading grades")
        return {}
    subm_id_to_grade = {}
    for (s, g) in subm_id_to_grade_raw.iteritems():
        try:
            s_id = long(s)
        except Exception, e:
            logger.debug("Error in reading grades")
            return {}
        subm_id_to_grade[s_id] = float(g)
    return subm_id_to_grade

def get_num_rows_of_D(compar_rows):
    """Computes number of rows in matrix D."""
    num_rows = 0
    for r in compar_rows:
        m = len(util.get_list(r.ordering))
        if m >= 2:
            num_rows += (m - 1) * m * 0.5
    return num_rows


def get_dict_subm_id_to_idx(compar_rows):
    items_from_orderings = set()
    for r in compar_rows:
        ordering = util.get_list(r.ordering)
        m = len(ordering)
        if m >= 2:
            items_from_orderings.update(set(ordering))
    subm_id_list = list(items_from_orderings)
    subm_id_to_idx = dict((subm_id_list[idx], idx) for
                                               idx in xrange(len(subm_id_list)))
    return subm_id_to_idx


def get_vector_of_average_grades(subm_id_to_list_of_grades, idx_to_subm_id):
    subm_id_to_avrg_grade = {}
    for subm_id, grade_list in subm_id_to_list_of_grades.iteritems():
        subm_id_to_avrg_grade[subm_id] = np.mean(grade_list)
    avrg_grades = np.zeros(len(idx_to_subm_id))
    for idx in xrange(len(idx_to_subm_id)):
        subm_id = idx_to_subm_id[idx]
        if subm_id_to_avrg_grade.has_key(subm_id):
            avrg_grades[idx] = subm_id_to_avrg_grade[subm_id]
    return avrg_grades


def get_number_of_tasks(venue_id):
    """ Method returns dictionaries:
    user_to_n_graded_tasks - tasks to which a user has assigned grade
    user_to_n_rejected_tasks - rejected tasks
    user_to_n_completed_tasks
    """
    db = current.db
    user_to_n_graded_tasks = {}
    user_to_n_rejected_tasks = {}
    user_to_n_completed_tasks = {}
    rows = db(db.task.venue_id == venue_id).select()
    for r in rows:
        u = r.user
        # Checking that we have initialized entries with 0.
        if not user_to_n_graded_tasks.has_key(u):
            user_to_n_graded_tasks[u] = 0
        if not user_to_n_rejected_tasks.has_key(u):
            user_to_n_rejected_tasks[u] = 0
        if not user_to_n_completed_tasks.has_key(u):
            user_to_n_completed_tasks[u] = 0
        # Fetching information.
        if r.is_completed:
            user_to_n_completed_tasks[u] = user_to_n_completed_tasks[u] + 1
            if r.rejected:
                user_to_n_rejected_tasks[u] = user_to_n_rejected_tasks[u] + 1
            else:
                user_to_n_graded_tasks[u] = user_to_n_graded_tasks[u] + 1
    return user_to_n_completed_tasks, user_to_n_graded_tasks, user_to_n_rejected_tasks


def read_db_for_ranking_by_grades(venue_id):
    """ The method fills matrix D, vector delta_vec and other containers
    with infrom form the db.
    argument how_to_construct_compar defines how to construct binary
    comparisons out of M-ary comparisons.

    Method return tuple  (D, delta_vec, subm_id_to_user, user_to_bin_comp_idx_list, idx_to_subm_id, avrg_grades)
    where
       - subm_id_to_user is a dictionary submission id -> author of it.
       - user_to_bin_comp_idx_list is a dictionary: user -> list of binary
       comparison indexes [i, j ...], where i corresponds to i-th row of matrix D.
       - idx_to_subm_id is a dictionary: column index -> submission id which
       corresponds to the column.
       - avrg_grades is a vector of average grades such that i-th
       element of avrg_grades corresponds to i-th column of matrix D.
       - user_to_n_graded_tasks is a dictionary: user -> number of submission
       the user has graded.
       - user_to_grades_dict is dictionary mapping user to a dictionary with
       grades (submission id -> grade).
    """

    db = current.db
    logger = current.logger
    subm_id_to_list_of_grades = {}
    # Fetching number of completed, graded and rejected tasks per user.
    (user_to_n_completed_tasks, user_to_n_graded_tasks,
        user_to_n_rejected_tasks) = get_number_of_tasks(venue_id)
    # user_to_grades_dict id a dictionary mapping user to another dictionary:
    # submission id -> grade.
    user_to_grades_dict = {}
    # user_to_bin_comp_idx_list is a dictionary: user -> list of binary
    # comparison indexes [i, j ...], where i corresponds to i-th row of matrix D
    user_to_bin_comp_idx_list = {}
    rows = db(db.submission.venue_id == venue_id).select()
    subm_id_to_user = dict((r.id, r.user) for r in rows)
    rows = db((db.comparison.venue_id == venue_id) &
              (db.comparison.is_valid == True)).select()
    # subm_id_to_idx is a dictionary mapping submission id to
    # column index in matrix D.
    subm_id_to_idx = get_dict_subm_id_to_idx(rows)
    current.logger.info("subm_id_to_idx: %r" % subm_id_to_idx)
    idx_to_subm_id = dict((idx, subm_id) for (subm_id, idx) in
                                              subm_id_to_idx.iteritems())
    # Caluculate dimensions if D and length of delta_vec.
    num_rows = get_num_rows_of_D(rows)
    num_columns = len(subm_id_to_idx)
    current.logger.info("Size of D: %d columns, %d rows" % (num_columns, num_rows))
    D = np.zeros((num_rows, num_columns))
    delta_vec = np.zeros(num_rows)
    # Filling matrix D and delta_vec
    idx = 0
    for r in rows:
        # Note, that ordering is from Best to Worst.
        ordering = util.get_list(r.ordering)
        # Getting grades.
        subm_id_to_grade = decode_json_grades(r.grades)
        if len(subm_id_to_grade) > 1:
            user_to_grades_dict[r.user] = subm_id_to_grade
        # Filling matrix D and vector delta_vec.
        normaliz = 1.0
        if len(ordering) > 1:
            normaliz = float(subm_id_to_grade[ordering[0]] -
                             subm_id_to_grade[ordering[-1]])
        for i in xrange(len(ordering)):
            if not subm_id_to_idx.has_key(ordering[i]):
                continue
            for j in xrange(i + 1, len(ordering), 1):
                if not subm_id_to_idx.has_key(ordering[j]):
                    continue
                g_i = subm_id_to_grade[ordering[i]]
                g_j = subm_id_to_grade[ordering[j]]
                #TODO(michael): delete grades comparison later,
                # now it is for sanity check.
                if g_i < g_j:
                    raise Exception("Error, grades are in a wrong order!")
                idx_i = subm_id_to_idx[ordering[i]]
                idx_j = subm_id_to_idx[ordering[j]]
                D[idx, idx_i] = 1
                D[idx, idx_j] = -1
                # Normailzation.
                if current.normalize_grades:
                    delta_vec[idx] = (g_i - g_j) / normaliz
                    delta_vec[idx] *= current.normalization_scale
                else:
                    delta_vec[idx] = g_i - g_j
                if not user_to_bin_comp_idx_list.has_key(r.user):
                    user_to_bin_comp_idx_list[r.user] = []
                user_to_bin_comp_idx_list[r.user].append(idx)
                idx += 1
        # Okay, now lets remember grades which was assigned to submissions.
        for subm_id, grade in subm_id_to_grade.iteritems():
            if not subm_id_to_list_of_grades.has_key(subm_id):
                subm_id_to_list_of_grades[subm_id] = []
            subm_id_to_list_of_grades[subm_id].append(grade)
    # Compute vector of average grades which is synchronized with matrix D,
    # i.e. i-th row of D corresponds to i-th element of avrg_grades.
    avrg_grades = get_vector_of_average_grades(subm_id_to_list_of_grades,
                                               idx_to_subm_id)
    # Reading how many submission a reviewer is supposed to grade.
    venue_row = db(db.venue.id == venue_id).select().first()
    return (D, delta_vec, subm_id_to_user, user_to_bin_comp_idx_list,
            idx_to_subm_id, avrg_grades, user_to_n_graded_tasks,
            user_to_n_completed_tasks, user_to_grades_dict,
            venue_row)


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


def write_db_for_ranking_by_grades(venue_id,
                                   user_to_final_grade,
                                   user_to_final_grade_perc,
                                   user_to_subm_grade,
                                   user_to_subm_perc,
                                   user_to_review_grade,
                                   user_to_review_perc,
                                   user_to_rep,
                                   user_to_n_completed_tasks,
                                   publish, run_id):
    db = current.db
    logger = current.logger
    user_list = get_list_of_all_students(venue_id)
    if len(user_list) == 0:
        # Nothing to write.
        db((db.grades_exp.venue_id == venue_id) &
           (db.grades_exp.run_id == run_id)).delete()
    if not publish:
        for u in user_list:
            db.grades_exp.update_or_insert((db.grades_exp.venue_id == venue_id) &
                                           (db.grades_exp.user == u) &
                                           (db.grades_exp.run_id == run_id),
                                           venue_id = venue_id,
                                           user = u,
                                           run_id = run_id,
                                           subm_grade = user_to_subm_grade.get(u),
                                           subm_percent = user_to_subm_perc.get(u),
                                           review_grade = user_to_review_grade.get(u),
                                           review_percent = user_to_review_perc.get(u),
                                           n_ratings = user_to_n_completed_tasks.get(u),
                                           reputation = user_to_rep.get(u),
                                           grade = user_to_final_grade.get(u),
                                           )
    else:
        if len(user_list) == 0:
            # Nothing to write.
            db(db.grades.venue_id == venue_id).delete()
        for u in user_list:
            db.grades.update_or_insert((db.grades.venue_id == venue_id) &
                                       (db.grades.user == u),
                                       venue_id = venue_id,
                                       user = u,
                                       submission_grade = user_to_subm_grade.get(u),
                                       submission_percentile = user_to_subm_perc.get(u),
                                       accuracy = user_to_review_grade.get(u),
                                       accuracy_percentile = user_to_review_perc.get(u),
                                       reputation = user_to_rep.get(u),
                                       n_ratings = user_to_n_completed_tasks.get(u),
                                       percentile = user_to_final_grade_perc.get(u),
                                       grade = user_to_final_grade.get(u),
                                       )
        # Saving evaluation date.
        t = datetime.utcnow()
        db(db.venue.id == venue_id).update(latest_grades_date = t,
                                           ranking_algo_description=run_id)
    db.commit()


def compute_reputation(f, user_to_subm_perc, user_to_accuracy, 
                       user_to_bin_compar_idx_list, subm_id_to_user, idx_to_subm_id):
    """ Returns vectors r, rep_vec and a dictionary user -> reputation.
    - r is a vector such that author of i-th binary comparison (i-th row of
    matrix D) has accuracy r_i.
    - rep_vec is a vector such that rep_vec[i] is reputation of an author
    of a submission which corresponds to i-th column of matrix D.
    f is a vector, where each element is the cost of a binary comparison. 
    Let length of f is equal to the number of rows of D.
    """
    r = np.zeros(f.shape[0])
    user_to_rep = {}
    # Iterates over the comparisons of the user.
    for user, idx_list in user_to_bin_compar_idx_list.iteritems():
        mask = np.zeros(f.shape[0])
        # Selects which comparisons were made by the user.
        for idx in idx_list:
            mask[idx] = 1
        # Cost is the average cost of the comparisons made by the user.
        if current.reputation_method == 'cost':
            cost = current.prec_coefficient * np.sum(f * mask)
            user_to_rep[user] = 1.0 / (1 + cost)
        else:
            user_to_rep[user] = user_to_accuracy[user] ** current.prec_coefficient
        if current.use_submission_rank_in_rep:
            user_to_rep[user] *= (util.get_or_0(user_to_subm_perc, user) / 100.0) ** current.submission_rank_exp
        for idx in idx_list:
            r[idx] = user_to_rep[user]
    rep_vec = np.zeros(len(idx_to_subm_id))
    for i in xrange(rep_vec.shape[0]):
        user = subm_id_to_user[idx_to_subm_id[i]]
        rep_vec[i] = util.get_or_0(user_to_rep, user)
    return r, rep_vec, user_to_rep


def get_accuracy_using_stdev(subm_id_to_subm_grade, user_to_grades_dict,
                 user_to_bin_compar_idx_list, f, num_subm_per_reviewer,
                 accuracy_type="stdev1",
                 map_stdev_to_accuracy=lambda x, y, z: x):
    """ Returns vector r and a dictionary user -> accuracy.
    Vector r is such that author of i-th binary comparison (i-th row of
    matrix D) has accuracy r_i.
    Arguments:
        - f is a cost vector such that i-th binary comparison (g1 - g2)
        induce cost f[i].
        - accuracy_type can be
            "stedv1" - computes avrg(x_i - g_i)**2
            "stdev2" - computes avrg((x_i - avrg(x_i)) - (g_i - avrg(g_i)))**2
            "stdev3" - normalizes x and g (function normalize_vec) and
                then computes avrg(x_i - g_i)
            "stdev_diff" first normalizes x and g then computes s = stdev(x -g),
                final accuracy is max(0, 1 - s/sqrt(2)) * min(k, n)/k, where
                k - number of reviewes a user is supposed to do
                n - number of reviewes a user has graded
        - map_stdev_to_accuracy is a function which calculates accuracy based on user's stdev.
          map_stdev_to_accuracy(stedv, number_of_reviews)
    """
    user_to_accuracy = {}
    r = np.zeros(f.shape[0])
    for u, subm_id_to_grade in user_to_grades_dict.iteritems():
        # x is a vector of sumbission grades by our main algorithm.
        # g is a vector of sumbission grades by the user u.
        x = np.zeros(len(subm_id_to_grade))
        g = np.zeros(len(subm_id_to_grade))
        idx = 0
        for subm_id, grade in subm_id_to_grade.iteritems():
            x[idx] = grade
            g[idx] = subm_id_to_subm_grade[subm_id]
            idx += 1
        # Here we compute standard deviation between x and g.
        x_mean = np.mean(x)
        g_mean = np.mean(g)
        if accuracy_type == 'stdev1':
            stdev = np.mean((x - g)**2)
        elif accuracy_type == 'stdev2':
            stdev = np.mean(((x - x_mean) - (g - g_mean))**2)
        elif accuracy_type == 'stdev3':
            x_1 = normalize_vec(x)
            g_1 = normalize_vec(g)
            stdev = np.mean((x_1 - g_1)**2)
        elif accuracy_type == 'stdev_diff':
            x_1 = normalize_vec(x)
            g_1 = normalize_vec(g)
            s = np.std(x_1 - g_1)
            n = len(user_to_grades_dict[u])
            accuracy = (max(0.0, 1.0 - s / (2.0 ** 0.5)) * 
                        min(n, num_subm_per_reviewer) / float(num_subm_per_reviewer))
        else:
            raise Exception("Please specify how to compute accuracy")
        if accuracy_type in ['stdev1', 'stdev2', 'stdev3']:
            accuracy = map_stdev_to_accuracy(stdev, len(user_to_grades_dict[u]),
                                                    num_subm_per_reviewer)
        user_to_accuracy[u] = accuracy
        # Computing vector r
        for idx in user_to_bin_compar_idx_list[u]:
            r[idx] = user_to_accuracy[u]
    return r, user_to_accuracy


def get_accuracy_using_correlation(subm_id_to_subm_grade, user_to_grades_dict,
                 user_to_bin_compar_idx_list, f, num_subm_per_reviewer):
    """ Returns vector r and a dictionary user -> accuracy.
    Vector r is such that author of i-th binary comparison (i-th row of
    matrix D) has accuracy r_i.
    Arguments:
        - f is a cost vector such that i-th binary comparison (g1 - g2)
        induce cost f[i].
        - accuracy_type can be
            "stedv1" - computes avrg(x_i - g_i)**2
            "stdev2" - computes avrg((x_i - avrg(x_i)) - (g_i - avrg(g_i)))**2
            "stdev3" - normalizes x and g (function normalize_vec) and
                then computes avrg(x_i - g_i)
            "stdev_diff" first normalizes x and g then computes s = stdev(x -g),
                final accuracy is max(0, 1 - s/sqrt(2)) * min(k, n)/k, where
                k - number of reviewes a user is supposed to do
                n - number of reviewes a user has graded
    """
    user_to_accuracy = {}
    r = np.zeros(f.shape[0])
    for u, subm_id_to_grade in user_to_grades_dict.iteritems():
        # x is a vector of sumbission grades by our main algorithm.
        # g is a vector of sumbission grades by the user u.
        x = np.zeros(len(subm_id_to_grade))
        g = np.zeros(len(subm_id_to_grade))
        idx = 0
        for subm_id, grade in subm_id_to_grade.iteritems():
            x[idx] = grade
            g[idx] = subm_id_to_subm_grade[subm_id]
            idx += 1
        # Here we compute the correlation between x and g.
        corr = max(0.0, np.corrcoef(x, g)[0, 1])
        n = len(user_to_grades_dict[u])
        accuracy = max(0.0, corr * min(n, num_subm_per_reviewer) / float(num_subm_per_reviewer))
        user_to_accuracy[u] = accuracy
        # Computing vector r
        for idx in user_to_bin_compar_idx_list[u]:
            r[idx] = user_to_accuracy[u]
    return r, user_to_accuracy


def stretch_grades(x, g, rep_vec=None):
    """ The method returns vector y, such that y_i = ax_i + b, where
    a, b = argmin rep_vec_i * (sum_i ax_i + b - g_i) ** 2.
    Arguments:
        - x is a vector of \"true\" grades of submisssions.
        - g is a vector such that g_i is average grade assigned to submission i.
        - rep_vec is vector with user's reputation.
    """
    threshold = 0.1
    if rep_vec is None:
        rep_vec = np.zeros(len(x)) + 1
    rsum = float(np.sum(rep_vec))
    a = rsum * np.sum(x * g * rep_vec) - np.sum(x * rep_vec) * np.sum(g * rep_vec)
    a = a / (rsum * np.sum (x **2 * rep_vec) - np.sum(x * rep_vec) ** 2)
    a = max(threshold, a)
    b = (-a * np.sum(x * rep_vec) + np.sum(g * rep_vec)) / rsum
    current.logger.info("Variable a in stretching function is %r" % a)
    return a * x + b


def get_dict_subm_id_to_subm_grade(grades_vec, idx_to_subm_id):
    subm_id_to_grade = {}
    for idx in xrange(len(grades_vec)):
        subm_id_to_grade[idx_to_subm_id[idx]] = grades_vec[idx]
    return subm_id_to_grade


def compute_percentile(user_to_grade):
    """ Method returns a dictionary user -> percentile given a dictionary
    user -> grade."""
    # Computes the grade percentiles.
    l = []
    for u, g in user_to_grade.iteritems():
        l.append((u, g))
    sorted_l = sorted(l, key = lambda x: x[1], reverse=True)
    user_to_perc = {}
    n_users = float(len(sorted_l))
    for i, el in enumerate(sorted_l):
        user_to_perc[el[0]] = 100.0 * (n_users - float(i)) / n_users
    return user_to_perc


def compute_final_grades(user_to_subm_grade, user_to_accuracy):
    """ Computes final grade of users as a combination of grade of a submission
    and reviewer accuracy."""
    user_to_final_grade = {}
    user_list = util.union_list(user_to_subm_grade.keys(),
                                user_to_accuracy.keys())
    for u in user_list:
        grade = util.get_or_0(user_to_subm_grade, u) * (100 - current.review_percentage) / 100.0
        grade += current.MAX_GRADE * util.get_or_0(user_to_accuracy, u) * current.review_percentage / 100.0
        user_to_final_grade[u] = grade
    return user_to_final_grade


def rank_by_grades(venue_id, run_id='exp', publish=False):
    """ Ranking with grades by minimizing global cost function.
    Argumetns:
        - current.num_iterations - number of iterations in the reputaion system.
        - run_id - will be written to the field db.grades_exp.run_id
        - publish is a flag whether we should write result to db.grades or not.
        - normalize is a boolean whether we need to normalize difference between
        grades or not.
        - normalization_scale is a number to which we normalize difference between grades.
    """
    db = current.db
    logger = current.logger
    logger.info("Computation of Crowdgrades has started.")
    (D, delta_vec, subm_id_to_user, user_to_bin_compar_idx_list, idx_to_subm_id,
        avrg_grades, user_to_n_graded_tasks, user_to_n_completed_tasks,
        user_to_grades_dict, venue_row) = read_db_for_ranking_by_grades(venue_id)
    if D.shape[0] == 0:
        # There are no comparisons in the db.
        logger.info("There are no comparisons in the db.")
        return
    objective = MinimizationObjective(D, delta_vec)
    num_compar, num_sumb = D.shape
    x_optimal = np.zeros(num_sumb) + 1
    r = np.zeros(num_compar) + 1
    for it in xrange(current.num_iterations):
        x_0 = x_optimal.copy()
        q = objective.get_Q(r)
        grad_q = objective.get_grad_Q(r)
        x_optimal = convopt.get_argmin(x_0, q, grad_q)
        # Stretching optimal x, minimizing the total square distance between grades given by 
        # students, and computed by the system.
        x_stretched = stretch_grades(x_optimal, avrg_grades)
        # Computing user's accuracy.
        subm_id_to_subm_grade = get_dict_subm_id_to_subm_grade(x_stretched,
                                                               idx_to_subm_id)
        subm_id_to_subm_percentile = compute_percentile(subm_id_to_subm_grade)
        f = objective.compute_f(x_optimal)

        # Computes a mapping from each user to the grade, and the percentile.
        user_to_subm_grade = {}
        for idx, subm_id in idx_to_subm_id.iteritems():
            user = subm_id_to_user[subm_id]
            user_to_subm_grade[user] = x_stretched[idx]
        user_to_subm_perc = compute_percentile(user_to_subm_grade)

        # We compute both accuracy, and reputation.  We can experiment with which one
        # is most helpful for the ranking.
        accuracy, user_to_accuracy = get_accuracy_using_correlation(
                                                subm_id_to_subm_grade,
                                                user_to_grades_dict,
                                                user_to_bin_compar_idx_list,
                                                f,
                                                venue_row.number_of_submissions_per_reviewer)
        r, _ , user_to_rep = compute_reputation(
            f, user_to_subm_perc, user_to_accuracy,
            user_to_bin_compar_idx_list, subm_id_to_user, idx_to_subm_id)
        current.logger.info("Completed iteration %d" % it)
    # Okay, now we build dictionaries for writing to the db.
    user_to_accuracy_perc = compute_percentile(user_to_accuracy)
    user_to_final_grade = compute_final_grades(user_to_subm_grade, user_to_accuracy)
    user_to_final_grade_perc = compute_percentile(user_to_final_grade)
    # Writting to the db.
    logger.info("Writing Crowdgrades to the db.")
    write_db_for_ranking_by_grades(venue_id, user_to_final_grade,
                                         user_to_final_grade_perc,
                                         user_to_subm_grade,
                                         user_to_subm_perc,
                                         user_to_accuracy,
                                         user_to_accuracy_perc,
                                         user_to_rep,
                                         user_to_n_completed_tasks,
                                         publish, run_id)


def map_stdev_to_accuracy(stdev, num_compar, num_subm_per_reviewer):
    """ Calculates reviewer accuracy based on standard deviation of grades.
    num_compar is number of submission a user has reviewed.
    """
    accuracy = 1.0 / (1 + stdev/np.sqrt(min(num_compar, num_subm_per_reviewer)))
    return accuracy

def normalize_vec(vec):
    vec_1 = vec - np.mean(vec)
    vec_1 = vec_1 / np.std(vec_1)
    return vec_1


def get_accuracy_using_dirichlet(f, user_to_bin_compar_idx_list):
    perc = 0.9
    user_to_accuracy = {}
    r = np.zeros(f.shape[0])
    for u in user_to_bin_compar_idx_list:
        alpha, beta = 0.01, 0.01
        delta = 0.001
        x = np.arange(0 + delta, 1, delta)
        y = x ** (alpha - 1) * (1 - x) ** (beta - 1)
        # Updating distribution.
        for idx in user_to_bin_compar_idx_list[u]:
            c = 1.0 / (1 + f[idx])
            y = y * (c * x + (1 - c) * (1 - x))
            y /= np.sum(y)
        # Computing 90 percentile.
        # Integral approximation is based on trapezoidal rule.
        y1 = y[:-1]
        y2 = y[1:]
        integral_vec = (y2 + y1) / 2 * delta
        integral = np.sum(integral_vec)
        cumsum = np.cumsum(integral_vec)
        threshold = (1 - perc) * integral
        idx = cumsum.searchsorted(threshold)
        accuracy = idx * delta
        user_to_accuracy[u] = accuracy
        # Computing vector r
        for idx in user_to_bin_compar_idx_list[u]:
            r[idx] = accuracy
    return r, user_to_accuracy
