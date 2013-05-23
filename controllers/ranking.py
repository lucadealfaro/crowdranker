# -*- coding: utf-8 -*-

import access
import util
from datetime import datetime
import numpy as np
import gluon.contrib.simplejson as simplejson


@auth.requires_login()
def view_submissions():
    """This function enables the view of the ranking of items submitted to a
    venue.  It is assumed that the people accessing this can have full
    information about the venue, including the identity of the submitters."""
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_view_submissions(c, props):
        session.flash = T('You do not have access to the submissions of this venue.')
        redirect(URL('venues', 'view_venue', args=[c.id]))
    # Prepares the query for the grid.
    q = (db.submission.venue_id == c.id)
    db.submission.quality.readable = False
    db.submission.error.readable = False
    db.submission.content.readable = False
    db.submission.content.writable = False
    db.submission.comment.writable = False
    db.submission.n_assigned_reviews.readable = True
    db.submission.n_assigned_reviews.label = T('Reviews Assigned')
    db.submission.n_completed_reviews.label = T('Done')
    db.submission.n_rejected_reviews.label = T('Declined')
    if c.allow_link_submission:
        db.submission.link.readable = True
    # Sets the fields.
    fields=[db.submission.user, db.submission.percentile,
            db.submission.n_assigned_reviews, db.submission.n_completed_reviews,
            db.submission.n_rejected_reviews]
    # Sets the link to view/edit the feedback.
    links=[]
    if access.can_view_feedback(c, props):
        links.append(dict(header=T('Feedback'), 
                          body = lambda r: A(T('View'), _class='btn', 
                                             _href=URL('feedback', 'view_feedback', args=['s', r.id]))))
    grid = SQLFORM.grid(q,
        field_id=db.submission.id,
        csv=True,
        args=request.args[:1],
        user_signature=False,
        details=False, create=False,
        editable=False,
        deletable=False,
        fields=fields,
        links=links,
        links_placement='left',
        maxtextlength=24,
        )
    title = A(c.name, _href=URL('venues', 'view_venue', args=[c.id]))
    return dict(title=title, grid=grid)


def get_num_reviews(subm_id, venue_id):
    """This function is used to heal old databases, and produce the count
    of completed reviews for each submission.
    In future releases, this is computed automatically by the review function."""
    # Tries to answer fast.
    subm = db.submission(subm_id)
    if subm.n_completed_reviews is not None:
        return subm.n_completed_reviews
    # Computes the number of reviews for each item.
    n = db((db.task.venue_id == venue_id) &
           (db.task.submission_id == subm.id) &
           (db.task.completed_date < datetime.utcnow())).count()
    # Stores it in the submission.
    subm.n_completed_reviews = n
    subm.update_record()
    db.commit()
    return n


@auth.requires_login()
def view_raters():
    """This function shows the contribution of each user to the total ranking of a venue."""
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_view_rating_contributions(c, props):
        session.flash = T('You do not have access to the rater contributions for this venue.')
        redirect(URL('venues', 'view_venue', args=[c.id]))
    # Prepares the query for the grid.
    q = (db.grades.venue_id == c.id)
    grid = SQLFORM.grid(q,
        args=request.args[:1],
        user_signature=False, details=True,
        create=False, editable=False, deletable=False,
        fields=[db.grades.user, db.grades.accuracy,
            db.grades.reputation, db.grades.n_ratings],
        maxtextlength=24,
        )
    title = A(c.name, _href=URL('venues', 'view_venue', args=[c.id]))
    return dict(grid=grid, title=title)

def short_float_or_None(val):
    if val is None:
        return None
    return float("%.3f" % val)

