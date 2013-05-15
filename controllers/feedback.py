# -*- coding: utf-8 -*-

import access
import util

@auth.requires_login()
def index():
    """Produces a list of the feedback obtained for a given venue,
    or for all venues."""
    venue_id = request.args(0)
    if venue_id == 'all':
        q = (db.submission.user == get_user_email())
    else:
        q = ((db.submission.user == get_user_email()) 
            & (db.submission.venue_id == venue_id))
    db.submission.id.represent = lambda x, r: A(T('View'), _class='btn', _href=URL('submission', 'view_own_submission', args=['v', r.id]))
    db.submission.id.label = T('Submission')
    db.submission.id.readable = True
    db.submission.venue_id.readable = True
    grid = SQLFORM.grid(q,
        fields=[db.submission.id, db.submission.venue_id,
                db.submission.date_created, db.submission.date_updated, ],
        csv=False, details=False, create=False, editable=False, deletable=False,
        args=request.args[:1],
        maxtextlength=24,        
        )
    return dict(grid=grid)


@auth.requires_login()
def view_feedback():
    """Shows detailed feedback for a user in a venue.
    This controller accepts various types of arguments: 
    * 's', submission_id
    * 'u', venue_id, username
    * 'v', venue_id  (in which case, shows own submission to that venue)
    """
    if len(request.args) == 0:
        redirect(URL('default', 'index'))
    if request.args(0) == 's':
        # submission_id
        n_args = 2
        subm = db.submission(request.args(1)) or redirect(URL('default', 'index'))
        c = db.venue(subm.venue_id) or redirect(URL('default', 'index'))
        username = subm.user
    elif request.args(0) == 'v':
        # venue_id
        n_args = 2
        c = db.venue(request.args(1)) or redirect(URL('default', 'index'))
        username = get_user_email()
        subm = db((db.submission.user == username) & (db.submission.venue_id == c.id)).select().first()
    else:
        # venue_id, username
        n_args = 3
        c = db.venue(request.args(1)) or redirect(URL('default', 'index'))
        username = request.args(2) or redirect(URL('default', 'index'))
        subm = db((db.submission.user == username) & (db.submission.venue_id == c.id)).select().first()

    # Checks permissions.
    props = db(db.user_properties.user == get_user_email()).select().first()
    if props == None:
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    is_author = (username == get_user_email())
    can_view_feedback = access.can_view_feedback(c, props) or is_author
    if (not can_view_feedback):
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    if not (access.can_view_feedback(c, props) or datetime.utcnow() > c.rate_close_date):
        session.flash = T('The ratings are not yet available.')
        redirect(URL('feedback', 'index', args=['all']))

    # Produces the link to edit the feedback.
    edit_feedback_link = None
    if subm is not None and access.can_observe(c, props):
        edit_feedback_link = A(T('Edit feedback'), _class='btn', 
                               _href=URL('submission', 'edit_feedback', args=[subm.id]))
    # Produces the download link.
    download_link = None
    if subm is not None and c.allow_file_upload and subm.content is not None:
        if is_author:
            download_link = A(T('Download'), _class='btn', 
                          _href=URL('submission', 'download_author', args=[subm.id, subm.content]))
        else:
            download_link = A(T('Download'), _class='btn', 
                          _href=URL('submission', 'download_manager', args=[subm.id, subm.content]))
    venue_link = A(c.name, _href=URL('venues', 'view_venue', args=[c.id]))

    # Submission link.
    subm_link = None
    if subm is not None and c.allow_link_submission:
        subm_link = A(subm.link, _href=subm.link)
    # Submission content and feedback.
    subm_comment = None
    subm_feedback = None
    if subm is not None:
        raw_subm_comment = keystore_read(subm.comment)
        if raw_subm_comment is not None and len(raw_subm_comment) > 0:
            subm_comment = MARKMIN(keystore_read(subm.comment))
        raw_feedback = keystore_read(subm.feedback)
        if raw_feedback is not None and len(raw_feedback) > 0:
            subm_feedback = MARKMIN(raw_feedback)
    # Display settings.
    db.submission.percentile.readable = True
    db.submission.comment.readable = True
    db.submission.feedback.readable = True
    if access.can_observe(c, props):
        db.submission.quality.readable = True
        db.submission.error.readable = True
    # Reads the grade information.
    submission_grade = submission_percentile = None
    review_grade = review_percentile = user_reputation = None
    final_grade = final_percentile = None
    assigned_grade = None
    if c.grades_released:
        grade_info = db((db.grades.user == username) & (db.grades.venue_id == c.id)).select().first()
        if grade_info is not None:
            submission_grade = represent_quality(grade_info.submission_grade, None)
            submission_percentile = represent_percentage(grade_info.submission_percentile, None)
            review_grade = represent_quality_10(grade_info.accuracy, None)
            review_percentile = represent_percentage(grade_info.accuracy_percentile, None)
            user_reputation = represent_01_as_percentage(grade_info.reputation, None)
            final_grade = represent_quality(grade_info.grade, None)
            final_percentile = represent_percentage(grade_info.percentile, None)
            assigned_grade = represent_quality(grade_info.assigned_grade, None)
    # Makes a grid of comments.
    db.task.submission_name.readable = False
    db.task.assigned_date.readable = False
    db.task.completed_date.readable = False
    db.task.rejected.readable = True
    db.task.helpfulness.readable = db.task.helpfulness.writable = True
    # Prevent editing the comments; the only thing editable should be the "is bogus" field.
    db.task.comments.writable = False
    db.task.comments.readable = True
    ranking_link = None
    if access.can_observe(c, props):
        db.task.user.readable = True
        db.task.completed_date.readable = True
        links = [
            dict(header=T('Review details'), body= lambda r:
                 A(T('View'), _class='btn', _href=URL('ranking', 'view_comparison', args=[r.id]))),
            ]
        details = False
        if subm is not None:
            ranking_link = A(T('details'), _href=URL('ranking', 'view_comparisons_given_submission', args=[subm.id]))
        reviews_link = A(T('details'), _href=URL('ranking', 'view_comparisons_given_user', args=[username, c.id]))
        db.task.user.represent = lambda v, r: A(v, _href=URL('ranking', 'view_comparisons_given_user',
                                                                   args=[v, c.id], user_signature=True))
    else:
        user_reputation = None
        links = [
            dict(header=T('Review feedback'), body = lambda r:
                 A(T('Give feedback'), _class='btn', 
                   _href=URL('feedback', 'reply_to_review', args=[r.id], user_signature=True))),
            ]
        details = False
        ranking_link = None
        reviews_link = None
    if subm is not None:
        q = ((db.task.submission_id == subm.id) & (db.task.is_completed == True))
        # q = (db.task.submission_id == subm.id)
    else:
        q = (db.task.id == -1)
    grid = SQLFORM.grid(q,
        fields=[db.task.id, db.task.user, db.task.rejected, db.task.comments, db.task.helpfulness, ],
        details = details,
        csv=False, create=False, editable=False, deletable=False, searchable=False,
        links=links,
        args=request.args[:n_args],
        maxtextlength=24,
        )
    return dict(subm=subm, download_link=download_link, subm_link=subm_link, username=username,
                subm_comment=subm_comment, subm_feedback=subm_feedback,
                edit_feedback_link=edit_feedback_link,
                is_admin=is_user_admin(), 
                submission_grade=submission_grade, submission_percentile=submission_percentile, 
                review_grade=review_grade, review_percentile=review_percentile,
                user_reputation=user_reputation,
                final_grade=final_grade, final_percentile=final_percentile, 
                assigned_grade=assigned_grade,
                venue_link=venue_link, grid=grid, ranking_link=ranking_link,
                reviews_link=reviews_link)


