# -*- coding: utf-8 -*-

import access
import util
import ranker
import gluon.contrib.simplejson as simplejson
from datetime import datetime
import datetime as dates

general_instructions = T("""
    **Ranking:** Rank the submission relative to submissions that you have previously reviewed
    by dragging and dropping submissions into place; the best submission
    should be on top.

    **Grading:** Assign a grade from 0 to 10 to each item
    (floating point grades are allowed).  The grades must reflect the
    ranking.  Assigning the same grade to two different submissions is
    not allowed.

    **Feedback:** Please provide feedback for the submission you are reviewing.
    """)


@auth.requires_signature()
def accept_review():
    """A user is accepting to do a review (notice that the GET is signed).
    Picks a task and adds it to the set of tasks for the user."""
    # Checks the permissions.
    c = db.venue(request.args(0)) or redirect('default', 'index')
    props = db(db.user_properties.user == get_user_email()).select(db.user_properties.venues_can_rate).first()
    if props == None:
        c_can_rate = []
    else:
        c_can_rate = util.get_list(props.venues_can_rate)
    if not (c.rate_constraint == None or c.id in c_can_rate):
        session.flash = T('You cannot rate this venue.')
        redirect(URL('venues', 'rateopen_index'))
    t = datetime.utcnow()
    if not (c.is_active and c.is_approved and c.rate_open_date <= t and c.rate_close_date >= t):
        session.flash = T('This venue is not open for rating.')
        redirect(URL('venues', 'rateopen_index'))
    # The user can rate the venue.
    # Does the user have any pending reviewing tasks for the venue?
    # TODO(luca): rewrite this in terms of completed flag.
    num_open_tasks = db((db.task.user == get_user_email()) &
                        (db.task.venue_id == c.id) &
                        (db.task.is_completed == False)).count()
    if num_open_tasks >= c.max_number_outstanding_reviews:
        session.flash = T('You have too many reviews outstanding for this venue. '
                          'Complete some of them before accepting additional reviewing tasks.')
        redirect(URL('rating', 'task_index'))
        
    while True:
        new_item = ranker.get_item(c.id, get_user_email(),
                                   can_rank_own_submissions=c.can_rank_own_submissions)
        if new_item == None:
            session.flash = T('There are no additional items that can be reviewed.')
            redirect(URL('venues', 'rateopen_index'))
        # Checks that there are no other review tasks for the same user and submission id.
        # This is a safety measure, to prevent bugs caused by get_item.
        already_assigned = db((db.task.user == get_user_email()) & (db.task.submission_id == new_item)).count()
        if already_assigned == 0:
            break
        logger.error("get_item tried to assign twice submission %r to user %r" % (new_item, get_user_email()))
        
    # Creates a reviewing task.
    # To name it, counts how many tasks the user has already for this venue.
    num_tasks = db((db.task.venue_id == c.id) & (db.task.user == get_user_email())).count()
    task_name = (c.name + ' ' + T('Submission') + ' ' + str(num_tasks + 1))[:STRING_FIELD_LENGTH]
    task_name_id = keystore_write(task_name)
    task_id = db.task.insert(submission_id = new_item, venue_id = c.id, submission_name = task_name_id)
    # Increments the number of reviews for the item.
    subm = db.submission(new_item)
    if subm is not None:
        if subm.n_assigned_reviews is None:
            subm.n_assigned_reviews = 1
        else:
            subm.n_assigned_reviews = subm.n_assigned_reviews + 1
        subm.update_record()
    db.commit()
    session.flash = T('A review has been added to your review assignments.')
    redirect(URL('task_index', args=[task_id]))

            
