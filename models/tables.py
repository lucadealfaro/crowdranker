# coding: utf8
from datetime import datetime
import datetime as dates # Ah, what a mess these python names
import gluon.contrib.simplejson as simplejson

STRING_FIELD_LENGTH = 255 # Default length of string fields.
MAX_TEXT_LENGTH = 786432
MAX_DATE = datetime(dates.MAXYEAR, 12, 1)
MAX_GRADE = 10.0
current.MAX_GRADE = MAX_GRADE

REVIEW_HELPFULNESS_LIST = [
    ('-2', '-2 : Factually wrong, bogus'),
    ('-1', '-1 : Unhelpful'),
    ('0', ' 0 : Neutral'),
    ('1', '+1 : Somewhat helpful'),
    ('2', '+2 : Very helpful'),                        
    ]

db.auth_user._format='%(email)s'

db.define_table('user_list',
    Field('name', length=STRING_FIELD_LENGTH),
    Field('creation_date', 'datetime', default=datetime.utcnow()),
    Field('managers', 'list:string'),
    Field('user_list', 'list:string'), 
    #TODO(luca): add a 'managed' field, and a table of users,
    # to allow managing very large sets of users via an API.
    format = '%(name)s',
    )

def represent_user_list(v, r):
    ul = db.user_list(v)
    if ul is None:
        return A(T('Nobody'), _href=URL('user_lists', 'index', user_signature=True))
    else:
        return A(ul.name, _href=URL('user_lists', 'index',
                                    args=['view', 'user_list', v], user_signature=True))


db.user_list.id.readable = db.user_list.id.writable = False
db.user_list.creation_date.writable = db.user_list.creation_date.readable = False 
db.user_list.name.required = True   
db.user_list.user_list.requires = [IS_LIST_OF(IS_EMAIL())]
db.user_list.managers.requires = [IS_LIST_OF(IS_EMAIL())]
db.user_list.user_list.label = 'Students'

db.define_table('user_properties',
    Field('user'), # Primary key
    Field('managed_user_lists', 'list:reference user_list'),
    Field('venues_can_manage', 'list:reference venue'),
    Field('venues_can_observe', 'list:reference venue'),
    Field('venues_can_submit', 'list:reference venue'),
    Field('venues_can_rate', 'list:reference venue'),
    Field('venues_has_submitted', 'list:reference venue'),
    Field('venues_has_rated', 'list:reference venue'),
    # List of venues where the user has redone reviews.
    # If the user do it twice then venue_id appears twice in the list.
    Field('venues_has_re_reviewed', 'list:reference venue'),
    )

db.user_properties.user.required = True


db.define_table('venue',
    Field('name', length=STRING_FIELD_LENGTH),
    Field('institution', length=STRING_FIELD_LENGTH, required=True),
    Field('description', 'text'), # key for keystore
    Field('creation_date', 'datetime', default=datetime.utcnow()),
    Field('created_by', default=get_user_email()),
    Field('managers', 'list:string'),
    Field('observers', 'list:string'),
    Field('submit_constraint', db.user_list, ondelete='SET NULL'),
    Field('rate_constraint', db.user_list, ondelete='SET NULL'),
    Field('raters_equal_submitters', 'boolean', default=True),
    Field('open_date', 'datetime', required=True),
    Field('close_date', 'datetime', required=True),
    Field('rate_open_date', 'datetime', required=True),
    Field('rate_close_date', 'datetime', required=True),
    Field('allow_multiple_submissions', 'boolean', default=False),
    Field('submission_instructions', 'text'), # key for keystore
    Field('allow_link_submission', 'boolean', default=False),
    Field('allow_file_upload', 'boolean', default=True),
    Field('is_active', 'boolean', required=True, default=True),
    Field('is_approved', 'boolean', required=True, default=False),
    Field('submissions_are_anonymized', 'boolean', default=True),
    Field('can_rank_own_submissions', 'boolean', default=False),
    Field('max_number_outstanding_reviews', 'integer', default=1),
    Field('feedback_is_anonymous', 'boolean', default=True),
    Field('submissions_visible_to_all', 'boolean', default=False),
    Field('submissions_visible_immediately', 'boolean', default=False),
    Field('feedback_accessible_immediately', 'boolean', default=False),
    Field('feedback_available_to_all', 'boolean', default=False),
    Field('rating_available_to_all', 'boolean', default=False),
    Field('rater_contributions_visible_to_all', default=False),
    Field('number_of_submissions_per_reviewer', 'integer', default=6),
    Field('reviews_as_percentage_of_grade', 'float', default=25),
    Field('latest_grades_date', 'datetime'),
    Field('grades_released', 'boolean', default=False),
    Field('ranking_algo_description', length=STRING_FIELD_LENGTH),
    Field('grading_instructions', 'text'), # key for keystore
    format = '%(name)s',
    )

