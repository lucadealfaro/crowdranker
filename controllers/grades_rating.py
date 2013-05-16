# -*- coding: utf-8 -*-

import access
import util
import ranker
import gluon.contrib.simplejson as simplejson
from datetime import datetime
import datetime as dates


@auth.requires_login()
def rank_by_grades():
    c = db.venue(request.args(0)) or redirect(URL('default', 'index'))
    props = db(db.user_properties.user == get_user_email()).select().first()
    if not access.can_manage(c, props):
        session.flash = T('You cannot evaluate contributors for this venue')
        redirect(URL('default', 'index'))
    ranker.rank_by_grades(c.id)
    db.commit()
    session.flash = T('Grades are computed')
    redirect(URL('venues', 'view_venue_research', args=[c.id]))