@auth.requires_login()
def task_index():
    # To avoid reading too many times from the db.
    venue_cache = {}

    def get_venue(venue_id):
        venue = venue_cache.get(venue_id)
        if venue is None:
            venue = db.venue(venue_id)
            venue_cache[venue_id] = venue
        return venue

    def open_for_review(r):
        date_now = datetime.utcnow()
        if r.completed_date > date_now:
            venue = get_venue(r.venue_id)
            return date_now < venue.rate_close_date and date_now > venue.rate_open_date
        else:
            return False

    def get_deadline(r):
        venue = get_venue(r.venue_id)
        return str(venue.rate_close_date) + ' UTC'

    def get_venue_name(r):
        venue = get_venue(r.venue_id)
        return venue.name
    
    db.task.completed_date.readable = False
    db.task.submission_name.readable = True
    # The representation below ensures that the text field is not shortened.
    db.task.submission_name.represent = lambda v, r: A(keystore_read(v), _href=URL('submission', 'view_submission', args=['e', r.id]))
    db.task.submission_name.label = T('Submission to review')
    db.task.venue_id.represent = lambda v, r: A(get_venue_name(r), _href=URL('venues', 'view_venue', args=[r.venue_id]))
    db.task.venue_id.readable = True
    db.task.venue_id.label = T('Assignment')
    
    if len(request.args) == 0:
        q = ((db.task.user == get_user_email()) &
             (db.task.is_completed == False))
        title = T('Submissions to review')
        links=[
            dict(header='Review deadline', body = get_deadline),
            ]
    else:
        t = db.task(request.args(0)) or redirect(URL('default', 'index'))
        # The mode if a specific item.
        title = T('Submissions to review')
        q = (db.task.id == t.id)
        links=[
            dict(header='Review deadline', body = get_deadline),
            ]
    grid = SQLFORM.grid(q,
        args=request.args[:1],
        field_id=db.task.id,
        fields=[db.task.submission_name, db.task.venue_id, db.task.assigned_date],
        user_signature=False, searchable=False,
        create=False, editable=False, deletable=False, csv=False, details=False,
        maxtextlength=32,
        links=links
        )
    return dict(title=title, grid=grid)

    
