# -*- coding: utf-8 -*-

from datetime import datetime
import util
from gluon import *

def can_manage(venue, props):
    if current.is_user_admin():
        return True
    if props is None:
        return False
    can_manage = venue.id in util.get_list(props.venues_can_manage)
    return can_manage

def is_real_manager(venue, props):
    if props is None:
        return False
    can_manage = venue.id in util.get_list(props.venues_can_manage)
    return can_manage

def can_observe(venue, props):
    if current.is_user_admin():
        return True
    if props is None:
        return False
    can_manage = venue.is_active and venue.id in util.get_list(props.venues_can_manage)
    can_observe = venue.is_approved and venue.is_active and venue.id in util.get_list(props.venues_can_observe)
    return can_manage or can_observe

def can_view_ratings(venue, props):
    if current.is_user_admin():
        return True
    if props is None:
        return False
    if can_observe(venue, props):
        return True
    if venue.rating_available_to_all:
        if venue.feedback_accessible_immediately:
            return True
        else:
            return venue.rate_close_date > datetime.utcnow()
    else:
        return False


def can_rate(venue, props):
    if props is None:
        return False
    return (venue.id in util.get_list(props.venues_can_rate))


def can_view_rating_contributions(venue, props):
    if current.is_user_admin():
        return True
    if props is None:
        return False
    if can_observe(venue, props):
        return True
    if venue.rater_contributions_visible_to_all:
        if venue.feedback_accessible_immediately:
            return True
        else:
            return venue.rate_close_date > datetime.utcnow()
    else:
        return False
    

def can_enter_true_quality(venue, props):
    if props is None:
        return False
    return can_observe(venue, props)
    

def can_view_feedback(venue, props):
    if current.is_user_admin():
        return True
    if props is None:
        return False
    if can_observe(venue, props):
        return True
    if venue.feedback_available_to_all:
        if venue.feedback_accessible_immediately:
            return True
        else:
            return venue.rate_close_date > datetime.utcnow()
    else:
        return False

    
def can_view_submissions(venue, props):
    if current.is_user_admin():
        return True
    if props is None:
        return False
    if can_observe(venue, props):
        return True
    if venue.submissions_visible_to_all:
        if venue.submissions_visible_immediately:
            return True
        else:
            return venue.close_date > datetime.utcnow()
    else:
        return False


def can_submit(venue, props):
    if props is None:
        return False
    return venue.is_approved and venue.is_active and (venue.id in util.get_list(props.venues_can_submit))
    
def has_submitted(venue, props):
    if props is None:
        return False
    return venue.id in util.get_list(props.venues_has_submitted)

def has_rated(venue, props):
    if props is None:
        return False
    return venue.id in util.get_list(props.venues_has_rated)

def validate_task(db, t_id, user_email):
    """Validates that user_email can do the reviewing task t."""
    t = db.task(t_id)
    if t == None:
        return False, 'Not authorized.'
    if t.user != user_email:
        return False, 'Not authorized.'
    s = db.submission(t.submission_id)
    if s == None:
        return False, 'Not authorized.'
    c = db.venue(s.venue_id)
    if c == None:
        return False, 'Not authorized.'
    if not (c.is_approved and c.is_active):
        return False, 'Not authorized.'
    d = datetime.utcnow()
    if c.rate_open_date > d or c.rate_close_date < d:
        return False, 'The review period is closed.'
    return True, (t, s, c)

        
