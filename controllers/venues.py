# -*- coding: utf-8 -*-

import access
import util

DEFAULT_GRADING_INSTRUCTIONS = """
Use the following grading scale:
- 10: Awesome
- 9:
- 8:
- 7:
- 6: Meets expectations.
- 5: 
- 4: 
- 3: 
- 2: Minimal effort in the right direction.
- 1: The submission is present, but there is essentially no work in it.
- 0: Missing submission, no work done, or wrong material submitted.
When grading, please consider:
- Clarity
- Functionality
- Style
"""


@auth.requires_login()
def view_venue():
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    # if c.raters_equal_submitters:
    db.venue.rate_constraint.readable = False
    if props == None and not is_user_admin(): 
        session.flash = T('Not Authorized.')
        redirect(URL('default', 'index'))
    # Checks view permission
    can_submit = access.can_submit(c, props)
    can_rate = access.can_rate(c, props)
    has_submitted = access.has_submitted(c, props)
    has_rated = access.has_rated(c, props)
    can_manage = access.can_manage(c, props)
    can_observe = access.can_observe(c, props)
    can_view_ratings = access.can_view_ratings(c, props)
    # Builds some links that are useful to give out to people.
    submission_link = URL('submission', 'submit', args=[c.id])
    review_link = URL('venues', 'reviewing_duties')
    if not (can_submit or can_rate or has_submitted or has_rated or can_manage or can_observe or can_view_ratings):
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    if can_observe:
        db.venue.grading_instructions.readable = True
    venue_form = SQLFORM(db.venue, record=c, readonly=True)
    link_list = []
    if can_manage:
        link_list.append(A(T('Edit'), _href=URL('venues', 'edit', args=[c.id], user_signature=True)))
    if can_submit:
        link_list.append(A(T('Submit to this venue'), _href=URL('submission', 'submit', args=[c.id])))
    if can_manage:
        link_list.append(A(T('Add submission'), _href=URL('submission', 'manager_submit', args=[c.id])))
    if has_submitted:
        link_list.append(A(T('My submissions'), _href=URL('feedback', 'index', args=[c.id])))
    if can_view_ratings or access.can_view_submissions(c, props):
        link_list.append(A(T('Submissions'), _href=URL('ranking', 'view_submissions', args=[c.id])))
    if can_rate and not can_manage:
        link_list.append(A(T('Review'), _href=URL('rating', 'accept_review', args=[c.id], user_signature=True)))
    if can_observe or can_manage:
        link_list.append(A(T('Comparisons'), _href=URL('ranking', 'view_comparisons_index', args=[c.id])))
    if can_view_ratings:
        link_list.append(A(T('Crowd-grades'), _href=URL('ranking', 'view_grades', args=[c.id])))
    if is_user_admin():
        link_list.append(A(T('Experimental grades'), _href=URL('ranking', 'view_exp_grades', args=[c.id])))
    return dict(form=venue_form, link_list=link_list, venue=c, has_rated=has_rated,
                submission_link=submission_link, review_link=review_link)
        

@auth.requires_login()
def subopen_index():
    props = db(db.user_properties.user == get_user_email()).select(db.user_properties.venues_can_submit).first()
    if props == None: 
        l = []
    else:
        l = util.get_list(props.venues_can_submit)
    t = datetime.utcnow()
    if len(l) == 0:
        q = (db.venue.id == -1)
    else:
        q = ((db.venue.id.belongs(l)) &
             (db.venue.close_date > t) & (db.venue.open_date < t) &
             (db.venue.is_active == True) & (db.venue.is_approved == True) 
             )
    grid = SQLFORM.grid(q,
        field_id=db.venue.id,
        fields=[db.venue.name, db.venue.open_date, db.venue.close_date],
        csv=False, details=False, create=False, editable=False, deletable=False,
        links=[
            dict(header=T('Submit'), body = lambda r: submit_link(r)),
            ],
        maxtextlength=24,
        )
    return dict(grid=grid)