@auth.requires_login()        
def review():
    """Enters the review, and comparisons, for a particular task.
    This also allows to decline a review.
    This can be used both for old, and new, reviews.
    The function is accessed by task id."""

    t = db.task(request.args(0)) or redirect(URL('default', 'index'))
    if t.user != get_user_email():
        session.flash = T('Invalid request.')
        redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()

    # Check that the venue rating deadline is currently open, or that the ranker
    # is a manager or observer.
    venue = db.venue(t.venue_id)
    if ((not access.can_observe(venue, props)) and
        (datetime.utcnow() < venue.rate_open_date or datetime.utcnow() > venue.rate_close_date)):
        session.flash = T('Reviewing for this venue is closed.')
        redirect(URL('venues', 'view_venue', args=[venue.id]))

    # Ok, the task belongs to the user. 
    # Gets the valid comparison for the venue, so we can read the grades.
    last_comparison = db((db.comparison.user == get_user_email())
        & (db.comparison.venue_id == t.venue_id) & (db.comparison.is_valid == True)).select().first()
    if last_comparison == None:
        last_ordering = []
        subm_id_to_nickname = {}
    else:
        last_ordering = util.get_list(last_comparison.ordering)
        try:
            subm_id_to_nickname = simplejson.loads(last_comparison.submission_nicknames)
        except Exception, e:
            logger.warning("Failed to decode submission_nicknames: " +
                           str(last_comparison.submission_nicknames))
            subm_id_to_nickname = {}
    current_list = last_ordering
    if t.submission_id not in last_ordering:
        current_list.append(t.submission_id)

    # Finds the grades that were given for the submissions previously reviewed.
    if last_comparison == None or last_comparison.grades == None:
        str_grades = {}
    else:
        try:
            str_grades = simplejson.loads(last_comparison.grades)
        except Exception, e:
            str_grades = {}
            logger.warning("Grades cannot be read: " + str(last_comparison.grades))
    # Now converts the keys to ints.
    grades = {}
    for k, v in str_grades.iteritems():
        try:
            grades[long(k)] = float(v)
        except Exception, e:
            logger.warning("Grades cannot be converted: " + str(k) + ":" + str(v))

    # Reads the data from the past review tasks done by the user.
    sub_info = {}
    keys_to_read = []
    tasks = db((db.task.user == get_user_email()) & (db.task.venue_id == venue.id)).select()
    for st in tasks:
        if st.submission_id in current_list:
            sub_info[st.submission_id] = {
                'name_key': st.submission_name,
                'comm_key': st.comments,
                }
            keys_to_read += [st.submission_name, st.comments]

    # Reads the keys from the datastore. 
    keys_to_read = [x for x in keys_to_read if x is not None]
    key_to_val = keystore_multi_read(keys_to_read)
    for i in sub_info:
        sub_info[i]['name'] = key_to_val.get(sub_info[i]['name_key'], 'Submission')
        sub_info[i]['comm'] = key_to_val.get(sub_info[i]['comm_key'], '')
    
    # ---qui---
    
    
        
    # We create a submission_id to line mapping, that will be passed in json to the view.
    submissions = {}
    for i in last_ordering:
        short_comments = util.shorten(sub_info[i]['comm'])
        line = SPAN(A(sub_info[i]['name'], 
                      _href=URL('submission', 'view_submission', args=['e', st.id])), 
                    " (Comments: ", short_comments, ") ")
        submissions[i] = line 

    # Adds also the last submission.
    line = A(sub_info[t.submission_id]['name'], 
             _href=(URL('submission', 'view_submission', args=['e', t.id])))
    submissions[t.submission_id] = line
    this_submission_name = sub_info[t.submission_id]['name']
            
    # Used to check each draggable item and determine which one we should
    # highlight (because its the current/new record).
    new_comparison_item = t.submission_id

    form = SQLFORM.factory(
        Field('unable_to_evaluate', 'boolean', default=False, 
              comment=T('Check this box if you are unable to evaluate fairly this submission.'
                        'If the submission is incomplete or incorrect, please do not '
                        'check this box: rather, enter an evaluation.')),
        Field('comments', 'text', requires=IS_LENGTH(minsize=16, maxsize=MAX_TEXT_LENGTH), comment=T('Please enter a review for the submission, or explain why you are unable to review it (at least 16 characters).')),
        hidden=dict(order='', grades='')
        )
    form.vars.comments = sub_info[t.submission_id]['comm']
    form.vars.unable_to_evaluate = t.rejected

    if form.process(onvalidation=verify_rating_form(t.submission_id)).accepted:
        # Updates the submission id to nicknames mapping.
        subm = db.submission(t.submission_id)
        subm_id_to_nickname[str(subm.id)] = util.produce_submission_nickname(subm)
        for subm_id in form.vars.order:
            if str(subm_id) not in subm_id_to_nickname:
                # We need the author of the submission.
                subm_id_to_nickname[str(subm_id)] = util.produce_submission_nickname(db.submission(subm_id))
        subm_id_to_nickname_str = simplejson.dumps(subm_id_to_nickname)
        
        # Stores a new comparison, erasing any previous one.
        db.comparison.update_or_insert(
            ((db.comparison.venue_id == t.venue_id) & (db.comparison.user == get_user_email())),
            venue_id = t.venue_id, user = get_user_email(), 
            ordering = form.vars.order, grades = form.vars.grades,
            submission_nicknames = subm_id_to_nickname_str)
        
        # Stores a historical record of the comparison.
        db.comparison_history.insert(
            venue_id = t.venue_id, user = get_user_email(), 
            ordering = form.vars.order, grades = form.vars.grades)

        # Marks the task as done, and inserts the comments.
        comment_id = keystore_update(t.comments, form.vars.comments)
        t.update_record(
            completed_date=datetime.utcnow(), is_completed=True, 
            comments=comment_id, rejected=form.vars.unable_to_evaluate)
        # Updates the number of reviews that the submission has received.
        # I could use some smart differential math, but the self-healing code below is probably safer.
        if subm != None:
            n_completed = 0
            n_rejected = 0
            rows = db(db.task.submission_id == subm.id).select()
            for r in rows:
                if r.is_completed:
                    if r.rejected:
                        n_rejected += 1
                    else:
                        n_completed += 1
            subm.n_completed_reviews = n_completed
            subm.n_rejected_reviews = n_rejected
            subm.update_record()
        
        # Marks that the user has reviewed for this venue.
        props = db(db.user_properties.user == get_user_email()).select(db.user_properties.id, db.user_properties.venues_has_rated).first()
        if props == None:
            db.user_properties.insert(user = get_user_email(),
                                      venues_has_rated = [venue.id])
        else:
            has_rated = util.get_list(props.venues_has_rated)
            has_rated = util.list_append_unique(has_rated, venue.id)
            props.update_record(venues_has_rated = has_rated)

        # Calling ranker.py directly.
        ranker.process_comparison(t.venue_id, get_user_email(),
                                  form.vars.order[::-1], t.submission_id)
        db.commit()
        session.flash = T('The review has been submitted.')
        redirect(URL('venues', 'reviewing_duties'))

    return dict(form=form, task=t, 
        submissions = submissions,
        grades = grades,
        sub_title = this_submission_name,
        general_instructions = general_instructions,
        venue = venue,
        grading_instructions = MARKMIN(keystore_read(venue.grading_instructions)),
        current_list = current_list,
        new_comparison_item = new_comparison_item,
        )

        
