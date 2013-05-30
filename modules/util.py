# -*- coding: utf-8 -*-

from gluon import *
import re
import string
import random

email_split_pattern = re.compile('[,\s]+')
whitespace = re.compile('\s+$')
all_whitespace = re.compile('\s*$')
vowels = 'aeiouy'
consonants = 'bcdfgmnpqrstvwz'

def union_id_list(l1, l2):
    """Computes the union of the 'id' elements of two lists of dictionaries."""
    id1l = [el['id'] for el in l1]
    id2l = [el['id'] for el in l2]
    for id in id2l:
        if not (id in id1l):
            id1l.append(id)
    return id1l

def union_list(l1, l2):
    l = l1[:]
    for el in l2:
        if el not in l:
            l.append(el)
    return l
            
def get_list(f):
    """Unfortunately, empty list fields are often returned as None rather than the empty list."""
    if f == None:
        return []
    else:
        return f

def id_list(l):
    return [el['id'] for el in l]
    
def get_id_list(f):
    return id_list(get_list(f))
    
def list_append_unique(l, el):
    """Appends an element to a list, if not present."""
    if l == None:
        return [el]
    if el in l:
        return l
    else:
        return l + [el]
                
def list_remove(l, el):
    """Removes element el from list l, if found."""
    if l == None:
        return []
    if el not in l:
        return l
    else:
        l.remove(el)
        return l
        
def list_diff(l1, l2):
    if l1 == None:
        l1 = []
    if l2 == None:
        l2 = []
    r = []
    for el in l1:
        if el not in l2:
            r += [el]
    return r

        
def split_emails(s):
    """Splits the emails that occur in a string s, returning the list of emails."""
    l = email_split_pattern.split(s)
    if l == None:
        return []
    else:
        r = []
        for el in l:
            if len(el) > 0 and not whitespace.match(el):
                r += [el]
        return r

def normalize_email_list(l):
    if isinstance(l, basestring):
        l = [l]
    r = []
    for el in l:
        ll = split_emails(el)
        for addr in ll:
            if addr not in r:
                r.append(addr)
    r.sort()
    return r

def is_none(s):
    """Checks whether something is empty or None"""
    if s == None:
        return True
    elif isinstance(s, basestring):
        return all_whitespace.match(str(s))
    else:
        return False
    
def get_random_id(n_sections=6, section_length=6):
    """Produces a memorable random string."""
    sections = []
    for i in range(n_sections):
        s = ''
        for j in range(section_length / 2):
            s += random.choice(consonants) + random.choice(vowels)
        sections.append(s)
    return '_'.join(sections)

def shorten(s, max_length=32, dotdot=True):
    max_length = max(2, max_length)
    if s is None:
        return ""
    if len(s) <= max_length:
        return s
    else:
        if dotdot:
            return s[:max_length - 3] + "..."
        else:
            return s[:max_length]

def produce_submission_nickname(subm):
    if subm != None:
        return shorten(subm.user, max_length=3, dotdot=False)
    else:
        return '???'

def get_original_extension(filename):
    if filename is Non            do_debias = form.vars.do_debiase:
        return ''
    else:
        return filename.split('.')[-1]
        
        
def print_codes(s):
    out = ''
    if s is not None:
        for c in s:
            out += str(ord(c)) + ' '
    return out


def get_or_0(d, k):
    r = d.get(k, None)
    if r == None:
        return 0.0
    else:
        return r


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


def decode_json_grades(dict_grades_json):
    """ dict_grades_json is a json serialized dictionary subm_id -> grade.
    """
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


def compute_percentile(id_to_grade):
    """ Method returns a dictionary id -> percentile given a dictionary
    id -> grade."""
    # Computes the grade percentiles.
    l = []
    for u, g in id_to_grade.iteritems():
        l.append((u, g))
    sorted_l = sorted(l, key = lambda x: x[1], reverse=True)
    id_to_perc = {}
    n_ids = float(len(sorted_l))
    for i, el in enumerate(sorted_l):
        id_to_perc[el[0]] = 100.0 * (n_ids - float(i)) / n_ids
    return id_to_perc



