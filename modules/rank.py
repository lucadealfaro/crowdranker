# -*- coding: utf-8 -*-

import numpy as np
import random
#import matplotlib.pyplot as plt
import time
import math

class Cost:
    """ Class contains cost function.
    """
    def __init__(self, cost_type='top-k', rank_cost_coefficient=-1):
        self.cost_type = cost_type
        self.rank_cost_coefficient = rank_cost_coefficient

    def calculate(self, i, k, id2rank):
        # ranking starts from 0, so first k rank are 0, 1, ..., k - 1
        if self.cost_type == 'top-k':
            if id2rank[i] < k:
                return 1
            else:
                return 0
        elif self.cost_type == 'one_over_rank':
            return  1./( 1 + id2rank[i])
        elif self.cost_type == 'rank_power_alpha':
            if self.rank_cost_coefficient == 0:
                raise Exception("If coefficient is zero then cost object should be None!")
            return (1 + id2rank[i]) ** self.rank_cost_coefficient
        elif self.cost_type == 'two_steps':
            if id2rank[i] < k:
                return 1
            if id2rank[i] < 3 * k / 2:
                return 0.5
            return 0
        elif self.cost_type == 'piecewise':
            a = 0.25
            x = id2rank[i]
            if x < k:
                return (-1) * a / k * x + 1 + a
            if x < 2 * k:
                return - 1. / k * x + 2
            return 0
        elif self.cost_type == 'smooth-top-k':
            beta = 2
            return 1.0 / (1 + (id2rank[i]/float(k)) ** beta)
        else:
            raise Exception('Cost funtion type is not specified')