@auth.requires_login()
def view_grades():
    """This function shows the final grade of each user.
    It takes as single argument the venue id.
    """
    # This function is used to get experimental grades from the db.
    def get_grade_fn(venue_id, run_id):
        def f(row):
            row = db((db.grades_exp.venue_id == venue_id) &
                     (db.grades_exp.user == row.user) &
                     (db.grades_exp.run_id == run_id)).select().first()
            if row is None:
                return 'None'
            # Generates a string summary.
            s = "subm_grade: %r subm_confidence: %r rev: %r rep: %r tot: %r" % (
                short_float_or_None(row.subm_grade),
                short_float_or_None(row.subm_confidence),
                short_float_or_None(row.review_grade),
                short_float_or_None(row.reputation),
                short_float_or_None(row.grade))
            return s
        return f
    
    # Main function.
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_view_ratings(c, props):
        session.flash = T('You do not have access to the final grades for this venue.')
        redirect(URL('venues', 'view_venue', args=[c.id]))
    # Checking that final grades are recent and don't need recomputation.
    venue_row = db(db.venue.id == c.id).select().first()
    grades_date = venue_row.latest_grades_date
    if grades_date is None:
        session.flash = T('The crowd-grades have not been computed yet.')
        redirect(URL('rating', 'crowd_grade', args=[c.id]))
    # The crowd-grades have been computed already.
    if is_user_admin():
        db.grades.reputation.readable = True
    db.grades.user.represent = represent_user_by_submission_feedback
    db.grades.venue_id.readable = False
    # Prepares the buttons at the top.
    link_list = []
    if access.can_manage(c, props):
        db.grades.assigned_grade.writable = True
        db.grades.assigned_grade.comment = T('Assign the desired grade to a few users, '
                                             'then automatically fill-in the remaining '
                                             'grades via interpolation. ')
        is_editable = True
        link_list.append(A(T('Recompute crowd-grades'), _href=URL('rating', 'crowd_grade', args=[c.id])))
        link_list.append(A(T('Interpolate final grades'), 
                           _href=URL('ranking', 'interpolate_grades', args=[c.id], user_signature=True)))
        link_list.append(A(T('Clear final grades'), 
                           _href=URL('ranking', 'reset_grades', args=[c.id], user_signature=True)))

        # Creates button to release / withdraw grades. 
        if c.grades_released:
            link_list.append(A(T('Hide grades from students'),
                               _href=URL('ranking', 'release_grades', args=[c.id, 'False'], user_signature=True)))
        else:
            link_list.append(A(T('Show grades to students'),
                               _href=URL('ranking', 'release_grades', args=[c.id, 'True'], user_signature=True)))
    else:
        db.grades.assigned_grade.writable = False
        is_editable = False
    # If one is the manager, and we are viewing experimental grades, offers the option
    # to download a spreadsheet including the experimental grades.
    if is_user_admin():
        link_list.append(A(T('View experimental runs'),
                           _href=URL('ranking', 'view_exp_grades', args=[c.id])))
    if is_user_admin() and request.vars.run_ids is not None:
        link_list.append(A(T('Download research data'), 
                           _href=URL('research', 'download_research_data.csv', args=[c.id], 
                                     vars=dict(run_ids=request.vars.run_ids),
                                     user_signature=True)))
    if is_user_admin():
        link_list.append(A(T('Evaluate grades'),
                           _href=URL('research', 'evaluate_grades', args=[c.id],
                                     user_signature=True)))
        link_list.append(A(T('Rerun evaluations'),
                           _href=URL('research', 'rerun_evaluations', args=[c.id],
                                     user_signature=True)))
    # Chooses the display fields.
    display_fields = [
        db.grades.user, db.grades.venue_id,
        db.grades.submission_grade, db.grades.submission_percentile,
        db.grades.accuracy, db.grades.n_ratings, 
        db.grades.grade, db.grades.percentile,
        db.grades.assigned_grade]
    if is_user_admin():
        display_fields.append(db.grades.reputation)
        display_fields.append(db.grades.submission_control_grade)
        db.grades.submission_control_grade.readable = True
    # Adds columns for any extra grade we wish to see.
    grid_links = []
    if is_user_admin() and request.vars.run_ids is not None:
        run_ids = request.vars.run_ids.split(',')
        for r in run_ids:
            grid_links.append(dict(
                header = r, 
                body = get_grade_fn(c.id, r)))
    if is_user_admin():
        # Adds a column for the true grade.
        grid_links.append(dict(
            header = '',
            body = lambda row: A(T('Enter control grade'), _class='btn',
                _href=URL('ranking', 'edit_control_grade', args=[c.id, row.user], user_signature=True))))
    # Prepares the grid.
    q = (db.grades.venue_id == c.id)
    grid = SQLFORM.grid(q,
        fields=display_fields,
        args=request.args[:1],
        user_signature=False, details=False,
        create=False, editable=is_editable, deletable=False,
        links=grid_links,
        maxtextlength=24,
        )
    title = A(c.name, _href=URL('venues', 'view_venue', args=[c.id]))
    grades_date_info = represent_date(c.latest_grades_date, c)
    if c.grades_released:
        grades_visibility = T('Grades are visible to students')
    else:
        grades_visibility = T('Grades are not visible to students')
    return dict(grid=grid, title=title, link_list=link_list, 
                grades_date_info=grades_date_info, grades_visibility=grades_visibility)