def represent_venue_name(v, r):
    return A(v, _href=URL('venues', 'view_venue', args=[r.id]))

def represent_venue_id(v, r):
    venue = db.venue(v)
    if venue is None:
        return 'None'
    return A(venue.name, _href=URL('venues', 'view_venue', args=[venue.id]))

def represent_date(v, r):
    if v == MAX_DATE or v is None:
        return ''
    return v.strftime('%Y-%m-%d %H:%M:%S UTC')

def represent_text_field(v, r):
    s = keystore_read(v)
    if s is None:
        return ''
    else:
        return MARKMIN(s)
    
def represent_plain_text_field(v, r):
    s = keystore_read(v)
    if s is None:
        return ''
    else:
        return s

def represent_percentage(v, r):
    if v is None:
        return 'None'
    return ("%3.0f%%" % v)

def represent_01_as_percentage(v, r):
    if v is None:
        return 'None'
    return ("%3.0f%%" % (v * 100))

def represent_quality(v, r):
    if v is None:
        return 'None'
    return ("%.2f" % v)

def represent_quality_10(v, r):
    if v is None:
        return 'None'
    return ("%.2f" % (v * 10.0))

db.venue.description.represent = represent_text_field
db.venue.created_by.readable = db.venue.created_by.writable = False
db.venue.submit_constraint.represent = represent_user_list
db.venue.rate_constraint.represent = represent_user_list
db.venue.name.label = T('Assignment')
db.venue.name.represent = represent_venue_name
db.venue.name.required = True
db.venue.name.requires = IS_LENGTH(minsize=16)
db.venue.grading_instructions.readable = db.venue.grading_instructions.writable = False
db.venue.grading_instructions.represent = represent_text_field
db.venue.is_approved.writable = False
db.venue.creation_date.writable = db.venue.creation_date.readable = False
db.venue.creation_date.represent = represent_date
db.venue.id.readable = db.venue.id.writable = False
db.venue.is_active.label = 'Active'
db.venue.submit_constraint.label = 'List of students'
db.venue.raters_equal_submitters.readable = db.venue.raters_equal_submitters.writable = False
db.venue.rate_constraint.label = 'Who can rate'
db.venue.open_date.label = 'Submission opening date'
db.venue.open_date.default = datetime.utcnow()
db.venue.close_date.label = 'Submission deadline'
db.venue.close_date.default = datetime.utcnow()
db.venue.rate_open_date.label = 'Reviewing start date'
db.venue.rate_open_date.default = datetime.utcnow()
db.venue.rate_close_date.label = 'Reviewing deadline'
db.venue.rate_close_date.default = datetime.utcnow()
db.venue.max_number_outstanding_reviews.requires = IS_INT_IN_RANGE(1, 100,
    error_message=T('Enter a number between 0 and 100.'))
