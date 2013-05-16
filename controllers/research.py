# -*- coding: utf-8 -*-

import access
import util
import gluon.contrib.simplejson as simplejson
from datetime import datetime
import evaluation
import json

@auth.requires_signature()
def download_research_data():
    """Produces a csv file containing the grades."""
    cid = request.args(0)
    # preapares the headers.
    orig_headers = ['user', 'submission_grade', 'submission_control_grade', 'accuracy',
                    'reputation', 'n_ratings', 'grade', 'assigned_grade']
    experiment_headers = ['subm_grade', 'review_grade', 'reputation', 'grade']
    run_ids = request.vars.run_ids.split(',')
    csv_headers = [h for h in orig_headers]
    csv_headers.append('run_default_rankdiff')
    for rid in run_ids:
        for h in experiment_headers:
            csv_headers.append('run_' + rid + '_' + h)
        csv_headers.append('run_' + rid + '_rankdiff')
            
    # Reads the grades.
    grades_table = db(db.grades.venue_id == cid).select().as_list()
    # Reads the various experimental runs.
    experimental_runs = {}
    for rid in run_ids:
        experimental_runs[rid] = {}
        rs = db((db.grades_exp.venue_id == cid) &
                (db.grades_exp.run_id == rid)).select().as_list()
        for r in rs:
            experimental_runs[rid][r['user']] = r
    
    # Computes the rank differences.
    known_users = [x['user'] for x in grades_table if x['submission_control_grade'] is not None]
    grades = {}
    rank_diff = {}
    grades['default'] = [(x['submission_grade'], x['user'])  for x in grades_table if x['user'] in known_users]
    grades[True] = [(x['submission_control_grade'], x['user']) for x in grades_table if x['user'] in known_users]
    rank_diff['default'] = evaluation.rank_difference(grades[True], grades['default'])
    for rid in run_ids:
        grades[rid] = [(x['subm_grade'], x['user']) for x in experimental_runs[rid].itervalues() if x['user'] in known_users]
        rank_diff[rid] = evaluation.rank_difference(grades[True], grades[rid])
            
    # Prepares the csv writer.
    import cStringIO, csv
    stream = cStringIO.StringIO()
    writer = csv.DictWriter(stream, fieldnames=csv_headers)
    headers = dict((n,n) for n in csv_headers)
    writer.writerow(headers)
    # Writes all the data.
    d = {}
    for r in grades_table:
        # First, we write the data in the row.
        for h in orig_headers:
            d[h] = r[h]
        d['run_default_rankdiff'] = rank_diff['default'].get(r['user'])
        # Then, we also write the extra data due to the experimental runs.
        for rid in run_ids:
            extra_row = experimental_runs[rid].get(r['user'])
            if extra_row is not None:
                for h in experiment_headers:
                    d['run_' + rid + '_' + h] = extra_row[h]
            d['run_' + rid + '_rankdiff'] = rank_diff[rid].get(r['user'])
        # We have all the information; writes the row.
        writer.writerow(d)
    stream.write('\r\n\r\n')
    filename = "assignment_%s" % request.args(0)
    return dict(stream=stream, filename=filename)