class Rank:
    """ Class contains methods for ranking items based on items comparison.
    """
    def __init__(self, items, alpha=0.9, num_bins=2001,
                 cost_obj=None, k=None, init_dist_type='gauss'):
        """
        Arguments:
            - items is a list of original items id.
              function. If cost_obj is None then we don't use any
              reward function and treat each item equally.
            - alpha is the annealing coefficient for distribution update.
            - num_bins is the number of histogram bins.
            - cost_obj is an object of type Cost, in other words it is reward
            - init_distr_type is type of ditribution we use for initialization
              quality distributions
        """
        # items are indexed by 0, 1, ..., num_items - 1 in the class but
        # "outside" they have ids from orig_items_id, so orig_items_id[n]
        # is original id of item n.
        self.orig_items_id = items
        num_items = len(items)
        self.num_items = num_items
        self.num_bins = num_bins
        self.cost_obj = cost_obj
        self.alpha = alpha
        # Constant k is for top-k problems.
        self.k = k
        # qdistr is numpy two dimensional array which represents quality
        # distribution, i-th row is a distribution for an item with id equals i.
        # qdistr is initialized as uniform distribution.
        if init_dist_type == 'unif':
            self.qdistr = np.zeros((num_items ,num_bins)) + 1./num_bins
        elif init_dist_type == 'gauss':
            # Does a Gaussian distribution centered in the center.
            #print num_items, num_bins
            x, y = np.mgrid[0:num_items, 0:num_bins]
            self.qdistr = np.zeros((self.num_items, self.num_bins))
            for i in xrange(self.num_items):
                self.qdistr[i, :] = self.get_normal_vector(self.num_bins,
                                                        self.num_bins / 2,
                                                        self.num_bins / 8)
            #self.qdistr = scipy.stats.distributions.norm.pdf(y, loc=num_bins / 2, scale = num_bins / 8)

            # Normalization.
            #self.qdistr = self.qdistr / np.sum(self.qdistr, 1) [:, np.newaxis]
            self.qdistr_init = self.qdistr.copy()
            # Plotting, for testing.
            #plt.plot(self.qdistr[0, :])
            #plt.draw()
            #time.sleep(2)
            #plt.close('all')

        self.rank2id, self.id2rank = self.compute_ranks(self.qdistr)
        # generate true items quality and rank
        self.generate_true_items_quality()
        self.rank2id_true, self.id2rank_true = \
                                            self.compute_ranks(self.qdistr_true)
        # Computing true quality vector; quality_true[i] is true quality
        # of item i.
        #self.quality_true = self.avg(self.qdistr_true)
        self.quality_true = self.num_items - self.id2rank_true

    @classmethod
    def from_qdistr_param(cls, items, qdistr_param, alpha=0.6,
                         num_bins=2001, cost_obj=None):
        """ Alternative constructor for creating rank object
        from quality distributions parameters.
        Arguments are the same like in __init__ method but qdistr_param
        is a list with mean and stdev for each item such that qdistr_param[2*i]
        and qdistr[2*i + 1] are mean and stdev for items[i].
        """
        result = cls(items, alpha, num_bins, cost_obj,
                     k=None, init_dist_type='gauss')
        result.restore_qdistr_from_parameters(qdistr_param)
        return result

    def get_normal_vector(self, num_bins, average, stdev):
        x_array = np.arange(num_bins)
        dist = x_array - average
        # In literature sigma is standard deviation and sigma**2 is variance.
        d = np.exp(-dist * dist / (2.0 * stdev * stdev))
        d = d / np.sum(d)
        return d

    #def plot_distributions(self, hold=False, **kwargs):
    #    plt.clf()
    #    for i in range(self.num_items):
    #        plt.plot(self.qdistr[i, :])
    #    #plt.title(self.get_title_for_plot(**kwargs))
    #    if hold:
    #        plt.show()
    #    else:
    #        plt.ioff()
    #        plt.draw()
    #    time.sleep(.3)

    #def get_title_for_plot(self, **kwargs):
    #    result = ''
    #    for key in kwargs:
    #        result += '%s %s, ' % (key, kwargs[key])
    #    result += 'raking error %s %%, ' % self.get_ranking_error()
    #    result += 'quality metric %s ' % self.get_quality_metric()
    #    return result


    def generate_true_items_quality(self):
        identity = np.eye(self.num_items)
        zeros = np.zeros((self.num_items, self.num_bins - self.num_items))
        self.qdistr_true = np.hstack((identity, zeros))


    def compute_ranks(self, quality_distr):
        """ Returns two vectors: id2rank and rank2id.
        id2rank[i] is a rank of an item with id i.
        rank2id[i] is an id of an item with rank i.
        """
        avg = self.avg(quality_distr)
        rank2id = avg.argsort()[::-1]
        id2rank = rank2id.argsort()
        return rank2id, id2rank

    def compute_percentile(self):
        # Rank is from 0, 1, ..., num_items - 1
        val = 100 / float(self.num_items)
        id2percentile = {}
        for idx in xrange(self.num_items):
            id2percentile[idx] = val * (self.num_items - self.id2rank[idx])
        return id2percentile

    def avg(self, quality_distr):
        """ returns vector v with average qualities for each item.
        v[i] is the average quality of the item with id i.
        """
        # grid_b is a matrix consisting of vertically stacked vector
        # (0, 1, ..., num_bins - 1)
        grid_b, _ = np.meshgrid(np.arange(self.num_bins),
                                     np.arange(self.num_items))
        # Actually values are from 1 to num_bins.
        grid_b = grid_b + 1
        # avg[i] is expected value of quality distribution for item with id i.
        avg = np.sum(quality_distr * grid_b, 1)
        return avg


    def update(self, sorted_items, new_item=None, alpha_annealing=None, 
               annealing_type='before_normalization_uniform'):
        """ Main update function.
        Given sorted_items and new_item it updates quality distributions and
        items ranks.
        Method returns dictionary d such that d['sumbission id'] is a list
        [percentile, average, stdev], i.e. percentile of the submission,
        average and stdev of quaility distribution of it.

        If alpha_annealing is None then we use old self.alpha otherwise we
        set self.alpha to alpha_annealing.

        Arguments:
            - sorted_items is a list of items sorted by user such that
            rank(sorted_items[i]) > rank(sorted_items[j]) for i < j
            (Worst to Best)

            - new_item is an id of a submission from sorted_items which was new
            to the user. If sorted_items contains only two elements then
            new_item is None.

            - annealing_type (see n_comparisons_update method) is whether
            'before_normalization_uniform' or
            'before_normalization_gauss' or
            'after_normalization'
        """
        # Setting new annealing coefficient.
        alpha_old = None
        if not alpha_annealing is None:
            alpha_old = self.alpha
            self.alpha = alpha_annealing
        # Obtaining ordering in terms of internal ids.
        sorted_ids = [self.orig_items_id.index(x) for x in sorted_items]
        self.n_comparisons_update(sorted_ids, annealing_type)
        id2percentile = self.compute_percentile()
        qdistr_param = self.get_qdistr_parameters()
        result = {}
        for idx in xrange(self.num_items):
            avrg = qdistr_param[2 * idx]
            stdev = qdistr_param[2 * idx + 1]
            result[self.orig_items_id[idx]] = (id2percentile[idx], avrg, stdev)
        # Setting old alpha back.
        if not alpha_old is None:
            self.alpha = alpha_old
        return result


    def get_ranking_error_inthe_end_of_round(self, num_items_to_compare):
        """
        TODO(michael): As for now this method is not in use.
                       Write method to return error which is
                       interpretable in terms of ranking.

        Method returns ranking error in the end of contest round.
        Each contest consists of rounds. On the first round users compare 2
        submissions, on the second round users compare 3 submsissions, etc.

        Because we don't know true quality of submissions then we need to make
        assumptions about how noisy will be users and return errors based on
        experiments.
        """
        # Current assumption is that 5% of users will sort submission randomly
        # (so 3 students out of 60 will order randomly).
        # Another assumption is that each user is gaussian user with stdev
        # equals 2 and any two heighbor submissions have distance 1 in quality.
        # In experiments with above settings I measured average(avrg_rank_error)
        # and stdev (stdev_rank_error) of ranking error
        # (ranking error of item i is |rank(i) - true_rank(i)|).
        #
        # Method returns ranking error as avrg_rank_error + 2 * stdev_rank_error
        if num_items_to_compare == 2: # First round.
            avrg_rank_error = 10.9
            stdev_rank_error = 8.8
        elif num_items_to_compare == 3: # Second round.
            avrg_rank_error = 6.6
            stdev_rank_error = 6
        elif num_items_to_compare == 4: # Third round.
            avrg_rank_error = 3.6
            stdev_rank_error = 3.6
        elif num_items_to_compare == 5: # Fourth round.
            avrg_rank_error = 2.1
            stdev_rank_error = 2.1
        elif num_items_to_compare == 6: # Fifth round.
            avrg_rank_error = 1.4
            stdev_rank_error = 1.3
        elif num_items_to_compare == 7: # Round number six.
            avrg_rank_error = 1.2
            stdev_rank_error = 1.1
        elif num_items_to_compare == 8: # Round number seven.
            avrg_rank_error = 1
            stdev_rank_error = 1
        else:
            return None
        return avrg_rank_error + 2 * stdev_rank_error


    def n_comparisons_update(self, descend_list,
                             annealing_type='before_normalization_uniform'):
        """ Updates quality distributions given n ordered items.
        Item id is from set {0, 1, ..., num_items - 1}
        Bins are 0, 1, ..., num_bins - 1

        descend_list is a list of id's such that
        rank(descend_list[i]) > rank(descend_list[j]) if i < j
        (Worst to Best)

        annealing type
            - 'after_normalization' is self explanatory
            - 'before_normalization_uniform' is using by default, it works
            best in presence of users who gave random ordering.
            - 'before_normalization_gauss' works best in presence of gaussian
            users (users who can swap similar items).
        """
        n = len(descend_list)
        factorial = math.factorial(n)
        # Let's denote quality of element descend_list[i] as zi, then
        # z0 < z1 < ... < z(n-1) where n is length of descend_list.

        # v[0, x] = Pr(x < z(n-1))
        # v[1, x] = Pr(x < z(n-2) < z(n-1))
        # v[i, x] = Pr(x < z(n-1-i) < ... < z(n-1))
        # v[n-2, x] = Pr(x < z1 < ... < z(n-1))
        v = np.zeros((n - 1, self.num_bins))
        q = self.qdistr[descend_list[n-1], :]
        v[0,:] = 1 - np.cumsum(q)

        # w[0, x] = Pr(z0 < x)
        # w[1, x] = Pr(z0 < z1 < x)
        # w[i, x] = Pr(z0 < z1 < ... < z(i) < x)
        # w[n-2, x] = Pr(z0 < z1 < ... < z(n-2) < x)
        w = np.zeros((n - 1, self.num_bins))
        q = self.qdistr[descend_list[0], :]
        w[0,:] = np.cumsum(q) - q

        # Filling v and w.
        for idx in xrange(1, n - 1, 1):
            # Matrix v.
            # Calculating v[idx,:] given v[idx-1,:].
            t = self.qdistr[descend_list[n - 1 - idx], :] * v[idx - 1, :]
            t = t[::-1]
            t = np.cumsum(t)
            # Shift.
            t = self.shift_vector(t)
            v[idx,:] = t[::-1]

            # Matrix w.
            # Calculating w[idx,:] given w[idx-1,:].
            t = self.qdistr[descend_list[idx], :] * w[idx - 1, :]
            t = np.cumsum(t)
            t = self.shift_vector(t)
            w[idx,:] = t
        # Updating distributions.
        # Update first distributions.
        idx = descend_list[0]
        q = self.qdistr[idx,:]
        q_prime = q * v[-1, :]
        # Annealing.
        if annealing_type == 'before_normalization_uniform':
            self.qdistr[idx,:] = (1.0/factorial) * (1 - self.alpha) * q + \
                                                               self.alpha * q_prime
            self.qdistr[idx,:] = self.qdistr[idx,:] / np.sum(self.qdistr[idx,:])
        elif annealing_type == 'after_normalization':
            q_prime = q_prime / np.sum(q_prime)
            self.qdistr[idx,:] = (1 - self.alpha) * q + self.alpha * q_prime
        elif annealing_type == 'before_normalization_gauss':
            ww = v[-1, :]
            self.qdistr[idx,:] = (1 - self.alpha) * q *(1 - ww) + \
                                      self.alpha * q * ww
            self.qdistr[idx,:] = self.qdistr[idx,:] / np.sum(self.qdistr[idx,:])
        else:
            # Should not happen.
            raise Exception("Error: annealing type is not known.")
        # Update last distributions.
        idx = descend_list[-1]
        q = self.qdistr[idx,:]
        q_prime = q * w[-1, :]
        # Annealing.
        if annealing_type == 'before_normalization_uniform':
            self.qdistr[idx,:] = (1.0/factorial) * (1 - self.alpha) * q + \
                                                               self.alpha * q_prime
            self.qdistr[idx,:] = self.qdistr[idx,:] / np.sum(self.qdistr[idx,:])
        elif annealing_type == 'after_normalization':
            q_prime = q_prime / np.sum(q_prime)
            self.qdistr[idx,:] = (1 - self.alpha) * q + self.alpha * q_prime
        elif annealing_type == 'before_normalization_gauss':
            ww = w[-1, :]
            self.qdistr[idx,:] = (1 - self.alpha) * q *(1 - ww) + \
                                      self.alpha * q * ww
            self.qdistr[idx,:] = self.qdistr[idx,:] / np.sum(self.qdistr[idx,:])
        else:
            # Should not happen.
            raise Exception("Error: annealing type is not known.")

        # Update the rest of distributions.
        for i in range(1, n - 1, 1):
            idx = descend_list[i]
            q = self.qdistr[idx,:]
            q_prime = q * w[i - 1, :] * v[-(i+1), :]
            # Annealing.
            if annealing_type == 'before_normalization_uniform':
                self.qdistr[idx,:] = (1.0/factorial) * (1 - self.alpha) * q + \
                                                               self.alpha * q_prime
                self.qdistr[idx,:] = self.qdistr[idx,:] / np.sum(self.qdistr[idx,:])
            elif annealing_type == 'after_normalization':
                q_prime = q_prime / np.sum(q_prime)
                self.qdistr[idx,:] = (1 - self.alpha) * q + self.alpha * q_prime
            elif annealing_type == 'before_normalization_gauss':
                ww = w[i - 1, :] * v[-(i+1), :]
                self.qdistr[idx,:] = (1 - self.alpha) * q *(1 - ww) + \
                                          self.alpha * q * ww
                self.qdistr[idx,:] = self.qdistr[idx,:] / np.sum(self.qdistr[idx,:])
            else:
                # Should not happen.
                raise Exception("Error: annealing type is not known.")

        # Update id2rank and rank2id vectors.
        self.rank2id, self.id2rank = self.compute_ranks(self.qdistr)

    def sample(self, black_items=None):
        """ Returns two items to compare. If there is no two items to sample
        from then None is returned.
        Sampling by loss-driven comparison algorithm.
        black_items cannot be sampled.
        """
        indices = range(self.num_items)
        if (not black_items == None) and (not len(black_items) == 0):
            indices = [x for x in indices if not x in black_items]
        if len(indices) < 2:
            return None
        # l is len(indices)^2 array; l[idx] is expected loss of for items with ids
        # idx/len(indices) and idx%len(indices)
        l = np.zeros(len(indices) ** 2)
        for i in xrange(len(indices)):
            for j in xrange(len(indices)):
                    # We are choosing pairs (i, j) such that p(i) < p(j)
                    ii = indices[i]
                    jj = indices[j]
                    if self.id2rank[ii] < self.id2rank[jj]:
                        l[i * len(indices) + j] = self.get_expected_loss(ii, jj)
                    else:
                        l[i * len(indices) + j] = 0
        # normalization
        l /= l.sum()

        # randomly choosing a pair
        cs = l.cumsum()
        rn = np.random.uniform()
        idx = cs.searchsorted(rn)
        i, j = idx/len(indices), idx%len(indices)
        # sanity check
        ii = indices[i]
        jj = indices[j]
        if self.id2rank[ii] >= self.id2rank[jj]:
            raise Exception('There is an error in sampling!')
        return ii, jj

    def sample_n_items(self, n):
        items = set()
        while True:
            i,j = self.sample()
            items.add(i)
            items.add(j)
            if len(items) == n:
                return list(items)
            if len(items) > n:
                items.remove(i if random.random() < 0.5 else j)
                return list(items)

    def sample_item(self, old_items, black_items=None, sample_one=True ):
        """ Method samples an item given items the user received before.
        If sample_one is true then if old_items is None or empty then method
        returns one item, otherwise it returns two itmes.
        black_items is a list with items which should not be sampled.
        If it is impossible to sample an item then None is returned.
        """
        if black_items == None:
            black_items = []
        if old_items == None or len(old_items) == 0:
            if len(black_items) == 0:
                l = self.sample()
            else:
                ids = [self.orig_items_id.index(x) for x in black_items]
                l = self.sample(ids)
            # If we need two elements.
            if not sample_one:
                if l == None:
                    return None
                return [self.orig_items_id[x] for x in l]
            # We need only one element.
            if not l is None:
                return self.orig_items_id[l[0]] if random.random() < 0.5 else\
                            self.orig_items_id[l[1]]
            # We cannot sample two items, try to sample only one.
            if len(black_items) == len(self.orig_items_id):
                return None
            if len(self.orig_items_id) == 0:
                return None
            item = [x for x in self.orig_items_id if not x in black_items]
            return item[0]

        taken_ids = [idx for idx in range(self.num_items) if \
                        self.orig_items_id[idx] in old_items]
        free_ids = [idx for idx in range(self.num_items) if \
                        (not self.orig_items_id[idx] in old_items and
                         not self.orig_items_id[idx] in black_items)]
        # If there are no items to pick from then return None.
        if len(free_ids) == 0:
            return None
        # l[idx] is expected loss of for items with ids
        # idx/len(taken_ids) and idx%len(taken_ids)
        l = np.zeros(len(taken_ids) * len(free_ids))
        for i in xrange(len(taken_ids)):
            for j in xrange(len(free_ids)):
                    ii = taken_ids[i]
                    jj = free_ids[j]
                    if self.id2rank[ii] < self.id2rank[jj]:
                        l[i * len(free_ids) + j] = self.get_expected_loss(ii, jj)
                    else:
                        l[i * len(free_ids) + j] = self.get_expected_loss(jj, ii)
        # normalization
        #print l
        l /= l.sum()

        # randomly choosing a pair
        cs = l.cumsum()
        rn = np.random.uniform()
        idx = cs.searchsorted(rn)
        i, j = idx/len(free_ids), idx%len(free_ids)
        ii = taken_ids[i]
        jj = free_ids[j]
        # sanity check
        #if self.id2rank[ii] >= self.id2rank[jj]:
        #    raise Exception('There is an error in sampling!')
        return self.orig_items_id[jj]

    def shift_vector(self, vec):
        """ Shifts vector one position right filling the most left element
        with zero.
        """
        vec[1:] = vec[:-1]
        vec[0] = 0
        return vec

    def get_expected_loss(self, i, j):
        """ Calculate expected loss l(i, j) between items i and j.
        It is implied that r(i) < r(j).
        """
        if self.cost_obj == None:
            return self.get_missrank_prob(i, j)
        c_i = self.get_cost(i, self.k, self.id2rank)
        c_j = self.get_cost(j, self.k, self.id2rank)
        #return abs(c_i + c_j - c_i * c_j) * self.get_missrank_prob(i, j)
        return abs(c_i - c_j) * self.get_missrank_prob(i, j)

    def get_cost(self, i, k, id2rank):
        return self.cost_obj.calculate(i, k, id2rank)

    def get_missrank_prob(self, i, k):
        """ Method returns probability that r(i) > r(k) where r(i) is a rank
        of an item with id i.
        """
        q_k = self.qdistr[k, :]
        Q_i = np.cumsum(self.qdistr[i, :])
        prob = np.dot(q_k, Q_i)
        return prob

    def get_quality_metric(self):
        """ Returns quality metric for current quality distribution
        for top-k problem.
        """
        q_true = np.sum(self.quality_true[self.rank2id_true[0:self.k]])
        q_alg = np.sum(self.quality_true[self.rank2id[0:self.k]])
        val = (q_true - q_alg) / float(self.k)
        return val

    def get_ranking_error(self):
        """ Get ranking error, i.e. ratio of number of items which wrongly
        have rank less than k to the constant k.
        """
        counter = 0
        for idx in xrange(self.num_items):
            if self.id2rank_true[idx] >= self.k and self.id2rank[idx] < self.k:
                counter += 1
        return 100 * float(counter)/self.k

    def get_qdistr_parameters(self):
        """ Method returns array w such that w[2*i], w[2*i+1] are mean and
        standard deviation of quality distribution of item i (self.qdist[i])
        """
        w = np.zeros(2 * self.num_items)
        val = range(self.num_bins)
        for i in xrange(self.num_items):
            p = self.qdistr[i,:]
            w[2 * i] = np.sum(p * val)
            w[2 * i + 1] = np.sqrt(np.sum(p * (val - w[2 * i]) ** 2))
        return w

    def restore_qdistr_from_parameters(self, w):
        """ Method restores quality distributions from array w returned by
        get_qdistr_parameters: w such that w[2*i], w[2*i+1] are mean and
        standard deviation of quality distribution of item i
        """
        self.qdist = np.zeros((self.num_items, self.num_bins))
        y = range(self.num_bins)
        for i in xrange(self.num_items):
            mean = w[2 * i]
            std = w[2 * i + 1]
            self.qdistr[i, :] = self.get_normal_vector(self.num_bins, mean, std)
            #self.qdistr[i,:] = scipy.stats.distributions.norm.pdf(y, loc=mean,
            #                                                    scale=std)
            if np.sum(self.qdistr[i,:]) == 0:
                print 'ERROR, sum should not be zero !!!'
        # Normalization.
        #self.qdistr = self.qdistr / np.sum(self.qdistr, 1) [:, np.newaxis]

    def evaluate_ordering(self, ordering):
        """ rank(oredring[i]) > rank(ordering[j]) for i < j
        (Worst to Best)
        Function, returns average probability of error.
        """
        n = len(ordering)
        if n <= 1:
            return 0
        # Below ordering is evaluated using "incremental" way.
        # Incremental type of ordering evaluation is when for each
        # entity e in ordering (starting from 2nd one) we compute
        # error_e = 1 - 2*max(Pr(error)) and total evaluation is
        # a sum of all error_e.
        # max(Pr(error)) is a maxmum error that the user made when comparing
        # entity e.
        val = 0.0
        for i in xrange(0, n, 1):
            ii = self.orig_items_id.index(ordering[i])
            l1 = [self.get_missrank_prob(self.orig_items_id.index(ordering[j]),
                                               ii) for j in xrange(i + 1, n, 1)]
            l2 = [self.get_missrank_prob(ii,
                   self.orig_items_id.index(ordering[j])) for j in xrange(0, i, 1)]
            #pr_error = 0
            #if len(l1) != 0:
            #    pr_error = max(l1)
            #if len(l2) != 0:
            #    pr_error = max([max(l2), pr_error])
            #val += 1 - 2 * pr_error
            l1.extend(l2)
            if len(l1) == 0:
                continue
            val += 1 - np.mean(l1)
        return val

    def evaluate_ordering_using_dirichlet(self, ordering):
        """ rank(oredring[i]) > rank(ordering[j]) for i < j
        (Worst to Best).
        """
        if len(ordering) <= 1:
            return 0
        # alpha is a number of "Truth"
        # beta is a number of "False"
        alpha, beta = 0.01, 0.01
        for i in xrange(len(ordering)):
            for j in xrange(i + 1, len(ordering), 1):
                item_i = self.orig_items_id.index(ordering[i])
                item_j = self.orig_items_id.index(ordering[j])
                # q is a probability that comparison is True
                #q = 1 - self.get_missrank_prob(item_i, item_j)
                q = 1 - self.get_missrank_prob(item_j, item_i)
                # Update alpha and beta.
                if q > 0.5:
                    alpha += 2 * (q - 0.5)
                else:
                    beta += 2 * (0.5 - q)
        # Okay, alpha and beta are computed.
        # Let's q is a probability that user says True.
        # The quality of the ordering is 90-th percentile, so we need to compute it.
        perc = 0.9
        # First, numerically compute unnormalised probability mass function of q
        delta = 0.001
        x = np.arange(0 + delta, 1, delta)
        #print 'alpha', alpha
        #print 'beta', beta
        y = x ** (alpha - 1) * (1 - x) ** (beta - 1)
        # Integral approximation based on trapezoidal rule.
        y1 = y[:-1]
        y2 = y[1:]
        integral_vec = (y2 + y1) / 2 * delta
        integral = np.sum(integral_vec)
        cumsum = np.cumsum(integral_vec)
        threshold = (1 - perc) * integral
        idx = cumsum.searchsorted(threshold)
        val = idx * delta
        return val

    def sort_items_truthfully(self, items):
        """ Method is for testing purposes.
        It simulates sorting by a truthful user.
        Returns sorted list of items so rank(result[i]) > rank(result[j])
        if i > j.
        #TODO(michael): check this function in case of use
        """
        items_ids = [idx for idx in range(self.num_items) if \
                        self.orig_items_id[idx] in items]
        values = np.array(self.quality_true)[items_ids]
        idx = np.argsort(values)
        return [self.orig_items_id[x] for x in np.array(items_ids)[idx]]

    def get_quality_of_order(self, qual_type='avrg_rank_error'):
        """ Method calculates quality of current order of items.
        (essentially it should be not quality but error)

        quality types:
            inversions - calculates normalized number of inversions.
            avrg_rank_error - is average of |rank(i) - true_rank(i)| over all
                              items.
            stdev_rank_error - standard deviation of |rank(i) - true_rank(i)|
        """
        if qual_type == 'inversions':
            seq = self.id2rank.argsort()
            seq = [self.id2rank_true[x] for x in seq]
            _, num_inv = self._sort_and_get_inv_num(seq)
            return 2.0 * num_inv / len(seq) / (len(seq) - 1)
        elif qual_type == 'avrg_rank_error':
            seq = np.abs(self.id2rank_true - self.id2rank)
            return np.mean(seq)
        elif qual_type == 'stdev_rank_error':
            seq = np.abs(self.id2rank_true - self.id2rank)
            return np.std(seq)
        else:
            raise Exception("Quality type is unknown!")


    def _sort_and_get_inv_num(self, seq):
        """ Returns tuple (sorted_seq, num_inv) where sorted_seq is sorted
        sequence seq and num_inv is number of invertions in seq.
        Increasing order has zeor inversions.
        Sequence 1, 5, 3, 2, have 3 inversions: (5,3), (5,2) and (3,2)
        Maximum number of inversion in a sequence of length N is N * (N - 1) / 2

        seq is a sequence with unique elements.
        """
        length = len(seq)
        if length <= 1:
            return seq, 0
        left = seq[: (length / 2)]
        right = seq[(length / 2) :]
        left_sorted, num_inv_left = self._sort_and_get_inv_num(left)
        right_sorted, num_inv_right = self._sort_and_get_inv_num(right)
        # Merging and counting invertions.
        length_l, length_r = len(left), len(right)
        idx_l, idx_r = 0, 0
        seq_sorted, num_inv = [0] * length, 0
        for idx in xrange(length):
            if idx_l == length_l:
                seq_sorted[idx:] = right_sorted[idx_r :]
                break
            if idx_r == length_r:
                seq_sorted[idx:] = left_sorted[idx_l :]
                break
            if left_sorted[idx_l] <= right_sorted[idx_r]:
                seq_sorted[idx] = left_sorted[idx_l]
                idx_l += 1
            else:
                seq_sorted[idx] = right_sorted[idx_r]
                idx_r += 1
                num_inv += length_l - idx_l
        num_inv += num_inv_left + num_inv_right
        return seq_sorted, num_inv
