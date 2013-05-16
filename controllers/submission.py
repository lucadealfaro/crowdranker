# -*- coding: utf-8 -*-

import access
import util
import ranker
import re
from contenttype import contenttype


@auth.requires_login()
def submit():
    # Gets the information on the venue.
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    # Gets information on the user.
    props = db(db.user_properties.user == get_user_email()).select().first()
    if props == None: 
        venue_ids = []
        venues_has_submitted = []
    else:
        venue_ids = util.get_list(props.venues_can_submit)
        venues_has_submitted = util.get_list(props.venues_has_submitted)
    # Is the venue open for submission?
    if not access.can_submit(c, props):
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    t = datetime.utcnow()
    if c.open_date > t:
        session.flash = T('Submissions are not open yet.')
        redirect(URL('venues', 'subopen_index'))
    if c.close_date < t:
        session.flash = T('The submission deadline has passed; submissions are closed.')
        redirect(URL('venues', 'subopen_index'))
        
    # Ok, the user can submit.  Looks for previous submissions.
    sub = db((db.submission.venue_id == c.id) & (db.submission.user == get_user_email())).select().first()
    if sub != None and not c.allow_multiple_submissions:
        session.flash = T('Update your existing submission')
        redirect(URL('submission', 'view_own_submission', args=['v', sub.id]))
    # Check whether link submission is allowed.
    db.submission.link.readable = db.submission.link.writable = c.allow_link_submission
    # Check whether attachment submission is allowed.
    db.submission.content.readable = db.submission.content.writable = c.allow_file_upload
    db.submission.n_completed_reviews.readable = False
    db.submission.n_rejected_reviews.readable = False
    db.submission.feedback.readable = db.submission.feedback.writable = False
    db.submission.date_updated.readable = False
    db.submission.date_created.readable = False
    db.submission.user.default = get_user_email()
    # Assigns default quality to the submission.
    avg, stdev = ranker.get_init_average_stdev()
    db.submission.quality.default = avg
    db.submission.error.default = stdev
    # No percentile readable.
    db.submission.percentile.readable = False
    # TODO(luca): check that it is fine to do the download link without parameters.
    form = SQLFORM(db.submission, upload=URL('download_auhor', args=[None]))
    form.vars.venue_id = c.id
    form.vars.date_updated = datetime.utcnow()
    if request.vars.content != None and request.vars.content != '':
        form.vars.original_filename = request.vars.content.filename
    if form.process(onvalidation=write_comment_to_keystore).accepted:
        # Adds the venue to the list of venues where the user submitted.
        # TODO(luca): Enable users to delete submissions.  But this is complicated; we need to 
        # delete also their quality information etc.  For the moment, no deletion.
        submitted_ids = util.id_list(venues_has_submitted)
        submitted_ids = util.list_append_unique(submitted_ids, c.id)
        if props == None:
            db.user_properties.insert(user=get_user_email(),
                                      venues_has_submitted=submitted_ids)
        else:
            props.update_record(venues_has_submitted=submitted_ids)
        db.commit()
        session.flash = T('Your submission has been accepted.')
        # We send the user to review their own submission, for completeness.
        redirect(URL('submission', 'view_own_submission', args=['v', form.vars.id]))
    instructions = keystore_read(c.submission_instructions, default='')
    if instructions == '':
        instructions = None
    else:
        instructions = MARKMIN(instructions)
    return dict(form=form, venue=c, instructions=instructions)


def write_comment_to_keystore(form):
    """Gets a submission form, and writes the comment to the keystore, replacing
    it by the keystore key."""
    k = keystore_write(form.vars.comment)
    form.vars.comment = k