def verify_rating_form(subm_id):
    """Verifies a ranking received from the browser, together with the grades."""
    def validate_rating(form):
        logger.debug("request.vars.order: %r" % request.vars.order)
        logger.debug("request.vars.grades: %r" % request.vars.grades)
        if request.vars.order == None or request.vars.grades == None:
            form.errors.comments = T('Error in the received ranking')
            session.flash = T('Error in the received ranking')
            return
        # Some browsers send the same information twice, both in the URI and in the body. 
        # Web2py then makes a list of those.  In this case, web2py keeps the base element.
        if isinstance(request.vars.order, list):
            logger.warning("The browser sent the ordering both via URI and body")
            if len(request.vars.order) > 0:
                request.vars.order = request.vars.order[0]
            else:
                form.errors.comments = T('Error in the received ranking')
                session.flash = T('Error in the received ranking')
                return
        if isinstance(request.vars.grades, list):
            logger.warning("The browser sent the grades both via URI and body")
            if len(request.vars.grades) > 0:
                request.vars.grades = request.vars.grades[0]
            else:
                form.errors.comments = T('Error in the received ranking')
                session.flash = T('Error in the received ranking')
                return
                
        # Verifies the order.
        try:
            decoded_order = [int(x) for x in request.vars.order.split()]
            for i in decoded_order:
                if i != subm_id:
                    # This must correspond to a previously done task.
                    mt = db((db.task.submission_id == i) &
                            (db.task.user == get_user_email())).select().first()
                    if mt == None or mt.completed_date > datetime.utcnow():
                        form.errors.comments = T('Corruputed data received')
                        session.flash = T('Corrupted data received')
                        break
        except ValueError:
            form.errors.comments = T('Error in the received ranking')
            session.flash = T('Error in the received ranking')
            return
        # If the review is declined, removes the submission from the ordering.
        if form.vars.unable_to_evaluate and subm_id in decoded_order:
            decoded_order.remove(subm_id)
        # Copies the decoded order for output.
        form.vars.order = decoded_order
        
        # Decodes the grades.
        try:
            rough_grades = simplejson.loads(request.vars.grades)
        except Exception, e:
            form.errors.comments = T('Error in the received grades')
            session.flash = T('Error in the received grades')
            return
        decoded_grades = {}
        for (s, g) in rough_grades.iteritems():
            try:
                logger.debug("Trying to decode: " + str(s))
                s_id = int(s)
            except Exception, e:
                form.errors.comments = T('Error in the received grades')
                session.flash = T('Error in the received grades')
                return
            # It is ok to leave blank a grade while rejecting the review.
            if s_id == subm_id and form.vars.unable_to_evaluate:
                continue
            if (g is None or g == '' or g.isspace()):
                logger.debug("Grade found empty.")
                form.errors.comments = T('Some grade has been left blank; please fill it in')
                session.flash = T('Error in the received grades')
                return
            try:
                decoded_grades[long(s)] = float(g)
            except Exception, e:
                form.errors.comments = T('Error in the received grades')
                session.flash = T('Error in the received grades')
                return
        
        # If the review is declined, removes the grade from consideration.
        if form.vars.unable_to_evaluate and subm_id in decoded_grades:
            del decoded_grades[subm_id]    
        # Copies the grades in the form variable.
        form.vars.grades = simplejson.dumps(decoded_grades)
        
        # Verifies the grades.
        grade_list = [(float(g), long(s)) for (s, g) in decoded_grades.iteritems()]                    
        for (g, s) in grade_list:
            if g < 0.0 or g > 10.0:
                form.errors.comments = T('Grades should be in the interval [0..10]')
                session.flash = T('Errors in the received grades')
                return
        # Sorts the grades in decreasing order.
        grade_list.sort()
        grade_list.reverse()
        # Checks that there are no duplicate grades.
        if len(grade_list) > 0:
            (prev, _) = grade_list[0]
            for (g, s) in grade_list[1:]:
                if g == prev:
                    form.errors.comments = T('There is a repeated grade: grades need to be unique.')
                    session.flash = T('Errors in the received grades')
                    return
                prev = g
            # Checks that the order of the grades matches the one of the submissions.
            subm_order = [s for (g, s) in grade_list]
            if subm_order != decoded_order:
                form.errors.comments = T('The ranking of the submissions does not reflect the grades.')
                session.flash = T('Errors in the received grades.')
                return
        logger.debug("form.vars.order: " + str(form.vars.order))
        logger.debug("form.vars.grades: " + str(form.vars.grades))
    return validate_rating


