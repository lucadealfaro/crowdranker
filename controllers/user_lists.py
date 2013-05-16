# -*- coding: utf-8 -*-

import util

@auth.requires_login()
def index():
    """Index of user list one can manage or use."""
    # Reads the list of ids of lists managed by the user.
    list_ids_l = db(db.user_properties.user == get_user_email()).select(db.user_properties.managed_user_lists).first()
    if list_ids_l == None:
        list_ids = []
    else:
        list_ids = util.get_list(list_ids_l.managed_user_lists)
    # Keeps track of old managers, if this is an update.
    if len(request.args) > 2 and request.args[-3] == 'edit':
        ul = db.user_list[request.args[-1]]
        old_managers = ul.managers
        old_members = ul.user_list
    else:
        old_managers = []
        old_members = []
    # Adds a few comments.
    if len(request.args) > 0 and (request.args[0] == 'edit' or request.args[0] == 'new'):
        db.user_list.name.comment = T('Name of user list')
        db.user_list.managers.comment = T('Email addresses of users who can manage the list')
        db.user_list.user_list.comment = T(
            'Email addresses of list members. '
            ' You can enter multiple addresses per line, separated by a mix of spaces and commas.')
    # Forms the query.
    if len(list_ids) == 0:
        q = (db.user_list.id == -1)
    else:
        q = (db.user_list.id.belongs(list_ids))
    # Fixes the query for admins.
    if is_user_admin():
        q = db.user_list
    # Deals with search parameter
    if request.vars.id and request.vars.id != '':
        try:
            id = int(request.vars.id)
        except ValueError:
            id = None
        if id != None and id in list_ids:
            q = (db.user_list.id == id)
    grid = SQLFORM.grid(q, 
        field_id = db.user_list.id,
        csv=False, details=True,
        deletable=is_user_admin(),
        oncreate=create_user_list,
        onvalidation=validate_user_list,
        onupdate=update_user_list(old_managers, old_members),
        ondelete=delete_user_list,
        )
    db.commit()
    return dict(grid=grid)
    

def validate_user_list(form):
    """Splits emails on the same line, and adds the user creating the list to its managers."""
    logger.debug("form.vars: " + str(form.vars))
    form.vars.user_list = util.normalize_email_list(form.vars.user_list)
    form.vars.managers = util.normalize_email_list(form.vars.managers)
    if get_user_email() not in form.vars.managers:
        form.vars.managers = [get_user_email()] + form.vars.managers
    

def update_user_list(old_managers, old_members):
    """We return a callback that takes a form argument."""
    def f(form):
        logger.debug("Old managers: " + str(old_managers))
        logger.debug("New managers: " + str(form.vars.managers))
        add_user_list_managers(form.vars.id, util.list_diff(form.vars.managers, old_managers))
        delete_user_list_managers(form.vars.id, util.list_diff(old_managers, form.vars.managers))
        # If the list membership has been modified, we may need to update all the users
        # for which the list was used as venue constraint.
        added_users = util.list_diff(form.vars.user_list, old_members)
        removed_users = util.list_diff(old_members, form.vars.user_list)
        if len(added_users) + len(removed_users) > 0:
            fix_venues_for_user_submit(form.vars.id, added_users, removed_users)
            fix_venues_for_user_rate(form.vars.id, added_users, removed_users)
    return f

def create_user_list(form):
    add_user_list_managers(form.vars.id, form.vars.managers)

def delete_user_list(table, id):
    # TODO(luca): What do we have to do for the venues that were using this list for access control?
    old_managers = db.user_list[id].managers
    logger.debug("On delete, the old managers were: " + str(old_managers))
    delete_user_list_managers(id, old_managers)

# Venue management.  Finds which venues are using this list as their access control.

def fix_venues_for_user_submit(list_id, added_users, removed_users):
    venues = db(db.venue.submit_constraint == list_id).select()
    for v in venues:
        add_venue_to_user_submit(v.id, added_users)
        delete_venue_from_user_submit(v.id, removed_users)

def fix_venues_for_user_rate(list_id, added_users, removed_users):
    venues = db(db.venue.rate_constraint == list_id).select()
    for v in venues:
        add_venue_to_user_rate(v.id, added_users)
        delete_venue_from_user_rate(v.id, removed_users)


# User properties management for managers.
 
def add_user_list_managers(id, managers):
    for m in managers:
        u = db(db.user_properties.user == m).select(db.user_properties.managed_user_lists).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            logger.debug("Creating user properties for user:" + str(m) + "<")
            db.user_properties.insert(user=m, managed_user_lists=[id])
        else:
            l = util.get_list(u.managed_user_lists)
            l = util.list_append_unique(l, id)
            db(db.user_properties.user == m).update(managed_user_lists = l)
            
def delete_user_list_managers(id, managers):
    """Removes the user list from those that each user can manage"""
    for m in managers:
        u = db(db.user_properties.user == m).select(db.user_properties.managed_user_lists).first()
        if u != None:
            l = util.list_remove(u.managed_user_lists, id)
            db(db.user_properties.user == m).update(managed_user_lists = l)

# User properties management for submit, can_rate
           
def add_venue_to_user_submit(venue_id, users):
    """Add the given users to those that can submit to venue venue_id."""
    for m in users:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_submit).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            logger.debug("Creating user properties for email:" + str(m) + "<")
            db.user_properties.insert(user=m, venues_can_submit = [venue_id])
        else:
            l = util.get_list(u.venues_can_submit)
            l = util.list_append_unique(l, venue_id)
            db(db.user_properties.user == m).update(venues_can_submit = l)
        
def add_venue_to_user_rate(venue_id, users):
    """Add the given users to those that can rate venue_id."""
    for m in users:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_rate).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            logger.debug("Creating user properties for user:" + str(m) + "<")
            db.user_properties.insert(user=m, venues_can_rate = [venue_id])
        else:
            l = util.get_list(u.venues_can_rate)
            l = util.list_append_unique(l, venue_id)
            db(db.user_properties.user == m).update(venues_can_rate = l)
        
def delete_venue_from_user_submit(venue_id, users):
    """Delete the users from those can can submit to venue_id."""
    for m in users:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_submit).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            logger.debug("Creating user properties for user:" + str(m) + "<")
            db.user_properties.insert(user=m, venues_can_submit = [])
        else:
            l = util.get_list(u.venues_can_submit)
            l = util.list_remove(l, venue_id)
            db(db.user_properties.user == m).update(venues_can_submit = l)

def delete_venue_from_user_rate(venue_id, users):
    """Delete the users from those that can rate venue_id."""
    for m in users:
        u = db(db.user_properties.user == m).select(db.user_properties.venues_can_rate).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            logger.debug("Creating user properties for user:" + str(m) + "<")
            db.user_properties.insert(user=m, venues_can_rate = [])
        else:
            l = util.get_list(u.venues_can_rate)
            l = util.list_remove(l, venue_id)
            db(db.user_properties.user == m).update(venues_can_rate = l)