def submit_link(r):
    if r.open_date > datetime.utcnow():
        return T('Not yet open')
    else:
        return A(T('Submit'), _class='btn', _href=URL('submission', 'submit', args=[r.id]))


@auth.requires_login()
def rateopen_index():
    #TODO(luca): see if I can put an inline form for accepting review tasks.
    props = db(db.user_properties.user == get_user_email()).select().first()
    if props == None:
        l = []
    else:
        l = util.get_list(props.venues_can_rate)
    t = datetime.utcnow()
    if len(l) == 0:
        q = (db.venue.id == -1)
    else:
        q = ((db.venue.id.belongs(l)) &
             (db.venue.rate_open_date < t) & (db.venue.rate_close_date > t) &
             (db.venue.is_active == True) & (db.venue.is_approved == True)
             )
    db.venue.rate_close_date.label = T('Review deadline')
    grid = SQLFORM.grid(q,
        field_id=db.venue.id,
        fields=[db.venue.name, db.venue.rate_open_date, db.venue.rate_close_date],
        csv=False, details=False, create=False, editable=False, deletable=False,
        links=[
            dict(header=T('Review'), body = lambda r: review_link(r)),
            ],
        maxtextlength=24,
        )
    return dict(grid=grid)

def review_link(r):
    if r.rate_open_date > datetime.utcnow():
        return T('Reviewing is not yet open')
    else:
        return A(T('Accept reviewing task'), _class='btn',
                 _href=URL('rating', 'accept_review', args=[r.id], user_signature=True))


@auth.requires_login()
def observed_index():
    props = db(db.user_properties.user == get_user_email()).select().first()    
    if props == None: 
        l = []
    else:
        l = util.id_list(util.get_list(props.venues_can_observe))
        l1 = util.id_list(util.get_list(props.venues_can_manage))
        for el in l1:
            if el not in l:
                l.append(el)
    if len(l) > 0:
        q = (db.venue.id.belongs(l) & (db.venue.is_approved == True))
    else:
        q = (db.venue.id == -1)
    db.venue.number_of_submissions_per_reviewer.readable = True
    db.venue.grading_instructions.readable = True
    db.venue.is_approved.readable = True
    grid = SQLFORM.grid(q,
        field_id=db.venue.id,
        fields=[db.venue.name, db.venue.close_date, db.venue.rate_close_date],
        csv=False, details=True, create=False, editable=False, deletable=False,
        maxtextlength=24,
        )
    return dict(grid=grid)

                
@auth.requires_login()
def reviewing_duties():
    """This function lists venues where users have reviews to accept, so that users
    can be redirected to a page where to perform such reviews."""
    # Produces a list of venues that are open for rating.
    props = db(db.user_properties.user == get_user_email()).select(db.user_properties.venues_can_rate).first()
    if props == None:
        l = []
    else:
        l = util.get_list(props.venues_can_rate)
    t = datetime.utcnow()
    if len(l) == 0:
        q = (db.venue.id == -1)
    else:
        q = ((db.venue.rate_open_date < t) & (db.venue.rate_close_date > t)
             & (db.venue.is_active == True) & (db.venue.id.belongs(l)))
    db.venue.rate_close_date.label = T('Review deadline')
    db.venue.number_of_submissions_per_reviewer.label = T('Total n. of reviews')
    grid = SQLFORM.grid(q,
        field_id=db.venue.id,
        fields=[db.venue.name, db.venue.rate_open_date, db.venue.rate_close_date,
                db.venue.number_of_submissions_per_reviewer],
        csv=False, details=False, create=False, editable=False, deletable=False,
        links=[
            dict(header=T('N. reviews still to do'), body = lambda r: get_num_reviews_todo(r)),
            dict(header='Accept', body = lambda r: review_link(r)),
            ],
        maxtextlength=24,
        )
    return dict(grid=grid)


