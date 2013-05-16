# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## Customize your APP title, subtitle and menus here
#########################################################################

response.title = None
response.subtitle = T('')

## read more at http://dev.w3.org/html5/markup/meta.name.html
response.meta.author = 'Luca de Alfaro <luca@dealfaro.org> and Michael Shavlovsky <mshavlov@ucsc.edu>'
response.meta.description = 'CrowdGrader Submission Ranking System'
response.meta.keywords = 'web2py, python, framework'
response.meta.generator = 'Web2py Web Framework'

## your http://google.com/analytics id
response.google_analytics_id = None

#########################################################################
## this is the main application menu add/remove items as required
#########################################################################

response.menu = [
    (T('CrowdGrader'), False, URL('default', 'index'), []),
    (T('Submit'), False, None, [
        (T('Submit your solutions'), False, URL('venues', 'subopen_index'), []),
        (T('Your submissions'), False, URL('feedback', 'index', args=['all']), []),
        ]),
    (T('Review'), False, None, [
        (T('Assignments to review'), False, URL('venues', 'reviewing_duties'), []),
        (T('Enter your reviews'), False, URL('rating', 'task_index'), []),
        (T('Your completed reviews'), False, URL('rating', 'review_index'), []),
        ]),
    (T('Feedback'), False, None, [
        (T('Your submissions'), False, URL('feedback', 'index', args=['all']), []),
        (T('Your reviews'), False, URL('rating', 'review_index'), []),
        ]),
    (T('Manage'), False, None, [
        (T('Active assignments you manage'), False, URL('venues', 'managed_index'), []),
        (T('All assignments you manage'), False, URL('venues', 'managed_index', vars=dict(all='yes'))),
        (T('Assignments where you are a TA'), False, URL('venues', 'observed_index'), []),
        (T('Student lists'), False, URL('user_lists', 'index'), []),
        ]),
]

#########################################################################
## provide shortcuts for development. remove in production
#########################################################################


#def _():
#    # shortcuts
#    app = request.application
#    ctr = request.controller
#    # useful links to internal and external resources
#
#_()
