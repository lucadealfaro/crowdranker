# -*- coding: utf-8 -*-

from datetime import datetime
import gluon.contrib.simplejson as simplejson
import util

@auth.requires_login()
def port_comments():
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    comments = db().select(db.comment.ALL)
    for c in comments:
        db((db.task.submission_id == c.submission_id) & (db.task.user_id == c.author)).update(comments = c.content)
    db.commit()
    session.flash = T('Ported comments.')
    redirect(URL('default', 'index'))
    
@auth.requires_login()
def compute_n_reviews():
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    submissions = db().select(db.submission.ALL)
    for s in submissions:
        s.n_assigned_reviews = db((db.task.submission_id == s.id) & (db.task.venue_id == s.venue_id)).count()
        s.n_completed_reviews = db((db.task.submission_id == s.id) & (db.task.venue_id == s.venue_id)
            & (db.task.completed_date < datetime.utcnow())).count()
        s.n_rejected_reviews = db((db.task.submission_id == s.id) & (db.task.venue_id == s.venue_id)
            & (db.task.rejected == False)).count()
        s.update_record()
    db.commit()
    session.flash = T('Fixed numbers of completed reviews')
    redirect(URL('default', 'index'))

@auth.requires_login()
def mark_completed_tasks():
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    tasks = db().select(db.task.ALL)
    for t in tasks:
        if t.completed_date < datetime.utcnow():
            t.update_record(is_completed = True)
        else:
            t.update_record(is_completed = False)
    db.commit()
    session.flash = T('done')
    redirect(URL('default', 'index'))
    
@auth.requires_login()
def create_comparison_nicks():
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    comps = db().select(db.comparison.ALL)
    for comp in comps:
        nicks = {}
        for subm_id in comp.ordering:
            s = db.submission(subm_id)
            if s is not None:
                nicks[subm_id] = util.produce_submission_nickname(s)
        comp.update_record(submission_nicknames = simplejson.dumps(nicks))
    db.commit()
    session.flash = T('done')
    redirect(URL('default', 'index'))
    
@auth.requires_login()
def fix_comparison_validity():
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    comps = db().select(db.comparison.ALL, orderby=~db.comparison.date)
    d = {}
    for comp in comps:
        key = (comp.venue_id, comp.user)
        if key not in d:
            # Latest = valid.
            comp.update_record(is_valid = True)
            d[key] = True
        else:
            # Not latest
            comp.update_record(is_valid = False)
    db.commit()
    session.flash = T('done')
    redirect(URL('default', 'index'))

@auth.requires_login()
def add_grading_instructions():
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    venues = db().select(db.venue.ALL)
    for c in venues:
        c.update_record(grading_instructions = """
Use the following grading scale:
- 10: you already gave awesome to some app, and this one is even better.
- 9: awesome.
- 8: great work, works really well.
- 7: works nicely, meeting the homework requirements.
- 6: meets the homework requirements, but not otherwise remarkable.
- 5: meets the homework requirements, but has some relatively minor mistakes.
- 4: has some noticeable missing functionality, but goes some of the way towards meeting the homework requirements.
- 3: something works.
- 2: does not work.
- 0: spurious submission, out of scope (e.g. wrong homework submitted).
When grading, please consider:
- Functionality. Can it do what it should?
- Usability.  How easy to use it is?  And as a lesser concern, how polished it is?
- Code style.  Is the code readable?  Well factored?  Well commented?""")
    db.commit()
    session.flash = T('done')
    redirect(URL('default', 'index'))
    