def get_num_reviews_todo(venue):
    if venue.number_of_submissions_per_reviewer == 0 or venue.number_of_submissions_per_reviewer == None:
        return 0
    # See how many reviewing tasks the user has accepted.
    n_accepted_tasks = db((db.task.venue_id == venue.id) &
                          (db.task.user == get_user_email())).count()
    return max(0, venue.number_of_submissions_per_reviewer - n_accepted_tasks)


def view_venue_link(venue_id):
    v = db.venue(venue_id)
    if v == None:
        return ''
    return A(v.name, _href=URL('venues', 'view_venue', args=[venue_id]))


def get_review_deadline(venue_id):
    v = db.venue(venue_id)
    if v == None:
        return ''
    return v.rate_close_date


@auth.requires_login()
def managed_index():
    active_only = True
    if request.vars.all and request.vars.all == 'yes':
        active_only = False
    props = db(db.user_properties.user == get_user_email()).select().first()    
    if props == None:
        managed_venue_list = []
        managed_user_lists = []
    else:
        managed_venue_list = util.get_list(props.venues_can_manage)
        managed_user_lists = util.get_list(props.managed_user_lists)
    logger.info("Managed venue list: %r", managed_venue_list)
    if len(managed_venue_list) > 0:
        if active_only:
            q = (db.venue.id.belongs(managed_venue_list)
                 & (db.venue.is_active == True))
        else:
            q = (db.venue.id.belongs(managed_venue_list))
    else:
        q = (db.venue.id == -1)
    # Admins can see all venues.
    if is_user_admin():
        if active_only:
            q = (db.venue.is_active == True)
        else:
            q = db.venue
    # Deals with search parameter.
    if request.vars.cid and request.vars.cid != '':
        try:
            cid = int(request.vars.cid)
        except ValueError:
            cid = None
        if cid != None and cid in managed_venue_list:
            q = (db.venue.id == cid)
    db.venue.is_approved.readable = True
    links=[
        dict(header=T('Edit'),
             body = lambda r: A(T('Edit'), _class='btn', 
                                _href=URL('venues', 'edit', args=[r.id], user_signature=True))),
        ]
    if is_user_admin():
        db.venue.created_by.readable = True
        db.venue.creation_date.readable = True
        db.venue.is_approved.default = True
        # Useful for debugging.
        db.venue.can_rank_own_submissions.readable = db.venue.can_rank_own_submissions.writable = True
        db.venue.feedback_accessible_immediately.readable = db.venue.feedback_accessible_immediately.writable = True
        fields = [db.venue.name, db.venue.created_by, db.venue.creation_date, db.venue.is_approved, db.venue.is_active]
        links.append(dict(header=T('Delete'),
                          body = lambda r: A(T('Delete'), _class='btn',
                                             _href=URL('venues', 'delete', args=[r.id], user_signature=True))))
    else:
        fields = [db.venue.name, db.venue.creation_date, db.venue.is_approved, db.venue.is_active]
    grid = SQLFORM.grid(q,
        field_id=db.venue.id,
        fields=fields,
        csv=False, details=False,
        create=False, editable=False, deletable=False, 
        links_in_grid=True,
        links=links,
        maxtextlength=24,
        )
    return dict(grid=grid)
    