@auth.requires_login()
def review_index():
    def get_venue_review_link(r):
        tt = datetime.utcnow()
        if tt >= r.rate_open_date and tt <= r.rate_close_date:
            return A(T('View/edit your reviews'), _class='btn',
                     _href=URL('rating', 'edit_reviews', args=[r.id], user_signature=True))
        else:
            return A(T('View reviews and feedback'), _class='btn',
                     _href=URL('feedback', 'view_my_reviews', args=[r.id]))
        
    props = db(db.user_properties.user == get_user_email()).select().first()
    if props is None:
        q = (db.venue.id == -1)
    else:
        venue_list = util.get_list(props.venues_has_rated)
        q = (db.venue.id.belongs(venue_list))
    db.venue.name.label = T('Assignment')
    db.venue.rate_open_date.readable = db.venue.rate_close_date.readable = False
    grid = SQLFORM.grid(q,
        field_id = db.venue.id,
        fields = [db.venue.name, db.venue.rate_open_date, db.venue.rate_close_date],
        create=False, details=False,
        csv=False, editable=False, deletable=False,
        links=[dict(header=T(''), body = lambda r: get_venue_review_link(r)),
            ],
        )
    return dict(grid=grid)


@auth.requires_signature()
def edit_reviews():
    """This controller lists all the submissions that have been assigned for review, and already 
    reviewed, in this venue, allowing their editing."""
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    tt = datetime.utcnow()
    review_is_open = (tt >= c.rate_open_date and tt <= c.rate_close_date)
    if not review_is_open:
        session.flash = T('Reviewing for this venue is now closed.')
        redirect(URL('default', 'index'))

    # Forms a query that selects the tasks the user has done for the venue.
    q = ((db.task.venue_id == c.id) &
         (db.task.user == get_user_email()) &
         (db.task.is_completed == True))
    db.task.assigned_date.writable = db.task.assigned_date.readable = False
    db.task.completed_date.writable = db.task.completed_date.readable = False
    db.task.rejected.readable = True
    db.task.comments.readable = True
    db.task.submission_name.label = T('Submission')
    db.task.submission_name.represent = lambda v, r: A(keystore_read(v, default="submission"),
        _href=URL('submission', 'view_submission', args=['e', r.id]))
    grid = SQLFORM.grid(
        q,
        csv=False, create=False,
        editable=False, searchable=False, details=False,
        deletable=False, args=request.args[:1],
        links=[
            dict(header = T('Edit Review'),
                 body = lambda r: A(T('Edit'), _class='btn', _href=URL('rating', 'review', args=[r.id])))
            ]
        )
    return dict(grid=grid, venue=c)