@auth.requires_signature()    
def reply_to_review():
    t = db.task(request.args(0)) or redirect(URL('default', 'index'))
    db.task.submission_name.readable = False
    db.task.assigned_date.readable = False
    db.task.completed_date.readable = False
    db.task.comments.readable = False
    db.task.helpfulness.readable = db.task.helpfulness.writable = True
    db.task.feedback.readable = db.task.feedback.writable = True
    form = SQLFORM(db.task, record=t)
    form.vars.feedback = keystore_read(t.feedback)
    if form.process(onvalidation=validate_review_feedback(t)).accepted:
        session.flash = T('Updated.')
        redirect(URL('feedback', 'view_feedback', args=['s', t.submission_id]))
    link_to_submission = A(T('View submission'), _href=URL('submission', 'view_own_submission', args=['v', t.submission_id]))
    review_comments = MARKMIN(keystore_read(t.comments))
    return dict(form=form, link_to_submission=link_to_submission, review_comments=review_comments)
    

def validate_review_feedback(t):
    def f(form):
        if not form.errors:
            feedback_id = keystore_update(t.feedback, form.vars.feedback)
            form.vars.feedback = feedback_id
    return f


@auth.requires_login()
def view_my_reviews():
    """This controller displays the reviews a user has written for a venue, along with
    the feedback they received."""
    c = db.venue(request.args(0)) or redirect(URL('rating', 'review_index'))
    link_to_venue = A(c.name, _href=URL('venues', 'view_venue', args=[c.id]))
    link_to_eval = A(T('My evaluation in this venue'), _class='btn', 
                     _href=URL('feedback', 'view_feedback', args=['v', c.id]))
    q = ((db.task.user == get_user_email()) & (db.task.venue_id == c.id))
    db.task.rejected.readable = True
    db.task.helpfulness.readable = True
    db.task.comments.readable = True
    db.task.feedback.readable = True
    # To prevent chopping
    db.task.submission_name.represent = represent_text_field
    grid = SQLFORM.grid(q,
        fields=[db.task.submission_name, db.task.rejected, db.task.helpfulness],
        details=True,
        editable=False, deletable=False, create=False, searchable=False,
        csv=False,
        args=request.args[:1],
        maxtextlength=24,
        )
    return dict(grid=grid, link_to_venue=link_to_venue, link_to_eval=link_to_eval)