db.venue.max_number_outstanding_reviews.readable = db.venue.max_number_outstanding_reviews.writable = False
db.venue.latest_grades_date.writable = False
db.venue.ranking_algo_description.writable = False
db.venue.ranking_algo_description.readable = False
db.venue.number_of_submissions_per_reviewer.writable = False
db.venue.submission_instructions.represent = represent_text_field
db.venue.submissions_are_anonymized.readable = db.venue.submissions_are_anonymized.writable = False
db.venue.allow_multiple_submissions.readable = db.venue.allow_multiple_submissions.writable = False
db.venue.feedback_available_to_all.default = False
db.venue.feedback_available_to_all.readable = db.venue.feedback_available_to_all.writable = False
db.venue.submissions_visible_immediately.default = False
db.venue.submissions_visible_immediately.readable = db.venue.submissions_visible_immediately.writable = False
db.venue.can_rank_own_submissions.readable = db.venue.can_rank_own_submissions.writable = False
db.venue.submissions_visible_to_all.readable = db.venue.submissions_visible_to_all.writable = False
db.venue.can_rank_own_submissions.readable = db.venue.can_rank_own_submissions.writable = False
db.venue.feedback_accessible_immediately.readable = db.venue.feedback_accessible_immediately.writable = False
db.venue.feedback_is_anonymous.readable = db.venue.feedback_is_anonymous.writable = False
db.venue.rating_available_to_all.readable = db.venue.rating_available_to_all.writable = False
db.venue.rater_contributions_visible_to_all.readable = db.venue.rater_contributions_visible_to_all.writable = False
db.venue.reviews_as_percentage_of_grade.writable = False
db.venue.reviews_as_percentage_of_grade.requires = IS_FLOAT_IN_RANGE(0, 100, 
    error_message=T('Please enter a percentage between 0 and 100.'))
db.venue.reviews_as_percentage_of_grade.represent = represent_percentage
db.venue.open_date.represent = db.venue.close_date.represent = represent_date
db.venue.rate_open_date.represent = db.venue.rate_close_date.represent = represent_date
db.venue.grades_released.readable = db.venue.grades_released.writable = False

db.define_table('submission',
    Field('user', default=get_user_email()),
    Field('date_created', 'datetime'),
    Field('date_updated', 'datetime'),
    Field('venue_id', db.venue),
    Field('original_filename', length=STRING_FIELD_LENGTH),
    Field('content', 'upload'),
    Field('link', length=512),
    Field('comment', 'text'), # Key to keystore. Of the person doing the submission.
    Field('quality', 'double'), # Of active learning algo, to assign submissions.
    Field('error', 'double'),   # Of active learning algo, to assign submissions.
    Field('true_quality', 'double'), # DEPRECATED. Grade by TA/instructor.
    Field('percentile', 'double'), # DEPRECATED.
    Field('n_assigned_reviews', 'integer', default=0),
    Field('n_completed_reviews', 'integer', default=0),
    Field('n_rejected_reviews', 'integer', default=0),
    Field('feedback', 'text'), # Key to keystore. Of a TA, grader, etc.  Visible to students.
    )
    
db.submission.user.label = T('Student')
db.submission.id.readable = db.submission.id.writable = False
db.submission.user.writable = False
db.submission.date_created.default = datetime.utcnow()
db.submission.date_created.represent = represent_date
db.submission.date_updated.default = datetime.utcnow()
db.submission.date_updated.represent = represent_date
db.submission.date_created.writable = False
db.submission.date_updated.writable = False
db.submission.original_filename.readable = db.submission.original_filename.writable = False
db.submission.venue_id.readable = db.submission.venue_id.writable = False
db.submission.venue_id.label = T('Assignment')
db.submission.venue_id.represent = represent_venue_id
db.submission.quality.readable = db.submission.quality.writable = False
db.submission.error.readable = db.submission.error.writable = False
db.submission.link.readable = db.submission.link.writable = False
db.submission.link.requires = IS_URL()
db.submission.n_assigned_reviews.writable = db.submission.n_assigned_reviews.readable = False
db.submission.n_completed_reviews.writable = False
db.submission.n_completed_reviews.label = T('Reviews with eval')
db.submission.n_rejected_reviews.writable = False
db.submission.n_rejected_reviews.label = T('Reviews w/o eval')
db.submission.feedback.label = T('Instructor Feedback')
db.submission.quality.represent = represent_quality
db.submission.error.represent = represent_quality
db.submission.comment.represent = represent_text_field
db.submission.comment.label = T('Content')
db.submission.feedback.represent = represent_text_field
db.submission.feedback.label = T('Instructor feedback')
db.submission.content.label = T('File upload')
db.submission.link.represent = lambda v, r: A(v, _href=v)

# Remove when deprecating.
db.submission.percentile.readable = db.submission.percentile.writable = False
db.submission.percentile.represent = represent_percentage
db.submission.true_quality.readable = db.submission.true_quality.writable = False
db.submission.true_quality.label = T('Control Grade')