def set_homework_defaults(bogus):
    """Sets defaults appropriate for most homeworks."""
    db.venue.allow_multiple_submissions.default = False
    # db.venue.allow_multiple_submissions.readable = db.venue.allow_multiple_submissions.writable = False
    db.venue.can_rank_own_submissions.default = False
    # db.venue.can_rank_own_submissions.readable = db.venue.can_rank_own_submissions.writable = False
    db.venue.max_number_outstanding_reviews.default = 1
    db.venue.max_number_outstanding_reviews.readable = db.venue.max_number_outstanding_reviews.writable = False
    db.venue.feedback_is_anonymous.default = True
    db.venue.feedback_is_anonymous.readable = db.venue.feedback_is_anonymous.writable = False
    db.venue.submissions_visible_immediately.default = False
    db.venue.submissions_visible_immediately.readable = db.venue.submissions_visible_immediately.writable = False
    db.venue.feedback_available_to_all.default = False
    db.venue.feedback_available_to_all.readable = db.venue.feedback_available_to_all.writable = False
    db.venue.rating_available_to_all.default = False
    db.venue.rating_available_to_all.readable = db.venue.rating_available_to_all.writable = False
    db.venue.rater_contributions_visible_to_all.default = False
    db.venue.rater_contributions_visible_to_all.readable = db.venue.rater_contributions_visible_to_all.writable = False
    db.venue.latest_grades_date.readable = False
    db.venue.rate_constraint.readable = db.venue.rate_constraint.writable = False
    db.venue.grading_instructions.default = DEFAULT_GRADING_INSTRUCTIONS
    db.venue.grading_instructions.readable = db.venue.grading_instructions.writable = True
    db.venue.reviews_as_percentage_of_grade.writable = True
    db.venue.number_of_submissions_per_reviewer.writable = True
    db.venue.open_date.default = db.venue.close_date.default = None
    db.venue.rate_open_date.default = db.venue.rate_close_date.default = None
    db.venue.grades_released.readable = db.venue.grades_released.writable = False

    
def set_homework_defaults_for_admin(bogus):
    """Sets permissions to edit by an admin who is not a manager."""
    db.venue.max_number_outstanding_reviews.readable = db.venue.max_number_outstanding_reviews.writable = False
    db.venue.feedback_is_anonymous.readable = db.venue.feedback_is_anonymous.writable = False
    db.venue.submissions_visible_immediately.readable = db.venue.submissions_visible_immediately.writable = False
    db.venue.feedback_available_to_all.readable = db.venue.feedback_available_to_all.writable = False
    db.venue.rating_available_to_all.readable = db.venue.rating_available_to_all.writable = False
    db.venue.rater_contributions_visible_to_all.readable = db.venue.rater_contributions_visible_to_all.writable = False
    db.venue.rate_constraint.readable = db.venue.rate_constraint.writable = False
    db.venue.submit_constraint.writable = False
    db.venue.name.writable = False
    db.venue.institution.writable = False
    db.venue.description.writable = False
    db.venue.managers.writable = False
    db.venue.observers.writable = False
    db.venue.open_date.writable = False
    db.venue.close_date.writable = False
    db.venue.rate_open_date.writable = False
    db.venue.rate_close_date.writable = False
    db.venue.allow_link_submission.writable = False
    db.venue.allow_file_upload.writable = False
    db.venue.is_active.writable = False
    db.venue.submission_instructions.writable = False
    db.venue.number_of_submissions_per_reviewer.writable = False
    db.venue.reviews_as_percentage_of_grade.writable = False
    db.venue.grading_instructions.writable = False
    db.venue.grades_released.writable = False
    logger.info("Set the defaults so the grading instructions are not writable.")
            