@auth.requires_login()
def manager_submit():
    """This function is used by venue managers to do submissions on behalf of others.  It can be used
    even when the submission deadline is past."""
    # Gets the information on the venue.
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    # Checks that the user is a manager for the venue.
    manager_props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_manage(c, manager_props):
        session.flash = T('Not authorized!')
        redirect(URL('default', 'index'))
    # Prepares the submission.
    db.submission.user.readable = db.submission.user.writable = True
    db.submission.user.default = ''
    db.submission.feedback.readable = db.submission.feedback.writable = False
    # Assigns default quality to the submission.
    avg, stdev = ranker.get_init_average_stdev()
    db.submission.quality.default = avg
    db.submission.error.default = stdev
    db.submission.percentile.readable = False
    db.submission.n_assigned_reviews.readable = False
    db.submission.n_completed_reviews.readable = False
    db.submission.n_rejected_reviews.readable = False
    # Check whether link submission is allowed.
    db.submission.link.readable = db.submission.link.writable = c.allow_link_submission
    # Check whether attachment submission is allowed.
    db.submission.content.readable = db.submission.content.writable = c.allow_file_upload

    # Prepares the submission form.
    form = SQLFORM(db.submission, upload=URL('download_manager', args=[None]))
    form.vars.venue_id = c.id
    form.vars.date_updated = datetime.utcnow()
    if request.vars.content != None and request.vars.content != '':
        form.vars.original_filename = request.vars.content.filename
    if form.process(onvalidation=write_comment_to_keystore).accepted:
        # Adds the venue to the list of venues where the user submitted.
        props = db(db.user_properties.user == form.vars.email).select().first()
        if props == None: 
            venues_has_submitted = []
        else:
            venues_has_submitted = util.get_list(props.venues_has_submitted)
        submitted_ids = util.id_list(venues_has_submitted)
        submitted_ids = util.list_append_unique(submitted_ids, c.id)
        if props == None:
            db(db.user_properties.user == form.vars.user).update(venues_has_submitted=submitted_ids)
        else:
            props.update_record(venues_has_submitted=submitted_ids)

        # If there is a prior submission of the same author to this venue, replaces the content.
        is_there_another = False
        other_subms = db((db.submission.user == form.vars.user) & 
                         (db.submission.venue_id == c.id)).select()
        for other_subm in other_subms:
            if other_subm.id != form.vars.id:
                is_there_another = True
                keystore_delete(other_subm.comment)
                other_subm.update_record(
                    date_updated = datetime.utcnow(),
                    original_filename = form.vars.original_filename,
                    content = form.vars.content,
                    link = form.vars.link,
                    comment = form.vars.comment,
                    n_assigned_reviews = 0,
                    n_completed_reviews = 0,
                    n_rejected_reviews = 0,
                    )
        # And deletes this submission.
        if is_there_another:
            db(db.submission.id == form.vars.id).delete()
            session.flash = T('The previous submission by the same author has been updated.')
        else:
            session.flash = T('The submission has been added.')
        db.commit()
        redirect(URL('ranking', 'view_submissions', args=[c.id]))
    instructions = keystore_read(c.submission_instructions, default='')
    if instructions == '':
        instructions = None
    else:
        instructions = MARKMIN(instructions)
    return dict(form=form, venue=c, instructions=instructions)
         

@auth.requires_login()
def view_submission():
    """Allows viewing a submission by someone who has the task to review it.
    This function is accessed by task id, not submission id, to check access
    and anonymize the submission.
    The parameters are: 
    * 'v', or 'e': according to whether one wants to view only, or also edit,
      the review;
    * task_id.
    """
    ok, v = access.validate_task(db, request.args(1), get_user_email())
    if not ok:
        session.flash = T(v)
        redirect(URL('default', 'index'))
    (t, subm, c) = v

    # Attachment submission.
    attachment_link = None
    if c.allow_file_upload:
        if subm.content is not None and subm.content != '':
            attachment_link = P(A(T('Download attachment'), _class='btn',
                                _href=URL('download_reviewer', args=[t.id, subm.content])))
        else:
            attachment_link = P(T('None'))
            
    # Link submission.
    if c.allow_link_submission and subm.link is not None:
        subm_link = P(A(subm.link, _href=subm.link))
    else:
        subm_link = P(T('None'))
        
    # Content; this is always present.
    if subm.comment is not None:
        subm_content = MARKMIN(keystore_read(subm.comment))
    else:
        subm_content = P(T('None'))
        
    review_link = None
    if request.args(0) == 'e':
        review_link = A(T('Enter/edit review'), _class='btn', _href=URL('rating', 'review', args=[t.id]))
    submission_name = keystore_read(t.submission_name, default='submission')
    return dict(task=t,
                submission_name=submission_name, subm=subm,
                subm_content=subm_content, subm_link=subm_link,
                review_link=review_link, attachment_link=attachment_link)