@auth.requires_signature()
def edit_control_grade():
    """Allows admins to edit the control grade.  Arguments:
    venue id, user."""
    if not is_user_admin():
        session.flash = T('Not Authorized.')
        redirect(URL('default', 'index'))
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    # props = db(db.user_properties.user == get_user_email()).select().first()
    # No modifications to any assigned grade.
    db.grades.assigned_grade.writable = False
    db.grades.submission_control_grade.readable = db.grades.submission_control_grade.writable = True
    row = db((db.grades.venue_id == c.id) & (db.grades.user == request.args(1))).select().first()
    if row is None:
        session.flash = T('No record found for the given user.')
        redirect(URL('ranking', 'view_grades', args=[c.id]))
    form = SQLFORM(db.grades, record=row)
    if form.process().accepted:
        session.flash = T('The control grade has been inserted.')
        if request.env.http_referrer:
            redirect(request.env.http_referrer)
        else:
            redirect(URL('ranking', 'view_grades', args=[c.id]))
    # Generates a link to view the submission.
    subm_link = A(T('View submission'), _class='btn', 
                  _href=URL('feedback', 'view_feedback', args=['u', c.id, row.user]))
    return dict(form=form, subm_link=subm_link)
    

@auth.requires_signature()
def release_grades():
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    visible = (request.args(1) == 'True')
    props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_manage(c, props):
        session.flash = T('Not authorized')
        redirect(URL('ranking', 'view_grades', args=[c.id]))
    db(db.venue.id == c.id).update(grades_released = visible)
    db.commit()
    if visible:
        session.flash = T('The grades are now visible to students.')
    else:
        session.flash = T('The grades are no longer visible to students.')
    redirect(URL('ranking', 'view_grades', args=[c.id]))


@auth.requires_signature()
def reset_grades():
    """This function resets the final grades to None."""
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_manage(c, props):
        session.flash = T('Not authorized')
        redirect(URL('ranking', 'view_grades', args=[c.id]))
    db(db.grades.venue_id == c.id).update(assigned_grade = None)
    db.commit()
    session.flash = T('The grades have been cleared.')
    redirect(URL('ranking', 'view_grades', args=[c.id]))
    
    
@auth.requires_signature()
def interpolate_grades():
    """This function interpolates the specified final grades."""
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_manage(c, props):
        session.flash = T('Not authorized')
        redirect(URL('ranking', 'view_grades', args=[c.id]))
    grades = db(db.grades.venue_id == c.id).select(db.grades.id, db.grades.grade, db.grades.assigned_grade, orderby=db.grades.percentile).as_list()
    if len(grades) == 0:
        return
    # Fixes the lower end.
    last_assigned_idx = 0
    last_assigned_crowd_grade = util.get_or_0(grades[0], 'grade')
    if grades[0]['assigned_grade'] is None:
        last_assigned_grade = 0.0
        db(db.grades.id == grades[0]['id']).update(assigned_grade = 0.0)
    else:
        last_assigned_grade = grades[0]['assigned_grade']
    # Interpolates the rest.
    for i, g in enumerate(grades):
        assigned_grade = g['assigned_grade']
        if assigned_grade is not None:
            # Interpolates from previous to this one.
            end_crowd_grade = util.get_or_0(g, 'grade')
            for k in range(last_assigned_idx + 1, i):
                crowd_grade = util.get_or_0(grades[k], 'grade')
                if end_crowd_grade == last_assigned_crowd_grade:
                    new_grade = end_crowd_grade
                else:
                    new_grade = (last_assigned_grade + (assigned_grade - last_assigned_grade) *   
                                 (crowd_grade - last_assigned_crowd_grade) / 
                                 (end_crowd_grade - last_assigned_crowd_grade))
                db(db.grades.id == grades[k]['id']).update(assigned_grade = new_grade)
            last_assigned_idx = i
            last_assigned_grade = assigned_grade
            last_assigned_crowd_grade = end_crowd_grade
    db.commit()
    session.flash = T('The grades have been interpolated.')
    redirect(URL('ranking', 'view_grades', args=[c.id]))
    