def add_help_for_venue(bogus):
    # Let's add a bit of help for editing
    db.venue.is_approved.comment = T('Is the assignment approved by the site admins?')
    db.venue.is_active.comment = T('Is the assignment active?')
    db.venue.managers.comment = T('Email addresses of assignment managers.')
    db.venue.observers.comment = T('Email addresses of assignment observers.')
    db.venue.name.comment = T('Name of the assignment.')
    db.venue.institution.comment = T('Your institution.')
    db.venue.open_date.comment = T('In UTC.')
    db.venue.close_date.comment = T('In UTC.')
    db.venue.rate_open_date.comment = T('In UTC.')
    db.venue.rate_close_date.comment = T('In UTC.')
    db.venue.allow_multiple_submissions.comment = T(
        'Allow users to submit multiple independent pieces of work to this venue.')
    db.venue.allow_link_submission.comment = T(
    'Allow the submissions of links.  NOTE: CrowdGrader does not check whether link contents change.')
    db.venue.feedback_accessible_immediately.comment = T(
        'Is the feedback accessible even before the review deadline?')
    db.venue.rating_available_to_all.comment = T(
        'The ratings will be publicly visible.')
    db.venue.feedback_available_to_all.comment = T(
        'The feedback to submissions will be available to all.')
    db.venue.feedback_is_anonymous.comment = T(
        'The identity of users providing feedback is not revealed.')
    db.venue.submissions_are_anonymized.comment = T(
        'The identities of submission authors are not revealed to the raters.')
    db.venue.max_number_outstanding_reviews.comment = T(
        'How many outstanding reviews for this venue can a user have at any given time. '
        'Enter a number between 1 and 100.  The lower, the more accurate the rankings are, '
        'since choosing later which submissions need additional reviews improves accuracy.')
    db.venue.submission_instructions.comment = T(
        'These instructions are shown in the submission page.  Please enter detailed instructions.')
    db.venue.can_rank_own_submissions.comment = T(
        'Allow users to rank their own submissions.  This is used mainly to facilitate '
        'demos and debugging.')
    db.venue.rater_contributions_visible_to_all.comment = T(
        'Allow everybody to see how much the reviewers contributed to the ranking.')
    db.venue.submissions_visible_to_all.comment = (
        'Submissions are visible to all.')
    db.venue.submissions_visible_immediately.comment = T(
        'Submissions are public immediately, even before the submission deadline.')
    db.venue.grading_instructions.comment = T(
        'These instructions are shown when a student enters a review.  You can edit them to reflect '
        'the grading criteria for the assignment.')
    db.venue.number_of_submissions_per_reviewer.comment = T('How many submissions should each student review?')
    db.venue.reviews_as_percentage_of_grade.comment = T('Percentage of overall grade that is determined by the review accuracy of the student.')
    db.venue.allow_file_upload.comment = T('Can students upload a file as part of the submission?')
    db.venue.grades_released.comment = T('The grades have been released to the students.')
    db.venue.submit_constraint.comment = T('List of students who can submit and rate.')
    db.venue.rate_constraint.comment = T('List of students who can submit and rate.')


