# -*- coding: utf-8 -*-

from gluon import *
import reputation
import util


class Vancouver():
    def __init__(self, venue_id, run_id='exp', publish=False,
                 use_median=False, do_debias=False):
        self.venue_id = venue_id
        self.run_id = run_id
        self.publish = publish
        # Information read.
        self.user_to_n_graded_tasks = {}
        self.user_to_n_rejected_tasks = {}
        self.user_to_n_completed_tasks = {}
        self.user_list = []
        self.user_to_submission_id = {}
        self.graph = reputation.Graph(use_median=use_median, do_debias=do_debias)
        # Grades.
        self.submission_grades = {}
        self.submission_percentiles = {}
        self.review_grades = {}
        self.review_percentiles = {}
        self.final_grades = {}
        self.final_percentiles = {}
        # Reads information about how the class is run.
        db = current.db
        self.venue = db(db.venue.id == venue_id).select().first()
        if self.venue is None:
            current.logger.error("Trying to evaluate a non-existent venue! %r" % venue_id)
        self.n_assigned_tasks = self.venue.number_of_submissions_per_reviewer
        self.review_grade_fraction = self.venue.reviews_as_percentage_of_grade / 100.0
        
    
    def read_number_of_tasks(self):
        """ Method returns dictionaries:
        user_to_n_graded_tasks - tasks to which a user has assigned grade
        user_to_n_rejected_tasks - rejected tasks
        user_to_n_completed_tasks
        """
        db = current.db
        # Resets the number of tasks.
        for u in self.user_list:
            self.user_to_n_completed_tasks[u] = 0
            self.user_to_n_graded_tasks[u] = 0
            self.user_to_n_rejected_tasks[u] = 0
        rows = db(db.task.venue_id == self.venue_id).select()
        for r in rows:
            u = r.user
            # Fetching information.
            if r.is_completed:
                self.user_to_n_completed_tasks[u] = self.user_to_n_completed_tasks.get(u, 0) + 1
                if r.rejected:
                    self.user_to_n_rejected_tasks[u] = self.user_to_n_rejected_tasks.get(u, 0) + 1
                else:
                    self.user_to_n_graded_tasks[u] = self.user_to_n_graded_tasks.get(u, 0) + 1
    
    
    def read_comparisons(self):
        """Reads the comparisons for a given contest."""
        db = current.db
        rows = db((db.comparison.venue_id == self.venue_id) &
                  (db.comparison.is_valid == True)).select()
        for r in rows:
            subm_id_to_grade = util.decode_json_grades(r.grades)
            for it_id, g in subm_id_to_grade.iteritems():
                self.graph.add_review(r.user, it_id, g)
                print "User", r.user, "item", it_id, "grade", g
    
    
    def read_user_list(self):
        """ Gets the users that participate in the class."""
        db = current.db
        c = db.venue(self.venue_id)
        r = db.user_list(c.submit_constraint)
        if r is not None:
            self.user_list = util.get_list(r.user_list)
        if not c.raters_equal_submitters:
            ulr = []
            r = db.user_list(c.rate_constraint)
            if r is not None:
                ulr = util.get_list(r.user_list)
            self.user_list = util.union_list(self.user_list, ulr)
    
    
    def read_user_to_submission_id(self):
        """Reads the user to submission_id correspondence."""
        db = current.db
        rows = db(db.submission.venue_id == self.venue_id).select()
        for r in rows:
            self.user_to_submission_id[r.user] = r.id
    
    
    def read_venue_data(self):
        """Reads the data for the given venue."""
        # Reading the list of all users.
        self.read_user_list()
        # Fetching number of completed, graded and rejected tasks per user.
        self.read_number_of_tasks()
        # Reading the graph of actual evaluations.
        self.read_comparisons()
        # Reads the list of all submissions.
        self.read_user_to_submission_id()

    
    def write_grades(self):
        db = current.db
        if self.publish:
            # Writes to the main table.
            db(db.grades.venue_id == self.venue_id).delete()
            for u in self.user_list:
                db.grades.insert(
                     venue_id = self.venue_id,
                     user = u,
                     submission_grade = self.submission_grades[u],
                     submission_percentile = self.submission_percentiles[u],
                     accuracy = self.review_grades[u],
                     accuracy_percentile = self.review_percentiles[u],
                     n_ratings = self.user_to_n_completed_tasks[u],
                     grade = self.final_grades[u],
                     percentile = self.final_percentiles[u],
                    )
        else:
            # Writes to a run table.
            db((db.grades_exp.venue_id == self.venue_id) &
               (db.grades_exp.run_id == self.run_id)).delete()
            for u in self.user_list:
                db.grades_exp.insert(
                    venue_id = self.venue_id,
                    run_id = self.run_id,
                    user = u,
                    subm_grade = self.submission_grades[u],
                    subm_percent = self.submission_percentiles[u],
                    review_grade = self.review_grades[u],
                    review_percent = self.review_percentiles[u],
                    n_ratings = self.user_to_n_completed_tasks[u],
                    grade = self.final_grades[u],
                    # TODO(luca): also write the final percentile.                                     
                    )
        db.commit()
            
    
    def compute_grades(self):
        """Once we have all the information on the item grades
        and user quality, we compute the actual grades and percentiles."""
        # Just to ensure these are at the bottom; cannot trust
        # 0.0 as there may be submissions with negative grade.
        min_grade = -1.0e10
        # First, submission grades.
        subm_grades = {}
        for u in self.user_list:
            subm_grades[u] = min_grade
            subm_id = self.user_to_submission_id.get(u)
            if subm_id is not None:
                it = self.graph.get_item(subm_id)
                if it is not None and it.grade is not None:
                    subm_grades[u] = it.grade
        # Computes the percentiles.
        self.submission_percentiles = util.compute_percentile(subm_grades)
        # And normalizes the grades between 0 and the max.
        for u, g in subm_grades.iteritems():
            self.submission_grades[u] = max(0.0, min(current.MAX_GRADE, g))
        # Then, computes the review grades.
        for u in self.user_list:
            self.review_grades[u] = 0.0
            user_node = self.graph.get_user(u)
            if user_node is not None and user_node.quality is not None:
                fraction_done = min(1.0, 1.0 * self.user_to_n_completed_tasks[u] / self.n_assigned_tasks)
                self.review_grades[u] = user_node.quality * fraction_done
        self.review_percentiles = util.compute_percentile(self.review_grades)
        # Finally, the final grades.  Note that we use the un-normalized
        # versions of the grades, so that "people that are better than 10" 
        # get extra credit that can go to their overall grade.
        fg = {}
        for u in self.user_list:
            sub_g = max(0.0, subm_grades[u])
            rev_g = self.review_grades[u]
            fg[u] = (current.MAX_GRADE * self.review_grade_fraction * rev_g + 
                     (1.0 - self.review_grade_fraction) * sub_g)
        self.final_percentiles = util.compute_percentile(fg)
        for u, g in fg.iteritems():
            self.final_grades[u] = max(0.0, min(current.MAX_GRADE, g))
        # That's all, folks.
        
    
    def run_evaluation(self):
        """Computes the grades using the Vancouver algorithm.
        This is the main method that needs to be called."""
        if self.venue is None:
            return
        # First, I need to read the data from the db on this venue.
        self.read_venue_data()
        # Second, computes all item grades...
        self.graph.evaluate_items()
        # ... and all user qualities. 
        self.graph.evaluate_users()
        # At this point, we have to assign the final grades.
        self.compute_grades()
        # Finally, writes the grades.
        self.write_grades()
        # Done!