@auth.requires_signature()
def evaluate_grades():
    """Evaluates various grading schemes wrt. the assumed truth of the reference grades."""
    c = db.venue(request.args(0))
    cid = c.id
    venue_link = A(T('Return to grades'), _href=URL('ranking', 'view_grades', args=[cid]))
    rows = db(db.grades_exp.venue_id == c.id).select(db.grades_exp.run_id, distinct=True)
    experiment_list = [r.run_id for r in rows]
    # Produces a multiple-choice form, indicating which results one wants to display.
    form = SQLFORM.factory(
        Field('run_ids', 'list:string', requires=IS_IN_SET(experiment_list, multiple=True)),
        )
    if form.process().accepted:
        run_ids = form.vars.run_ids
        # Reads the grades.
        grades_table = db(db.grades.venue_id == cid).select().as_list()
        # Reads the various experimental runs.
        experimental_runs = {}
        for rid in run_ids:
            experimental_runs[rid] = db((db.grades_exp.venue_id == cid) &
                                        (db.grades_exp.run_id == rid)).select().as_list()
        # Filter all of these lists, so that only the users who also have a reference
        # grade are kept.
        known_users = [x['user'] for x in grades_table if x['submission_control_grade'] is not None]
        grades = {}
        grades['default'] = [(x['submission_grade'], x['user'])  for x in grades_table if x['user'] in known_users]
        grades[True] = [(x['submission_control_grade'], x['user']) for x in grades_table if x['user'] in known_users]
        for rid in run_ids:
            grades[rid] = [(x['subm_grade'], x['user']) for x in experimental_runs[rid] if x['user'] in known_users]
        # Computes the qualities of the various runs.
        kt = {}
        s_score = {}
        norm2 = {}
        s_corr = {}
        kt['default'] = evaluation.kendall_tau(grades[True], grades['default'])
        s_score['default'] = evaluation.grade_score(grades[True], grades['default'])
        s_corr['default'] = evaluation.grade_correlation(grades[True], grades['default'])
        norm2['default'] = evaluation.grade_norm2(grades[True], grades['default'])
        for rid in run_ids:
            kt[rid] = evaluation.kendall_tau(grades[True], grades[rid])
            s_score[rid] = evaluation.grade_score(grades[True], grades[rid])
            s_corr[rid] = evaluation.grade_correlation(grades[True], grades[rid])
            norm2[rid] = evaluation.grade_norm2(grades[True], grades[rid])
        all_runs = run_ids + ['default']
        # Reads the run information for the various runs.
        run_info = {}
        for rid in all_runs:
            info = db((db.run_parameters.venue_id == cid) &
                      (db.run_parameters.run_id == rid)).select().first()
            if info is None:
                run_info[rid] = None
            else:
                run_info[rid] = "Date: %s Parameters: %r" % (info.date.isoformat(), info.params)
        # Voila.
        return dict(run_ids=all_runs, kt=kt, s_score=s_score, s_corr=s_corr, norm2=norm2,
                    run_info=run_info, venue_link = venue_link, form=None)
    else:
        return dict(form=form, venue_link=venue_link)
    
    
@auth.requires_signature()
def rerun_evaluations():
    """Evaluates various grading schemes wrt. the assumed truth of the reference grades."""
    c = db.venue(request.args(0))
    cid = c.id
    venue_link = A(T('Return to grades'), _href=URL('ranking', 'view_grades', args=[cid]))
    rows = db(db.grades_exp.venue_id == c.id).select(db.grades_exp.run_id, distinct=True)
    experiment_list = [r.run_id for r in rows]
    # Produces a multiple-choice form, indicating which results one wants to display.
    form = SQLFORM.factory(
        Field('run_ids', 'list:string', requires=IS_IN_SET(experiment_list, multiple=True)),
        )
    if form.process().accepted:
        from google.appengine.api import taskqueue
        run_ids = form.vars.run_ids
        for run_id in run_ids:
            r = db((db.run_parameters.venue_id == cid) & 
                   (db.run_parameters.run_id == run_id)).select().first()
            if r is not None:
                try:
                    params = json.loads(r.params)
                    publish = params[REPUTATION_SYSTEM_PUBLISH]
                    if publish == 'None' or publish == 'False':
                        # We only re-run unpublished runs.
                        q = taskqueue.Queue(REPUTATION_SYSTEM_QUEUE)
                        t = taskqueue.Task(
                            url = REPUTATION_SYSTEM_RUN_URL,
                            params = params
                            )
                        q.add(t)
                        logger.info("Enqueued evaluation %r" % run_id)
                except Exception, e:
                    logger.warning("Something went wrong enqueuing an eval request: %r" % e)
        session.flash = T('The requests have been enqueued')
        return redirect(URL('ranking', 'view_grades', args=[cid]))
    return dict(form=form, venue_link=venue_link)

                   
    