@auth.requires_login()
def edit():
    """Edits or creates a venue."""
    is_edit = (request.args(0) is not None)
    if is_edit:
        c = db.venue(request.args(0))
        if c is None:
            session.flash = T('No such assignment.')
            redirect(URL('venues', 'managed_index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    if props == None:
        managed_venue_list = []
        managed_user_lists = []
    else:
        managed_venue_list = util.get_list(props.venues_can_manage)
        managed_user_lists = util.get_list(props.managed_user_lists)
    if is_edit and not access.can_manage(c, props):
        session.flash = T('Not authorized.')
        redirect(URL('venues', 'managed_index'))
    is_real_manager = (not is_edit) or (c.id in managed_venue_list)
    logger.info("Is this real manager: %r" % is_real_manager)

    # Sets defaults
    set_homework_defaults(None)
    add_help_for_venue(None)
    if not is_edit:
        # Let's not bother someone who creates a venue with this.
        db.venue.grades_released.readable = db.venue.grades_released.writable = False
    if not is_real_manager:
        set_homework_defaults_for_admin(None)
    # Defaults for approved field.
    default_is_approved = is_user_admin() or IS_VENUE_CREATION_OPEN or get_user_email() in PREAPPROVED_EMAILS
    if not default_is_approved:
        email_parts = get_user_email().split('@')
        default_is_approved = len(email_parts) > 1 and email_parts[1] in PREAPPROVED_DOMAINS
    db.venue.is_approved.default = default_is_approved
    logger.info("User is admin: %r" % is_user_admin())
    if is_user_admin():
        db.venue.is_approved.writable = db.venue.is_approved.readable = True
    else:
        db.venue.is_approved.writable = False
        db.venue.is_approved.readable = False

    # Stores old defaults.
    if is_edit:
        old_managers = c.managers
        old_observers = c.observers
        old_submit_constraint = c.submit_constraint
        old_rate_constraint = c.rate_constraint

    # Define list_q as the query defining which user lists the user manages, OR, the previously existing list.
    allowed_user_lists = managed_user_lists
    if is_edit:
        allowed_user_lists.append(c.submit_constraint)
        allowed_user_lists.append(c.rate_constraint)
    if is_real_manager:
        list_q = (db.user_list.id.belongs(allowed_user_lists))
    elif is_user_admin:
        list_q = (db.user_list)
    else:
        list_q = (db.user_list.id < 0)
    db.venue.submit_constraint.requires = IS_EMPTY_OR(IS_IN_DB(
        db(list_q), 'user_list.id', '%(name)s', zero=T('-- Nobody --')))
    db.venue.rate_constraint.requires = IS_EMPTY_OR(IS_IN_DB(
        db(list_q), 'user_list.id', '%(name)s', zero=T('-- Nobody --')))

    # Generates the editing form.
    if is_edit:
        form = SQLFORM(db.venue, record=c)
        title = T('Edit Assignment')
    else:
        form = SQLFORM(db.venue)
        title = T('Create Assignment')

    # Creates a message to warn if approval will be required.
    if is_edit or default_is_approved:
        message = None
    else:
        message = SPAN(T(
            'You can create an assignment.  However, before the assignment can be used, '
            'it will need to be approved by the crowdgrader.org admins (they will be '
            'notified when the assignment is created).  If you wish to be whitelisted, '
            'please contact the admins at '), A(EMAIL_TO, _href=("mailto:" + EMAIL_TO)))
    
    # If this is an edit, pre-fills in some fields.
    if is_edit and is_real_manager:
        read_info = keystore_multi_read([c.description, c.submission_instructions, c.grading_instructions], default='')
        form.vars.description = read_info.get(c.description)
        form.vars.submission_instructions = read_info.get(c.submission_instructions)
        form.vars.grading_instructions = read_info.get(c.grading_instructions)
        this_venue = c
    else:
        this_venue = None
        
    if form.process(onvalidation=validate_venue(this_venue, True, is_real_manager)).accepted:
        id = form.vars.id
        if is_edit:
            # Do NOT combine these two ifs.
            if is_real_manager:
                # Note that this has to be called ONLY if the edit is done by the real manager.
                # Otherwise, things like form.vars.managers, form.vars.submit_constraint, etc, are None, 
                # and the update_venue code will actually REMOVE access from those people -- even though
                # the people will still be listed as part of the venue.
                update_venue(c.id, form, old_managers, old_observers, old_submit_constraint, old_rate_constraint)
        else:
            create_venue(id, form)
            logger.info("User " + get_user_email() + " created venue: http://www.crowdgrader.org" + URL('venues', 'view_venue', args=[id]))
            
            # Sends email.
            from google.appengine.api import mail
            venue_url =  URL('venues', 'view_venue', args=[id])
            subject = "New assignment created"
            body = ("A new assignment has been created by: " + get_user_email() + "\n" +
                    "Assignment URL: https://crowdgrader.appspot.com" + venue_url)
            mail.send_mail_to_admins(EMAIL_FROM, subject, body)
            
            session.flash = T('The assignment has been created. ')
            if default_is_approved:
                redirect(URL('venues', 'view_venue', args=[id]))
            else:
                redirect(URL('venues', 'venue_was_created', args=[id], user_signature=True))
            
        # Sends the user to look at the newly created or updated venue.
        redirect(URL('venues', 'view_venue', args=[id]))
        
    return dict(form=form, title=title, message=message)


@auth.requires_signature()
def venue_was_created():
    return redirect(URL('venues', 'view_venue', args=[request.args(0)]))
            
            
@auth.requires_signature()
def delete():
    c = db.venue(request.args(0))
    if c is None:
        session.flash = T('No such assignment.')
        redirect(URL('venues', 'managed_index'))
    if not is_user_admin():
        session.flash = T('Not authorized.')
        redirect(URL('venues', 'managed_index'))
    form = FORM.confirm('Delete the assignment', {'Cancel': URL('venues', 'managed_index')})
    if form.accepted:
        # Deletes the text records.
        keystore_delete(c.description)
        keystore_delete(c.submission_instructions)
        keystore_delete(c.grading_instructions)
        # Pre-propagates the deletion
        delete_venue(c.id)
        # Finally, really deletes it.
        db(db.venue.id == c.id).delete()
        db.commit()
        session.flash = T('The assignment has been deleted')
        redirect(URL('venues', 'managed_index'))
    return dict(form=form)


def get_list_members(user_list_id):
    """Utility function to get members of user list."""
    user_list = db.user_list(user_list_id)
    if user_list is None:
        return []
    return util.get_list(user_list.user_list)

    
def validate_venue(c, raters_equal_submitters, is_real_manager):
    def f(form):
        """Validates the form venue, splitting managers listed on the same line."""
        if is_real_manager:
            form.vars.managers = util.normalize_email_list(form.vars.managers)
            form.vars.observers = util.normalize_email_list(form.vars.observers)
            if raters_equal_submitters:
                form.vars.rate_constraint = form.vars.submit_constraint
            if get_user_email() not in form.vars.managers:
                form.vars.managers = [get_user_email()] + form.vars.managers
            # Checks the dates.
            if form.vars.open_date is None:
                form.errors.open_date = T('The date is required.')
            if form.vars.close_date is None:
                form.errors.close_date = T('The date is required.')
            if form.vars.rate_open_date is None:
                form.errors.rate_open_date = T('The date is required.')
            if form.vars.rate_close_date is None:
                form.errors.rate_close_date = T('The date is required.')
            if not (form.errors.open_date or form.errors.close_date or form.errors.rate_open_date or form.errors.rate_close_date):
                if form.vars.close_date < form.vars.open_date:
                    form.errors.close_date = T('The submission deadline must follow the submission opening date.')
                if form.vars.rate_open_date < form.vars.close_date:
                    form.errors.rate_open_date = T('The review start date must follow the submission deadline.')
                if form.vars.rate_close_date < form.vars.rate_open_date:
                    form.errors.rate_close_date = T('The review deadline must follow the review starting date.')
            # If there are no errors, updates the descriptions.
            if not form.errors:
                if c is not None:
                    form.vars.description = keystore_update(c.description, form.vars.description)
                    form.vars.submission_instructions = keystore_update(c.submission_instructions, form.vars.submission_instructions)
                    form.vars.grading_instructions = keystore_update(c.grading_instructions, form.vars.grading_instructions)
                else:
                    form.vars.description = keystore_write(form.vars.description)
                    form.vars.submission_instructions = keystore_write(form.vars.submission_instructions)
                    form.vars.grading_instructions = keystore_write(form.vars.grading_instructions)
            
    return f

def add_venue_to_user_managers(id, user_list):
    for m in user_list:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_manage).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            db.user_properties.insert(user=m, venues_can_manage = [id])
        else:
            l = u.venues_can_manage
            l = util.list_append_unique(l, id)
            db(db.user_properties.user == m).update(venues_can_manage = l)
    db.commit()
        
def add_venue_to_user_observers(id, user_list):
    for m in user_list:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_observe).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            db.user_properties.insert(user=m, venues_can_observe = [id])
        else:
            l = u.venues_can_observe
            l = util.list_append_unique(l, id)
            db(db.user_properties.user == m).update(venues_can_observe = l)
    db.commit()
        