@auth.requires_login()
def crowd_grade():
    # Gets the information on the venue.
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_manage(c, props):
        session.flash = T('You cannot evaluate contributors for this venue')
        redirect(URL('default', 'index'))
    if is_user_admin():
        form = SQLFORM.factory(
            Field('algo', default=ALGO_OPT, requires=IS_IN_SET(ALGO_LIST)),
            Field('run_id', default='exp'),
            Field('cost_type', default=ALGO_DEFAULT_COST_TYPE, requires=IS_IN_SET(['linear', 'quadratic'])),
            Field('pos_slope', 'double', default=ALGO_DEFAULT_POS_SLOPE, requires=IS_FLOAT_IN_RANGE(0.0, 1000.0)),
            Field('neg_slope', 'double', default=ALGO_DEFAULT_NEG_SLOPE, requires=IS_FLOAT_IN_RANGE(0.0, 1000.0)),
            Field('normalize_grades', 'boolean', default=ALGO_DEFAULT_NORMALIZE),
            Field('normalization_scale', 'double', default=ALGO_DEFAULT_NORMALIZATION_SCALE, requires=IS_FLOAT_IN_RANGE(0.01, 1000.0)),
            Field('reputation_method', default=ALGO_DEFAULT_REPUTATION_METHOD, requires=IS_IN_SET([ALGO_DEFAULT_REPUTATION_METHOD, 'stdev'])),
            Field('precision_coefficient', 'double', default=ALGO_DEFAULT_PREC_COEFF, requires=IS_FLOAT_IN_RANGE(0.0, 1000.0)),
            Field('use_submission_rank_in_reputation', 'boolean', default=True),
            Field('submission_rank_exponent_for_reputation', 'double', default=ALGO_DEFAULT_RANK_REP_EXP, requires=IS_FLOAT_IN_RANGE(0.1, 10.0)),
            Field('precision_method', default=ALGO_DEFAULT_PREC_METHOD, requires=IS_IN_SET([ALGO_PREC_METHOD_DIST, ALGO_PREC_METHOD_CORR])),
            Field('matrix_D_type', default=MATRIX_D_TYPE_GRADES_DIST, requires=IS_IN_SET([MATRIX_D_TYPE_GRADES_DIST, MATRIX_D_TYPE_GRADES_SINGLE])),
            Field('num_iterations', 'integer', default=ALGO_DEFAULT_NUM_ITERATIONS, requires=IS_INT_IN_RANGE(1, 20)),
            Field('publish', 'boolean', default=False, writable=access.is_real_manager(c, props)),
            )
    else:
        form = FORM.confirm(T('Run'),
            {T('Cancel'): URL('venues', 'view_venue', args=[c.id])})
    # Notice that the confirm form does not need and must not call
    # .accepts or .process because this is done internally (from web2py book).
    if ((is_user_admin() and form.process().accepted) or 
       (not is_user_admin() and form.accepted)):
        if is_user_admin():
            algo = form.vars.algo
            run_id = form.vars.run_id
            cost_type = form.vars.cost_type
            pos_slope = form.vars.pos_slope
            neg_slope = form.vars.neg_slope
            normalize_grades = form.vars.normalize_grades
            normalization_scale = form.vars.normalization_scale
            reputation_method = form.vars.reputation_method
            precision_coefficient = form.vars.precision_coefficient
            use_submission_rank_in_reputation = form.vars.use_submission_rank_in_reputation
            submission_rank_exp = form.vars.submission_rank_exponent_for_reputation
            precision_method = form.vars.precision_method
            num_iterations = form.vars.num_iterations
            publish = form.vars.publish
            matrix_D_type = form.vars.matrix_D_type
        else:            
            algo = ALGO_OPT
            run_id = 'default'
            cost_type = ALGO_DEFAULT_COST_TYPE
            pos_slope = ALGO_DEFAULT_POS_SLOPE
            neg_slope = ALGO_DEFAULT_NEG_SLOPE
            normalize_grades = ALGO_DEFAULT_NORMALIZE
            normalization_scale = ALGO_DEFAULT_NORMALIZATION_SCALE
            reputation_method = ALGO_DEFAULT_REPUTATION_METHOD
            precision_coefficient = ALGO_DEFAULT_PREC_COEFF
            use_submission_rank_in_reputation = True
            submission_rank_exp = ALGO_DEFAULT_RANK_REP_EXP
            precision_method = ALGO_DEFAULT_PREC_METHOD
            num_iterations = ALGO_DEFAULT_NUM_ITERATIONS
            matrix_D_type = MATRIX_D_TYPE_GRADES_DIST
            publish = True
        # Performs the computation.
        return redirect(URL('queues', 'run_rep_sys', vars={
                    REPUTATION_SYSTEM_PARAM_VENUE_ID: c.id,
                    REPUTATION_SYSTEM_ALGO: algo,
                    REPUTATION_SYSTEM_RUN_ID: run_id,
                    REPUTATION_SYSTEM_COST_TYPE: cost_type,
                    REPUTATION_SYSTEM_POS_SLOPE: pos_slope,
                    REPUTATION_SYSTEM_NEG_SLOPE: neg_slope,
                    REPUTATION_SYSTEM_NORMALIZE_GRADES: normalize_grades,
                    REPUTATION_SYSTEM_NORMALIZATION_SCALE: normalization_scale,
                    REPUTATION_SYSTEM_REPUTATION_METHOD: reputation_method,
                    REPUTATION_SYSTEM_PREC_COEFF: precision_coefficient,
                    REPUTATION_SYSTEM_PARAM_REVIEW_PERCENTAGE: c.reviews_as_percentage_of_grade,
                    REPUTATION_SYSTEM_USE_SUBMISSION_RANK_IN_REP: use_submission_rank_in_reputation,
                    REPUTATION_SYSTEM_SUBMISSION_RANK_REP_EXP: submission_rank_exp,
                    REPUTATION_SYSTEM_PREC_METHOD: precision_method,
                    REPUTATION_SYSTEM_PARAM_NUM_ITERATIONS: num_iterations,
                    REPUTATION_SYSTEM_STARTOVER: 'True',
                    REPUTATION_SYSTEM_PUBLISH: publish,
                    REPUTATION_SYSTEM_MATRIX_D_TYPE: matrix_D_type,
                    },
                    user_signature=True))
    venue_link = A(c.name, _href=URL('venues', 'view_venue', args=[c.id]))
    return dict(venue_link=venue_link, confirmation_form=form)