def represent_task_name_view_feedback(v, r):
    return A(T('View submission'), _class='btn', _href=URL('feedback', 'view_feedback', args=['s', r.submission_id]))


@auth.requires_login()
def view_comparison():
    """This function displays an individual task."""
    # We are given the task id.
    t = db.task(request.args(0)) or redirect(URL('default', 'index'))
    rating_user = t.user
    submission_id = t.submission_id
    # We need to get the most recent comparison by the user who has done this task.
    comp = db((db.comparison.venue_id == t.venue_id) &
              (db.comparison.user == t.user)).select(orderby=~db.comparison.date).first()
    c = db.venue(t.venue_id) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    subm = db.submission(submission_id)
    if not access.can_observe(c, props):
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    db.comparison.id.readable = False
    db.comparison.ordering.readable = False
    db.comparison.grades.represent = represent_grades
    db.comparison.date.readable = False
    db.comparison.is_valid.readable = False
    db.task.user.readable = True
    db.task.user.label = T('Reviewer')
    db.task.user.represent = lambda v, r: A(v, _href=URL('feedback', 'view_feedback', args=['u', c.id, v]))
    db.task.venue_id.readable = True
    db.task.venue_id.represent = represent_venue_id
    db.task.comments.readable = True
    db.task.is_completed.readable = True
    db.task.rejected.readable = True
    db.task.helpfulness.readable = True
    db.task.feedback.readable = True
    db.comparison.venue_id.readable = (t is None)
    db.comparison.venue_id.represent = represent_venue_id
    db.comparison.user.readable = (comp is None)
    db.comparison.user.label = T('Reviewer')
    if comp is None:
        comp_form = T('No corresponding comparison found.')
    else:
        comp_form = SQLFORM(db.comparison, record=comp, readonly=True)
    task_form = SQLFORM(db.task, record=t, readonly=True)
    return dict(comp_form=comp_form, task_form=task_form, user=rating_user, subm_id=submission_id,
                subm=subm)


@auth.requires_login()
def view_comparisons_index():
    """This function displays all comparisons for a venue."""
    props = db(db.user_properties.user == get_user_email()).select().first()
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    if not access.can_observe(c, props):
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    q = ((db.comparison.venue_id == c.id) & (db.comparison.is_valid == True))
    db.comparison.ordering.represent = represent_ordering
    db.comparison.user.represent = represent_user_by_submission_feedback
    db.comparison.venue_id.readable = False
    fields=[db.comparison.user, db.comparison.venue_id,
            db.comparison.grades, db.comparison.submission_nicknames, db.comparison.date,]
    if is_user_admin():
        fields=[db.comparison.user, db.comparison.venue_id, db.comparison.grades,
                db.comparison.submission_nicknames, db.comparison.is_valid, db.comparison.date,]
        q = (db.comparison.venue_id == c.id)
    grid = SQLFORM.grid(q,
        field_id=db.comparison.id,
        fields=fields,
        csv=True,
        args=request.args[:1],
        user_signature=False,
        details=False, create=False,
        editable=False, deletable=False,
        maxtextlength=24,
        )
    title = T('Comparisons for venue ' + c.name)
    return dict(title=title, grid=grid)