def add_venue_to_user_submit(id, user_list):
    for m in user_list:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_submit).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            db.user_properties.insert(user=m, venues_can_submit = [id])
        else:
            l = u.venues_can_submit
            l = util.list_append_unique(l, id)
            db(db.user_properties.user == m).update(venues_can_submit = l)
    db.commit()
        
def add_venue_to_user_rate(id, user_list):
    for m in user_list:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_rate).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            db.user_properties.insert(user=m, venues_can_rate = [id])
        else:
            l = u.venues_can_rate
            l = util.list_append_unique(l, id)
            db(db.user_properties.user == m).update(venues_can_rate = l)
    db.commit()

def delete_venue_from_managers(id, user_list):
    for m in user_list:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_manage).first()
        if u != None:
            l = util.list_remove(u.venues_can_manage, id)
            db(db.user_properties.user == m).update(venues_can_manage = l)
    db.commit()
       
def delete_venue_from_observers(id, user_list):
    for m in user_list:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_observe).first()
        if u != None:
            l = util.list_remove(u.venues_can_observe, id)
            db(db.user_properties.user == m).update(venues_can_observe = l)
    db.commit()
       
def delete_venue_from_submitters(id, user_list):
    for m in user_list:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_submit).first()
        if u != None:
            l = util.list_remove(u.venues_can_submit, id)
            db(db.user_properties.user == m).update(venues_can_submit = l)
    db.commit()
       