def represent_double3(v, r):
    if v is None:
        return 'None'
    return ("%.3f" % v)

def represent_grades(v, r, breaker=BR()):
    if v is None:
        return 'None'
    try:
        d = simplejson.loads(v)
        id_to_nicks = simplejson.loads(r.submission_nicknames)
        l = []
        sorted_sub = []
        for k, w in d.iteritems():
            sorted_sub.append((int(k), float(w)))
        sorted_sub = sorted(sorted_sub, key = lambda el : el[1], reverse = True)
        for k, w, in sorted_sub:
            nick = id_to_nicks.get(str(k), '???')
            l.append(SPAN(A(nick, _href=URL('feedback', 'view_feedback', args=['s', k])),
                          SPAN(':  '), '{:5.2f}'.format(w), breaker))
        attributes = {}
        return SPAN(*l, **attributes)
    except Exception, e:
        return '-- data error --'

def represent_grades_compact(v, r):
    return represent_grades(v, r, breaker='; ')

db.define_table('comparison', # An ordering of submissions, from Best to Worst.
    Field('user', default=get_user_email()),
    Field('date', 'datetime', default=datetime.utcnow()),
    Field('venue_id', db.venue),
    Field('ordering', 'list:reference submission'),
    Field('grades', length=512), # This is a json dictionary of submission_id: grade
    Field('submission_nicknames', length=256), # This is a json dictionary mapping submission ids into strings for visualization
    Field('is_valid', 'boolean', default=True),
    )

def represent_ordering(v, r):
    if v is None:
        return ''
    try:
        id_to_nicks = simplejson.loads(r.submission_nicknames)
        urls = [SPAN(A(str(id_to_nicks.get(str(el), '')),
                           _href=URL('feedback', 'view_feedback', args=['s', el])), ' ')
                for el in v]
        attributes = {}
        return SPAN(*urls, **attributes)
    except Exception, e:
        return '-- data error --'

db.comparison.user.label = T('Student')
db.comparison.grades.represent = represent_grades_compact
db.comparison.venue_id.represent = represent_venue_id
db.comparison.venue_id.label = T('Assignment')
db.comparison.submission_nicknames.readable = db.comparison.submission_nicknames.writable = False
db.comparison.ordering.represent = represent_ordering
db.comparison.date.represent = represent_date
db.comparison.is_valid.readable = False

# Similar to above, but used for logging of comparison events.
db.define_table('comparison_history', 
    Field('user', default=get_user_email()),
    Field('date', 'datetime', default=datetime.utcnow()),
    Field('venue_id', db.venue),
    Field('ordering', 'list:reference submission'),
    Field('grades', length=512), # This is a json dictionary of submission_id: grade
    )


def represent_helpfulness(v, r):
    if v is None:
        return ''
    try:
        i = int(v)
    except Exception, e:
        return v
    return "%+02d" % i
    
db.define_table('task', # Tasks a user should complete for reviewing.
    Field('user', default=get_user_email()),
    Field('submission_id', db.submission),
    Field('venue_id', db.venue),
    Field('submission_name'), # Key to keystore.  Name of the submission from the point of view of the user.
    Field('assigned_date', 'datetime', default=datetime.utcnow()),
    Field('completed_date', 'datetime', default=MAX_DATE),
    Field('is_completed', 'boolean', default=False),
    Field('rejected', 'boolean', default=False),
    Field('comments', 'text'), # Key to keystore.  This is the review.
    Field('grade', 'double'), # This is the grade that the student assigned.
    Field('helpfulness'),
    Field('feedback', 'text'), # Key to keystore.  This is the feedback to the review.
    )