@auth.requires_login()
def view_comparisons_given_submission():
    """This function displays comparisons wich contains given submission."""
    props = db(db.user_properties.user == get_user_email()).select().first()
    subm = db.submission(request.args(0)) or redirect(URL('default', 'index'))
    c = db.venue(subm.venue_id) or redirect(URL('default', 'index'))
    if not access.can_observe(c, props):
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    # Create query.
    # First, determine the people who have reviewed this submission.
    reviewers_r = db(db.task.submission_id == subm.id).select(db.task.user).as_list()
    reviewers = [x['user'] for x in reviewers_r]
    # Second, displays all the comparisons by these users in this venue.
    q = ((db.comparison.venue_id == c.id) &
         (db.comparison.user.belongs(reviewers)) & (db.comparison.is_valid == True))
    db.comparison.ordering.represent = represent_ordering
    db.comparison.user.represent = represent_user_by_submission_feedback
    db.comparison.venue_id.readable = False
    fields=[db.comparison.user, db.comparison.venue_id,
            db.comparison.grades, db.comparison.submission_nicknames, db.comparison.date,]
    if is_user_admin():
        fields=[db.comparison.user, db.comparison.venue_id,
                db.comparison.grades, db.comparison.submission_nicknames,
                db.comparison.is_valid, db.comparison.date,]
        q = ((db.comparison.venue_id == c.id) & (db.comparison.user.belongs(reviewers)))

    grid = SQLFORM.grid(q,
        field_id=db.comparison.id,
        fields=fields,
        csv=True,
        args=request.args[:1],
        user_signature=False,
        details=False, create=False,
        editable=False, deletable=False,
        maxtextlength=24,
        )
    return dict(subm=subm, venue=c, grid=grid)


@auth.requires_login()
def view_comparisons_given_user():
    """This function displays comparisons for a user in a given venue.
    The arguments are user, venue_id."""
    props = db(db.user_properties.user == get_user_email()).select().first()
    user = request.args(0) or redirect(URL('default', 'index'))
    venue_id = request.args(1) or redirect(URL('default', 'index'))
    c = db.venue(venue_id) or redirect(URL('default', 'index'))
    if not access.can_observe(c, props):
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    # Create query.
    q = ((db.comparison.venue_id == venue_id) &
         (db.comparison.user == user) & (db.comparison.is_valid == True))
    db.comparison.ordering.represent = represent_ordering
    db.comparison.venue_id.readable = False
    db.comparison.user.represent = represent_user_by_submission_feedback
    fields=[db.comparison.user, db.comparison.venue_id,
            db.comparison.grades, db.comparison.submission_nicknames, db.comparison.date,]
    if is_user_admin():
        fields=[db.comparison.user, db.comparison.venue_id, db.comparison.grades,
                db.comparison.submission_nicknames, db.comparison.is_valid, db.comparison.date,]
        q = ((db.comparison.venue_id == venue_id) &
             (db.comparison.user == user))

    grid = SQLFORM.grid(q,
        field_id=db.comparison.id,
        fields=fields,
        csv=True,
        args=request.args[:2],
        user_signature=False,
        details=False, create=False,
        editable=False, deletable=False,
        maxtextlength=24,
        )
    return dict(user=user, venue=c, grid=grid)


@auth.requires_login()
def view_exp_grades():
    """This function enables to select experimental grades 
    that are available for a venue, and display them."""
    if not is_user_admin():
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    c = db.venue(request.args(0))
    rows = db(db.grades_exp.venue_id == c.id).select(db.grades_exp.run_id, distinct=True)
    experiment_list = [r.run_id for r in rows]
    # Produces a multiple-choice form, indicating which results one wants to display.
    form = SQLFORM.factory(
        Field('run_ids', 'list:string', requires=IS_IN_SET(experiment_list, multiple=True)),
        )
    if form.process().accepted:
        # Redirects to displaying those selected experiments.
        if isinstance(form.vars.run_ids, basestring):
            exp_list = form.vars.run_ids
        else:
            exp_list = ','.join(form.vars.run_ids)
        redirect(URL('ranking', 'view_grades', args=[request.args(0)], vars={'run_ids': exp_list}))
    venue_link = A(c.name, _href=URL('venues', 'view_venue', args=[c.id]))
    return dict(form=form, venue_link=venue_link)