@auth.requires_login()
def view_own_submission_to_venue():
    """This redirects to view_own_submission, but is indexed by venue_id."""
    subm = db((db.submission.venue_id == request.args(0)) & (db.submission.user == get_user_email())).select().first()
    if subm is None:
        redirect(URL('default', 'index'))
    redirect(URL('submission', 'view_own_submission', args=['v', subm.id]))
    
   
@auth.requires_login()
def view_own_submission():
    """Allows viewing a submission by the submission owner.
    The argument list is:
    - v or e, depending on whether the user wants to edit the submission (e) or just view it;
    - the submission id."""
    subm = db.submission(request.args(1)) or redirect(URL('default', 'index'))
    want_to_edit = request.args(0) == 'e'
    if subm.user != get_user_email():
        session.flash = T('You cannot view this submission.')
        redirect(URL('default', 'index'))
    c = db.venue(subm.venue_id) or redirect(URL('default', 'index'))
    t = datetime.utcnow()
    if c.is_active and c.is_approved and c.close_date < t:
        want_to_edit = False
    # If there is feedback, redirects to the feedback view.
    if c.is_active and c.is_approved and c.rate_close_date < t:
         return redirect(URL('feedback', 'view_feedback', args=['s', subm.id]))
    # Check whether link submission is allowed.
    db.submission.link.readable = db.submission.link.writable = c.allow_link_submission
    # Check whether attachment submission is allowed.
    db.submission.content.readable = db.submission.content.writable = c.allow_file_upload
    db.submission.user.readable = db.submission.user.writable = False
    db.submission.feedback.readable = db.submission.feedback.writable = False
    db.submission.percentile.readable = db.submission.percentile.writable = False
    db.submission.n_completed_reviews.readable = False
    db.submission.n_rejected_reviews.readable = False
    db.submission.content.label = T('Your uploaded file')
    db.submission.venue_id.readable = True
    db.submission.comment.readable = True
    can_be_edited = (c.is_active and c.is_approved and c.open_date <= t and c.close_date >= t)
    is_editable = want_to_edit and can_be_edited
    edit_button = None
    if is_editable:
        # The venue is still open for submissions, and we allow editing of the submission.
        db.submission.date_updated.update = datetime.utcnow()
        old_comment_key = subm.comment
        form = SQLFORM(db.submission, record=subm, upload=URL('download_author', args=[subm.id]),
                       deletable=False)
        form.vars.comment = keystore_read(old_comment_key)
        if request.vars.content != None and request.vars.content != '':
            form.vars.original_filename = request.vars.content.filename
        if form.process(onvalidation=update_comment_to_keystore(old_comment_key)).accepted:
            session.flash = T('Your submission has been updated.')
            redirect(URL('submission', 'view_own_submission', args=['v', subm.id]))
        instructions = keystore_read(c.submission_instructions, default='')
        if instructions == '':
            instructions = None
        else:
            instructions = MARKMIN(instructions)
    else:
        instructions = None
        # The venue is no longer open for submission.
        form = SQLFORM(db.submission, record=subm, readonly=True,
                       upload=URL('download_author', args=[subm.id]), buttons=[])
        if can_be_edited:
            edit_button = A(T('Edit your submission'), _class='btn',
                            _href=URL('submission', 'view_own_submission', args=['e', subm.id]))
    warnings = []
    if (not want_to_edit) and c.allow_file_upload and (subm.content is None or subm.content == ''):
        warnings.append(T('No file has been attached.'))
    return dict(form=form, subm=subm, edit_button=edit_button,
                warnings=warnings, instructions=instructions)


def update_comment_to_keystore(old_key):
    def f(form):
        """Gets a submission form, and writes the comment to the keystore, replacing
        it by the keystore key."""
        k = keystore_update(old_key, form.vars.comment)
        form.vars.comment = k
    return f