db.task.user.label = T('Student')
db.task.id.readable = db.task.id.writable = False
db.task.user.readable = db.task.user.writable = False
db.task.submission_id.readable = db.task.submission_id.writable = False
db.task.venue_id.readable = db.task.venue_id.writable = False
db.task.assigned_date.writable = False
db.task.assigned_date.label = T('Date review assigned')
db.task.completed_date.writable = False
db.task.is_completed.writable = db.task.is_completed.readable = False
db.task.submission_name.writable = False
db.task.submission_name.represent = represent_plain_text_field
db.task.rejected.readable = db.task.rejected.writable = False
db.task.comments.readable = db.task.comments.writable = False
db.task.comments.represent = represent_text_field
db.task.comments.label = T('Reviewer comments')
db.task.rejected.label = T('Declined to evaluate')
db.task.helpfulness.readable = db.task.helpfulness.writable = False
db.task.feedback.readable = db.task.feedback.writable = False
db.task.feedback.represent = represent_text_field
db.task.feedback.label = T('Review feedback')
db.task.helpfulness.label = T('Review helpfulness')
db.task.venue_id.label = T('Assignment')
db.task.venue_id.represent = represent_venue_id
db.task.assigned_date.represent = represent_date
db.task.completed_date.represent = represent_date
db.task.helpfulness.requires = IS_IN_SET(REVIEW_HELPFULNESS_LIST)
db.task.helpfulness.represent = represent_helpfulness
db.task.grade.readable = db.task.grade.writable = False


db.define_table('grades',
    Field('venue_id', db.venue, required=True),
    Field('user', required=True),
    Field('submission_grade', 'double'), # Computed crowd-grade
    Field('submission_percentile', 'double'), # Quality percentile of submission.
    Field('submission_control_grade', 'double'), # Assigned by a TA by reviewing the submission.
    Field('accuracy', 'double'), # "reviewer" grade
    Field('accuracy_percentile', 'double'),
    Field('reputation', 'double'), # For our info.
    Field('n_ratings', 'integer'),
    Field('grade', 'double'), # Algo-assigned final grade.
    Field('percentile', 'double'), # Percentile of the final grade
    Field('assigned_grade', 'double'), # Assigned by instructor, due to percentile.
    )

db.grades.id.readable = db.grades.id.writable = False
db.grades.percentile.represent = represent_percentage
db.grades.submission_grade.writable = False
db.grades.submission_grade.represent = represent_quality
db.grades.submission_grade.label = T('Submission crowd-grade')
db.grades.submission_percentile.label = T('Submission %')
db.grades.submission_percentile.represent = represent_percentage
db.grades.submission_percentile.writable = False
db.grades.user.writable = False
db.grades.venue_id.represent = represent_venue_id
db.grades.venue_id.label = T('Assignment')
db.grades.venue_id.writable = False
db.grades.accuracy.represent = represent_01_as_percentage
db.grades.accuracy.writable = False
db.grades.accuracy_percentile.represent = represent_percentage
db.grades.accuracy_percentile.writable = False
db.grades.reputation.represent = represent_percentage
db.grades.assigned_grade.label = "Final grade"
db.grades.assigned_grade.represent = represent_quality
db.grades.n_ratings.writable = False
db.grades.reputation.readable = db.grades.reputation.writable = False
db.grades.percentile.label = T('Overall percentile')
db.grades.percentile.writable = False
db.grades.grade.writable = False
db.grades.grade.label = T('Overall crowd-grade')
db.grades.percentile.label = T('Overall %')
db.grades.grade.represent = represent_quality
db.grades.submission_control_grade.readable = db.grades.submission_control_grade.writable = False
db.grades.submission_control_grade.represent = represent_quality
db.grades.submission_control_grade.label = T('Control grade')

# This table stores experimental grades for submissions, derived with 
# experimental algorithms.
db.define_table('grades_exp',
    Field('venue_id', db.venue, required=True),
    Field('user', required=True),
    Field('run_id'),
    Field('subm_grade', 'double'), # Algo grade of submission
    Field('subm_percent', 'double'), # Algo percentile of submission
    Field('subm_confidence', 'double'), # Confidence in algo grade of submission
    Field('review_grade', 'double'), 
    Field('review_percent', 'double'),
    Field('n_ratings', 'integer'),
    Field('reputation', 'double'),
    Field('grade', 'double'), # Final grade of student in assignment.
    )

# This table stores information about experimental runs.
db.define_table('run_parameters',
    Field('venue_id', db.venue, required=True),
    Field('run_id'),
    Field('params', 'text'), # Parameters of the run.
    Field('date', 'datetime', default=datetime.utcnow()),
    )

#####################

def represent_user_by_submission_feedback(v, r):
    return A(v, _href=URL('feedback', 'view_feedback', args=['u', r.venue_id, v]))
