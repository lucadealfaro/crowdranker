# -*- coding: utf-8 -*-

from gluon import *
import numpy as N

def kendall_tau(grades1, grades2):
    """Computes the kendall-tau correlation between two orders.
    Each order has the form (score, id), where the id can be anything
    (e.g., a username)."""
    grades1.sort()
    grades2.sort()
    pos1 = {}
    pos2 = {}
    for i, el in enumerate(grades1):
        score, id = el
        if score is not None:
            pos1[id] = i
    for i, el in enumerate(grades2):
        score, id = el
        if score is not None:
            pos2[id] = i
    # Computes the total of positions different.
    tot = 0
    n = 0
    for id, idx1 in pos1.iteritems():
        if id in pos2:
            idx2 = pos2[id]
            tot += abs(idx1 - idx2)
            n += 1
    if n < 2:
        return 0.0
    kt = tot / (n * (n - 1) / 2.0)
    return kt


def grade_score(grades1, grades2):
    """Computes the score correlation between two gradings.
    This is computed as follows.  First, the two gradings are
    renormalized, so that the average is 0 and the variance is 1.
    Then, we compute the standard deviation of the score difference,
    and we compare it with sqrt(2), which is the expected one."""
    # First, we compute the common ids.
    id1 = [id for score, id in grades1 if score is not None]
    id2 = [id for score, id in grades2 if score is not None]
    ids = [id for id in id1 if id in id2]
    # Then, we compute mappings of ids to grades.
    map1 = dict([(id, g) for g, id in grades1])
    map2 = dict([(id, g) for g, id in grades2])
    # Finally, arrays of grades.
    a1 = N.array([map1[id] for id in ids])
    a2 = N.array([map2[id] for id in ids])
    if a1.size < 2:
        return 0.0
    current.logger.info("a1: %r" % a1)
    current.logger.info("a2: %r" % a2)
    a1 = a1 - N.average(a1)
    a2 = a2 - N.average(a2)
    a1 = a1 / N.std(a1)
    a2 = a2 / N.std(a2)
    s = N.std(a1 - a2)
    current.logger.info("a1 n: %r" % a1)
    current.logger.info("a2 n: %r" % a2)
    current.logger.info("s: %r" % s)
    return 1.0 - s / (2.0 ** 0.5)


def grade_norm2(grades1, grades2):
    """Computes the norm-2 distance between the two sets of
    grades.  This makes sense of course only if grading out of 10."""
    # First, we compute the common ids.
    id1 = [id for score, id in grades1 if score is not None]
    id2 = [id for score, id in grades2 if score is not None]
    ids = [id for id in id1 if id in id2]
    # Then, we compute mappings of ids to grades.
    map1 = dict([(id, g) for g, id in grades1])
    map2 = dict([(id, g) for g, id in grades2])
    # Finally, arrays of grades.
    a1 = N.array([map1[id] for id in ids])
    a2 = N.array([map2[id] for id in ids])
    if a1.size < 2:
        return 0.0
    d = a1 - a2
    sq_d = N.sum(d * d) / d.size
    return sq_d ** 0.5


def rank_difference(grades1, grades2):
    grades1.sort()
    grades2.sort()
    pos1 = {}
    pos2 = {}
    for i, el in enumerate(grades1):
        score, id = el
        if score is not None:
            pos1[id] = i
    for i, el in enumerate(grades2):
        score, id = el
        if score is not None:
            pos2[id] = i
    # Computes the difference in rank.
    rd = {}
    for id, idx1 in pos1.iteritems():
        if id in pos2:
            idx2 = pos2[id]
            rd[id] = abs(idx1 - idx2)
    return rd
    