def delete_venue_from_raters(id, user_list):
    for m in user_list:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_rate).first()
        if u != None:
            l = util.list_remove(u.venues_can_rate, id)
            db(db.user_properties.user == m).update(venues_can_rate = l)
    db.commit()
                        
def create_venue(id, form):
    """Processes the creation of a context, propagating the effects."""
    # First, we need to add the context for the new managers.
    add_venue_to_user_managers(id, form.vars.managers)
    add_venue_to_user_observers(id, form.vars.observers)
    # If there is a submit constraint, we need to allow all the users
    # in the list to submit.
    if not util.is_none(form.vars.submit_constraint):
        # We need to add everybody in that list to submit.
        add_venue_to_user_submit(id, get_list_members(form.vars.submit_constraint))
    # If there is a rating constraint, we need to allow all the users
    # in the list to rate.
    if not util.is_none(form.vars.rate_constraint):
        add_venue_to_user_rate(id, get_list_members(form.vars.rate_constraint))
    # Authorizationi message.
    if not is_user_admin():
        session.flash = T('Your assignment has been created. '
                          'Before it can be used, it needs to be approved.')
        
                
def update_venue(id, form, old_managers, old_observers, old_submit_constraint, old_rate_constraint):
    """A venue is being updated.  We need to return a callback for the form,
    that will produce the proper update, taking into account the change in permissions."""
    # Managers.
    add_venue_to_user_managers(id, util.list_diff(form.vars.managers, old_managers))
    delete_venue_from_managers(id, util.list_diff(old_managers, form.vars.managers))
    # Observers.
    add_venue_to_user_observers(id, util.list_diff(form.vars.observers, old_observers))
    delete_venue_from_observers(id, util.list_diff(old_observers, form.vars.observers))
    # Submitters.
    if str(old_submit_constraint) != str(form.vars.submit_constraint):
        # We need to update.
        if old_submit_constraint != None:
            delete_venue_from_submitters(id, get_list_members(old_submit_constraint))
        if not util.is_none(form.vars.submit_constraint):
            user_list = get_list_members(form.vars.submit_constraint)
            add_venue_to_user_submit(id, user_list)
    # Raters.
    if str(old_rate_constraint) != str(form.vars.rate_constraint):
        # We need to update.
        if old_rate_constraint != None:
            delete_venue_from_raters(id, get_list_members(old_rate_constraint))
        if not util.is_none(form.vars.rate_constraint):
            add_venue_to_user_rate(id, get_list_members(form.vars.rate_constraint))
                
def delete_venue(id):
    c = db.venue[id]
    delete_venue_from_managers(id, c.managers)
    delete_venue_from_observers(id, c.observers)
    if c.submit_constraint != None:
        user_list = get_list_members(c.submit_constraint)
        delete_venue_from_submitters(id, user_list)
    if c.rate_constraint != None:
        user_list = get_list_members(c.rate_constraint)
        delete_venue_from_raters(id, user_list)