def anonimize_all_venues():
    name_dict = {}
    def get_new_name(n):
        if n == 'luca@ucsc.edu' or n == 'mshavlov@ucsc.edu':
            return n
        if n in name_dict:
            return name_dict[n]
        else:
            while True:
                m = util.get_random_id(n_sections=1) + '@example.com'
                if m not in name_dict:
                    break
            name_dict[n] = m
            return m

    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    form = FORM.confirm(T('This will anonymize all venues; the original data WILL BE LOST.'))
    if form.accepted:
        # Builds a dictionary for anonymization.
        new_names = {}
        # Convert user lists.
        rows = db().select(db.user_list.ALL)
        for ul in rows:
            ul.update_record(managers = [get_new_name(x) for x in ul.managers],
                             user_list = [get_new_name(x) for x in ul.user_list])
        # Convert venues.
        rows = db().select(db.venue.ALL)
        for r in rows:
            r.update_record(created_by = get_new_name(r.created_by),
                            managers = [get_new_name(x) for x in r.managers],
                            observers = [get_new_name(x) for x in r.observers])
        # Convert submissions.
        rows = db().select(db.submission.ALL)
        for r in rows:
            r.update_record(user = get_new_name(r.user),
                            title = util.get_random_id(n_sections=1),
                            )
        db.commit()
        # Convert comparisons.
        rows = db().select(db.comparison.ALL)
        for r in rows:
            # Creates a new nickname dictionary.
            nicks = {}
            for subm_id in r.ordering:
                s = db.submission(subm_id)
                if s is not None:
                    nicks[subm_id] = util.produce_submission_nickname(s)
            r.update_record(user = get_new_name(r.user),
                            submission_nicknames = simplejson.dumps(nicks))
        # Converts tasks.
        rows = db().select(db.task.ALL)
        for r in rows:
            r.update_record(user = get_new_name(r.user))
        # Converts final grades.
        rows = db().select(db.grades.ALL)
        for r in rows:
            r.update_record(user = get_new_name(r.user))
        db.commit()

        # Now for the hard part: the system tables.
        rows = db().select(db.auth_user.ALL)
        for r in rows:
            u = get_new_name(r.email)
            r.update_record(first_name = u,
                            last_name = u,
                            email = u,
                            password = db.auth_user.password.requires[0]('hello')[0])
        db.commit()
        
        session.flash = T('done')
        redirect(URL('default', 'index'))
    return dict(form=form)

def delete_users_passwords():
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    form = FORM.confirm(T('This will change users\' passwords; the original data WILL BE LOST.'))
    if form.accepted:
        ## Fetch a set of users which passwords we don't want to change.
        #important_user_set = set()
        #rows = db().select(db.venue.ALL)
        #for v in rows:
        #    manager_list = util.get_list(v.managers)
        #    observers_list = util.get_list(v.observers)
        #    important_user_set = important_user_set.union(set(manager_list)
        #    important_user_set = important_user_set.union(set(observers_list)
        # Now changing passwords.
        rows = db().select(db.auth_user.ALL)
        for r in rows:
            #u = r.email
            #if not u in important_user_set:
            r.update_record(password = db.auth_user.password.requires[0]('hello')[0])
        db.commit()
        session.flash = T('done')
        redirect(URL('default', 'index'))
    return dict(form=form)
        
@auth.requires_login()
def migrate_to_key_value_store():
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    # Submission table.
    submissions = db().select(db.submission.ALL)
    for row in submissions:
        # comment field.
        key = keystore_write(row.comment)
        row.comment = key
        # feedback field.
        key = keystore_write(row.feedback)
        row.feedback = key
        row.update_record()
    # Task table.
    tasks = db().select(db.task.ALL)
    for row in tasks:
        # submission_name field.
        key = keystore_write(row.submission_name)
        row.submission_name = key
        # comments field.
        key = keystore_write(row.comments)
        row.comments = key
        # feedback field.
        key =  keystore_write(row.why_bogus)
        row.feedback = key
        # helpfulness field.
        if row.is_bogus:
            row.helpfulness = "-2"
        else:
            row.helpfulness = "0"
        row.update_record()
    # Venue table
    venues = db().select(db.venue.ALL)
    for row in venues:
        # description field.
        key = keystore_write(row.description)
        row.description = key
        # submission_instructions field.
        key = keystore_write(row.submission_instructions)
        row.submission_instructions = key
        # grading_instructions field.
        key = keystore_write(row.grading_instructions)
        row.grading_instructions = key
        row.update_record()
    db.commit()
    session.flash = T('Migration to key-value store is done')
    redirect(URL('default', 'index'))

def set_default_venue_reviews_as_percentage_of_grade():
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    rows = db().select(db.venue.ALL)
    for r in rows:
        r.update_record(reviews_as_percentage_of_grade = 25)
    db.commit()
    session.flash = T('done')
    redirect(URL('default', 'index'))

@auth.requires_login()
def fix_evaluation_params():
    def fix(params):
        try:
            if len(params) > 10 and params[:8] == "<Storage":
                ps = params[8:-1].replace("'", '"')
                pj = simplejson.loads(ps)
                return simplejson.dumps(pj)
            else:
                return params
        except Exception, e:
            logging.info("Exception: %r" % e)
            return params
    if not is_user_admin():
        session.flash = T('Not authorized')
        redirect(URL('default', 'index'))
    rows = db().select(db.run_parameters.ALL)
    for r in rows:
        r.update_record(params = fix(r.params))
    db.commit()
    session.flash = T('done')
    redirect(URL('default', 'index'))
    