@auth.requires_login()
def edit_feedback():
    """This function is used by TAs and instructors to give feedback on a submission."""
    subm = db.submission(request.args(0))
    c = db.venue(subm.venue_id)
    if subm is None or c is None:
        session.flash = T('No such submission.')
        redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_observe(c, props):
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    # Sets the correct permissions.
    db.submission.quality.readable = False
    db.submission.error.readable = False
    db.submission.content.readable = False
    db.submission.content.writable = False
    db.submission.comment.writable = False
    db.submission.n_assigned_reviews.readable = False
    db.submission.n_completed_reviews.readable = False
    db.submission.n_rejected_reviews.readable = False
    if c.allow_link_submission:
        db.submission.link.readable = True
    # Produces the form.
    form = SQLFORM(db.submission, record=subm, upload=URL('download_manager', args=[subm.id]),
                   deletable=False)
    old_feedback_key = subm.feedback
    form.vars.feedback = keystore_read(old_feedback_key)
    if form.process(onvalidation=update_feedback_to_keystore(old_feedback_key)).accepted:
        session.flash = T('The feedback has been updated.')
        redirect(URL('feedback', 'view_feedback', args=['s', subm.id]))
    return dict(form=form)


def update_feedback_to_keystore(old_key):
    def f(form):
        """Inserts/updates the feedback on a submission."""
        k = keystore_update(old_key, form.vars.feedback)
        form.vars.feedback = k
    return f


@auth.requires_login()
def download_author():
    # The user must be the owner of the submission.
    subm = db.submission(request.args(0))
    if (subm == None):
        redirect(URL('default', 'index'))
    if subm.user != get_user_email():
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    return my_download(subm.original_filename, subm_content=subm.content)


@auth.requires_login()
def download_manager():
    # The user must be the manager of the venue where the submission occurred.
    subm = db.submission(request.args(0)) or redirect(URL('default', 'index' ))
    # Gets the venue.
    c = db.venue(subm.venue_id)
    if c is None:
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    managers = util.get_list(c.managers)
    if auth.user.email not in managers:
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))        
    return my_download(subm.original_filename, subm_content=subm.content)
        

@auth.requires_login()
def download_viewer():
    """This method allows the download of a submission by someone who has access to
    all the submissions of the venue.  We need to do all access control here."""
    subm = db.submission(request.args(0)) or redirect(URL('default', 'index'))
    c = db.venue(subm.venue_id) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    # Does the user have access to the venue submissions?
    if not access.can_view_submissions(c, props): 
        session.flash(T('Not authorized.'))
        redirect(URL('default', 'index'))
    # Creates an appropriate file name for the submission.
    original_ext = util.get_original_extension(subm.original_filename)
    filename = c.name + '_' + subm.user
    filename += '.' + original_ext
    # Allows the download.
    return my_download(filename, subm_content=s.content)


@auth.requires_login()
def download_reviewer():
    # Checks that the reviewer has access.
    ok, v = access.validate_task(db, request.args(0), get_user_email())
    if not ok:
        session.flash = T(v)
        redirect(URL('default', 'index'))
    (t, s, c) = v
    # Builds the download name for the file.
    if c.submissions_are_anonymized:
        # Get the extension of the original file
        original_ext = util.get_original_extension(s.original_filename)
        if t is None:
            subm_name = 'submission'
        else:
            subm_name = keystore_read(t.submission_name, default='submission')
        file_alias = subm_name + '.' + original_ext
    else:
        file_alias = s.original_filename
    return my_download(file_alias, subm_content=s.content)


DEFAULT_CHUNK_SIZE = 64 * 1024

def my_download(download_filename, subm_content=request.args[-1]):
    """This implements my download procedure that can rename files."""
    if download_filename is None:
        download_filename = 'submission'
    name = subm_content
    items = re.compile('(?P<table>.*?)\.(?P<field>.*?)\..*')\
        .match(name)
    if not items:
        raise HTTP(404)
    (t, f) = (items.group('table'), items.group('field'))
    try:
        field = db[t][f]
    except AttributeError:
        raise HTTP(404)
    try:
        (filename, stream) = field.retrieve(name)
    except IOError:
        raise HTTP(404)
    headers = response.headers
    headers['Content-Type'] = contenttype(name)
    headers['Content-Disposition'] = \
        'attachment; filename="%s"' % download_filename.replace('"','\"')
    return response.stream(stream, chunk_size=DEFAULT_CHUNK_SIZE)
