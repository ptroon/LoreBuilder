
#
# Blueprint for the GUI
#

from flask import Flask, Blueprint, url_for, jsonify, make_response, app, \
        render_template, request, session, redirect, flash, g
from flask_login import login_required, login_user, logout_user, current_user
from flask_mail import Message
import re
import logging
from datetime import datetime
from file_read_backwards import FileReadBackwards
from sqlalchemy.orm import aliased

from project.models import *
from project import app, db, is_admin, mail, get_user
from project.gui.forms import *
from project.gui.logic import *

gui_blueprint = Blueprint('gui_blueprint', __name__, url_prefix="/fpa")

def get_version ():
    session["version"] = app.config["VERSION"]

# Checks to see if token is set as a session variable
def is_loggedin ():
    try:
        if session['token']:
            return True
        else:
            return False
    except:
        return False

#################################################################
# ROOT #
########
@gui_blueprint.route("/")
def _index ():

    if current_user.is_authenticated:
        bookings = Booking.query.filter(Booking.owner_id==get_user()).all()
        admin = Booking.query.all()
        return render_template("dashboard.html", data1=bookings, data2=admin)
    else:
        return redirect(url_for('gui_blueprint._login'))

#################################################################
# LOGIN #
#########
@gui_blueprint.route("/login", methods=["POST","GET"])
def _login ():

    form = UserForm()
    if request.method=='POST':

        if request.form['login_id'] and request.form['password']:
            user = User.query.filter_by(login_id=request.form['login_id']).first()
            if not user:
                app.logger.warning ("Log in error for " + request.form['login_id'] + ", no account found")
                flash('No account found for ' + request.form['login_id'], 'warning')
                return render_template("login.html", form=form)
            else:
                role = Role.query.filter_by(id=user.role).first()
                _role = re.search("LOGIN", role.role_app_sections)
                if user.is_correct_password(request.form['password']) and _role: # check hash OK and user can actually log in
                    session['login_id'] = request.form['login_id']
                    login_user(user)
                    app.logger.info ("Successfully logged in " + request.form['login_id'])

            if current_user.is_authenticated:
                flash('You were successfully logged in', 'success')
                if request.form["next"]:
                    return redirect(request.form["next"])
                return redirect(url_for('gui_blueprint._index'))

            flash('Error with login! id or password wrong or account currently locked', 'warning')
            return render_template("login.html", form=form)

        else:
            flash('Login or password missing!', 'warning')
            return render_template("login.html", form=form)

    else:
        return render_template("login.html", form=form)

#################################################################
# LOGOUT #
##########
@gui_blueprint.route("/logout", methods=["GET"])
def _logout ():

    if request.method == 'GET':
        if current_user.is_authenticated:
            session['login_id'] = None
            logout_user()
    return redirect(url_for('gui_blueprint._index'))

#################################################################
# REGISTER #
############
@gui_blueprint.route("/register", methods=["GET", "POST"])
def _register ():

    form = UserForm()
    form.savebtn.label.text = 'Register'
    form.role.data = 6 # Add as a new user
    if request.method == 'GET':
        return render_template("register.html", form=form)

    if form.validate_on_submit():
        user = User(form.login_id.data, form.forename.data, form.surname.data, form.comment.data, form.password.data, form.email.data, form.role.data, form.vendor.data)
        db.session.add(user)

        if not form.password.data:
            del form.password

        form.populate_obj(user)
        user.last_modified = datetime.now()
        user.modified_by = session["login_id"]
        user.last_login = None

        if not form.created_date.data:
            user.created_date = datetime.now()

        db.session.commit()
        flash ('User saved successfully', 'success')
        return redirect(url_for('gui_blueprint._index'))

    else:
        flash_errors(form)
        return render_template("register.html", form=form)


#################################################################
# COMPLEXES #
#############
@gui_blueprint.route("/admin/complexes")
@login_required
def _complexes ():
    if is_admin():

        a = aliased(Parameter)
        b = aliased(Parameter)
        c = aliased(Parameter)
        d = aliased(Parameter)

        complexes = db.session.query(Complex, a, b, c, d).\
        filter(Complex.complex_manager==a.id).\
        filter(Complex.complex_type==b.id).\
        filter(Complex.complex_country==c.id).\
        filter(Complex.complex_active==d.id).all()

        return render_template("complexes.html", data = complexes)
    else:
        return render_template("403.html", error = "You are not an administrator")

@gui_blueprint.route("/admin/editcomplex/<id>", methods=["GET","POST"])
@login_required
def _editcomplex (id):
    if is_admin():

        complex = Complex.query.filter_by(id=id).first()
        form = ComplexForm(obj=complex)

        if request.method == "GET":
            return render_template("editcomplex.html", data=complex, form=form)

        if form.validate_on_submit():
            if not complex:
                complex = Complex()
                db.session.add(complex)

            form.populate_obj(complex)
            complex.complex_updated = datetime.now()
            db.session.commit()
            flash ('Complex saved successfully', 'success')
            return redirect(url_for('gui_blueprint._complexes'))
        else:
            flash_errors(form)

        return render_template("editcomplex.html", data=complex, form=form)

    else:
        return render_template("403.html", error = "You are not an administrator")

#################################################################
# LOGS #
########
@gui_blueprint.route("/admin/logs", methods=["GET","POST"])
@login_required
def _logs ():
    if is_admin():

        form = LogForm()

        # Prevent the rec # counter from breaking the app - default to 10
        try:
            records = int(request.args.get('log_records'))
        except:
            records = 5

        # Prevent the log name from breaking the app - default to LOG_FILE variable
        try:
            rec_t = request.args.get('log_options')
            log_t   = app.config[rec_t]
        except:
            log_t = app.config["LOG_FILE"]

        form.log_records.data = str(records)
        form.log_options.data = rec_t
        data = FileReadBackwards(log_t, encoding="utf-8")
        return render_template("logs.html", data=data, form=form, counter=records)
    else:
        return render_template("403.html", error = "You are not an administrator")

#################################################################
# USERS #
#########
@gui_blueprint.route("/admin/users", methods=["GET"])
@login_required
def _users ():
    if is_admin():
        users = db.session.query(User,Role,Parameter).join(Role).outerjoin(Parameter).order_by(User.id.asc())
        return render_template("users.html", data = users)
    else:
        return render_template("403.html", error = "You are not an administrator")

@gui_blueprint.route("/admin/edituser/<id>", methods=["GET","POST"])
@login_required
def _edituser (id):
    if is_admin():

        user = User.query.filter_by(id=id).first()
        form = UserForm(obj=user)

        if request.method == "GET":
            return render_template("edituser.html", data = user, form = form)

        if request.method == "POST":
            if not form.password.data:
                del form.password


        if form.validate_on_submit():
            if form.savebtn.data:
                if not user:
                    user = User(form.login_id.data, form.forename.data, form.surname.data, form.comment.data, form.password.data, form.email.data, form.role.data, form.vendor.data)
                    db.session.add(user)

                form.populate_obj(user)
                user.last_modified = datetime.now()
                user.modified_by = session["login_id"]
                user.last_login = None

                if not form.created_date.data:
                    user.created_date = datetime.now()

                db.session.commit()
                flash ('User saved successfully', 'success')
                return redirect(url_for('gui_blueprint._users'))

            if form.deletebtn.data:
                user = User.query.filter_by(id=id).first()
                db.session.delete(user)
                flash ('User removed successfully', 'success')
                db.session.commit()
                return redirect(url_for('gui_blueprint._users'))

        else:
            flash_errors (form)

        return render_template("edituser.html", data=user, form=form)

    else:
        return render_template("403.html", error = "You are not an administrator")

#################################################################
# ROLES #
#########
@gui_blueprint.route("/admin/roles", methods=["GET"])
@login_required
def _roles ():
    if is_admin():
        roles = Role.query.order_by(Role.id.asc())
        return render_template("roles.html", data = roles)
    else:
        return render_template("403.html", error = "You are not an administrator")


@gui_blueprint.route("/admin/editrole/<id>", methods=["GET","POST"])
@login_required
def _editrole (id):

    if is_admin():

        role = Role.query.filter_by(id=id).first()
        form = RoleForm(obj=role)

        if request.method == "GET":
            return render_template("editrole.html", form=form, data=role)

        if form.validate_on_submit():

            if form.savebtn.data:
                if not role:
                    role = Role(form.role_name.data, form.role_admin.data, form.role_app_sections.data, form.enabled.data)
                    db.session.add(role)

                form.populate_obj(role)
                role.created_date = datetime.now()
                db.session.commit()
                flash ('Role saved successfully', 'success')
                return redirect(url_for('gui_blueprint._roles'))

            if form.deletebtn.data:
                role = Role.query.filter_by(id=id).first()
                counter = User.query.filter_by(role=role.id).count()
                if counter == 0:  # there are no user accounts using this role
                    db.session.delete(role)
                    flash ('Role removed successfully', 'success')
                    db.session.commit()
                else:
                    flash ('Cannot delete role as it is in use', 'warning')

        else:
            flash_errors (form)
            return render_template("editrole.html", form=form, data=role)

        return redirect(url_for('gui_blueprint._roles'))

#################################################################
# DATES #
#########
@gui_blueprint.route("/admin/dates", methods=["GET"])
@login_required
def _dates ():
    if is_admin():
        a = aliased(Parameter)
        b = aliased(Parameter)
        c = aliased(Parameter)
        d = aliased(DateOfInterest)

        dates = db.session.query(d.id, d.doi_name, d.doi_regions, d.doi_start_dt, d.doi_end_dt, a.param_value, \
        b.param_name, c.param_name).join(a, d.doi_priority==a.id).\
        join(b, d.doi_hap==b.id).join(c, d.doi_locked==c.id).order_by(d.doi_start_dt.asc()).all()

        return render_template("dates.html", data=dates)
    else:
        return render_template("403.html", error = "You are not an administrator")

@gui_blueprint.route("/admin/editdate/<id>", methods=["GET","POST"])
@login_required
def _editdate (id):

    if is_admin():

        doi = DateOfInterest.query.filter_by(id=id).first()
        form = DOIForm(obj=doi)

        if request.method == "GET":
            if doi:
                form.doi_start_dt.data = datetime.strftime(datetime.strptime(doi.doi_start_dt, '%Y-%m-%d %H:%M:%S'), '%d/%m/%Y %H:%M')
                form.doi_end_dt.data = datetime.strftime(datetime.strptime(doi.doi_end_dt, '%Y-%m-%d %H:%M:%S'), '%d/%m/%Y %H:%M')
            return render_template("editdate.html", form=form, data=doi)

        if form.deletebtn.data:
            doi = DateOfInterest.query.filter_by(id=id).first()
            db.session.delete(doi)
            flash ('Date removed successfully', 'success')
            db.session.commit()
            return redirect(url_for('gui_blueprint._dates'))

        if form.validate_on_submit():

            start_dt = datetime.strptime(form.doi_start_dt.data, '%d/%m/%Y %H:%M')
            end_dt = datetime.strptime(form.doi_end_dt.data, '%d/%m/%Y %H:%M')

            if form.savebtn.data:
                if not doi:
                    doi = DateOfInterest(form.doi_name.data, form.doi_priority.data, form.doi_comment.data, \
                    start_dt, end_dt, form.doi_regions, form.doi_locked, form.doi_hap)
                    db.session.add(doi)

                form.populate_obj(doi)
                doi.doi_start_dt = start_dt
                doi.doi_end_dt = end_dt
                db.session.commit()

                flash ('Date saved successfully', 'success')
                return redirect(url_for('gui_blueprint._dates'))

        else:
            flash_errors(form)
            return render_template("editdate.html", form=form, data=doi)

        return redirect(url_for('gui_blueprint._dates'))


    else:
        return render_template("403.html", error = "You are not an administrator")

#################################################################
# SEARCH #
##########
@gui_blueprint.route("/search", methods=["GET","POST"])
def _search ():

    a = aliased(DateOfInterest)

    form = MainSearchForm()
    if request.method == 'POST':

        # get query
        query = request.form.get('search_input', None)

        if query:
            # get matches
            results = db.session.query(a.id, a.doi_name, a.doi_comment, a.doi_start_dt, a.doi_end_dt).\
            filter((a.doi_comment+' '+a.doi_name).ilike(('%{}%').format(query))).all()

            return render_template("search.html", query=query, results=results, form=form)
        else:
            return render_template("search.html", query=None, results=None, form=form)
    else:
        return render_template("search.html", query=None, results=None, form=form)

#################################################################
# HELP #
########
@gui_blueprint.route("/usage")
def _help ():

    if request.method == 'GET':
        help = db.session.query(Parameter.param_name, Parameter.param_value).filter(Parameter.param_group==113).order_by(Parameter.id.asc()).all()
        return render_template("help.html", data = help)

#################################################################
# BOOKINGS #
############

@gui_blueprint.route("/bookings", methods=["GET"])
def _bookings ():

    # Show the booking calendar view
    if request.method == "GET":
        form = ComplexNameSelectForm()
        defdate = request.args.get("defdate", datetime.now())
        return render_template("calendar.html", form=form, defdate=defdate)


@gui_blueprint.route("/editbooking/<id>", methods=["GET","POST"])
def _editbooking (id):

    #for key, value in request.form.items():
    #    print(key, value)

    booking = Booking.query.filter_by(id=id).first()
    form = BookingForm(obj=request.form)

    if request.method == "POST":

        # check from initial select form submitted as "Next"
        if request.form.get("nextbtn", False):
            cplx = int(request.form.get("complex_select", 1)) # Get Complex ID
            complex = Complex.query.filter(Complex.id==int(cplx)).first() # Get complex object from query

            s_time = complex.complex_push_start
            e_time = complex.complex_push_end
            form.start_dt.default = request.form.get("start") + " " + s_time
            form.end_dt.default = request.form.get("start") + " " + e_time
            form.tmp_date.default = request.form.get("start").replace("-","/")
            form.tmp_start_t.default = s_time
            form.tmp_end_t.default = e_time

            if is_day_allowed(request.form.get("start"), complex.complex_push_days):
                form.approval_required.default = "0" # may change once the booking has been checked
            else:
                form.approval_required.default = "1"

            form.complex.default = request.form.get("complex_select", 1)
            form.complex_text.default = complex.complex_name

            form.process()
            return render_template("editbooking.html", form=form)

        # This is the actual booking page and we're trying to save the record
        # VALID
        if form.validate_on_submit():

            # We have made it to the process/checking section.  Data is valid so we determine if the booking
            # needs to be approved or not.
            if request.form.get("checkbtn", False):
                complex = Complex.query.filter(Complex.id==int(form.complex.data)).first() # Get complex object from query

                print (form.tmp_date.data)
                print (form.tmp_start_t.data)
                print (form.tmp_end_t.data)

                print (is_booking_custom(form.tmp_start_t.data, form.tmp_end_t.data, form.complex.data))
                print (is_booking_core_ok(form.tmp_date.data, form.complex.data))

                # if is_booking_core_ok(form.start_dt):

                return redirect(url_for('gui_blueprint._index'))

            return redirect(url_for('gui_blueprint._bookings'))


        # INVALID, so go back to edit page and get corrections by user.
        else:
            print (form.approval_required.default)
            flash_errors(form)
            return render_template("editbooking.html", form=form)


# Check the booking for business rules
@gui_blueprint.route("/checkbooking/<id>", methods=["GET","POST"])
def _checkbooking (id):

    return redirect(url_for('gui_blueprint._bookings'))

#################################################################
# PUSH DAYS #
#############
@gui_blueprint.route("/pushdays", methods=["GET"])
def _pushdays ():

    cplx_list = []
    a_cplx = []
    # Show the booking calendar view
    if request.method == "GET":

        search = request.args.get('search', None) # see if a search argument was given

        complexes = Complex.query.all() # get all complexes
        for cplx in complexes:
            a_cplx.append(cplx.complex_name)
            for day_ in cplx.complex_push_days:
                a_cplx.append(day_)
            cplx_list.append(a_cplx)
            print (a_cplx)
            a_cplx = []

        return render_template("push.html", data=cplx_list, search=search)

#################################################################
# PARAMETERS #
##############
# Show parameters in a form using a select box to control groupings
@gui_blueprint.route("/admin/parameters", methods=["GET","POST"])
@login_required
def _parameters ():

    if is_admin():
        sel = ParameterSearchForm()

        if request.method == 'POST':
            sel.param_groups.default = request.form["param_groups"]
            sel.process()
            session["group"] = sel.param_groups.default # save group into session variable for reference.
            # params = Parameter.query.filter(Parameter.param_group == sel.param_groups.default).paginate(1, app.config["PAGINATION_SIZE"], False) # get the currently chosen option from the select list and use to control which parameters are shown
            params = Parameter.query.filter(Parameter.param_group == sel.param_groups.default).all()
        else:
            session["group"] = request.args.get('group', 0, type=int)

            if session["group"] > 0:
                page = request.args.get('page', 1, type=int)
                # set the session variable to the arg GROUP from the URL and then choose the params from that group id.
                sel.param_groups.default = session["group"]
                sel.process()
                # params = Parameter.query.filter(Parameter.param_group == Parameter.query.filter(Parameter.id == session["group"]).first().id).paginate(page, app.config["PAGINATION_SIZE"], False)
                params = Parameter.query.filter(Parameter.param_group == Parameter.query.filter(Parameter.id == session["group"]).first().id).all()
            else:
                # Just get the first in the list as the chosen option, then get the params for that id.
                session["group"] = Parameter.query.filter(Parameter.param_group==0).order_by(Parameter.param_name.asc()).first().id
                # params = Parameter.query.filter(Parameter.param_group == session["group"]).paginate(1, app.config["PAGINATION_SIZE"], False)
                params = Parameter.query.filter(Parameter.param_group == session["group"]).all()
                sel.param_groups.default = session["group"]
                sel.process()

        print (params)
        return render_template("parameters.html", data=params, sel=sel)
    else:
        return render_template("403.html", error = "You are not an administrator")


# Edit Parameter for the application
@gui_blueprint.route("/admin/editparameter/<id>", methods=["GET","POST"])
@login_required
def _editparameter (id):
    if is_admin():

        param = Parameter.query.filter_by(id=id).first()
        form = ParameterForm(obj=param)

        if request.method == "GET":
            return render_template("editparameter.html", data=param, form=form)

        if form.validate_on_submit():
            if form.savebtn.data:
                if not param:
                    param = Parameter(form.id.data, form.param_name.data, form.param_value.data, form.param_group.data, form.param_parent.data, form.param_disabled.data, form.param_critical.data)
                    db.session.add(param)

                form.populate_obj(param)
                db.session.commit()
                return redirect(url_for('gui_blueprint._parameters', group=session["group"]))

            if form.deletebtn.data:
                param = Parameter.query.filter_by(id=id).first()
                capacity = Parameter.query.filter(Parameter.param_group==param.id).count()
                if capacity == 0:
                    db.session.delete(param)
                    db.session.commit()
                else:
                    flash("Cannot delete non-empty Parameter Group: " + param.param_name, "warning")

                return redirect(url_for('gui_blueprint._parameters', group=0))

        else:
            for fieldName, errorMessages in form.errors.items():
                for err in errorMessages:
                    print (fieldName + " " + err + " value:(" + str(form.param_group.data) + ")")
            return render_template("400.html", error = form.errors)

    else:
        return render_template("403.html", error = "You are not an administrator")


#################################################################
# PROFILE #
###########
@gui_blueprint.route("/editprofile", methods=["GET","POST"])
@login_required
def _editprofile ():

    # Get user's details to be edited
    profile = User.query.filter(User.login_id == get_user()).first()
    form = UserForm(obj=profile)

    # If we are GET'ing the form then add data and show correct form & template
    if request.method == "GET":
        return render_template("profile.html", data=profile, form=form)

    del form.role # user can't change this in their profile
    del form.last_login # they aren't logging in at this stage

    # delete password if they haven't entered text to change it.
    if request.method == "POST":
        if not form.password.data:
            del form.password

    # If we are POST'ing then we are making a change, so show message
    if form.validate_on_submit():
        if form.savebtn.data:
            form.populate_obj(profile)
            profile.last_modified = datetime.now()
            profile.modified_by = session["login_id"]
            db.session.commit()
            flash ("Saved Profile Details", 'success')
            return redirect(url_for('gui_blueprint._index'))

    else:
        flash_errors(form)
        return render_template("profile.html", data=profile, form=form)

#################################################################
# EMAIL #
#########
'''
@gui_blueprint.route("/admin/email", methods=["POST","GET"])
@login_required
def _email ():

    if request.method == "GET":
        if is_admin():
            return render_template("email.html")
        else:
            return render_template("403.html", error = "You are not an administrator")

    if request.method == "POST":
        msg = Message(subject=request.form["subject"],
                      sender=app.config["MAIL_USERNAME"],
                      recipients=request.form["recipient"],
                      body=request.form["body"])
        # mail.send(msg)
        # print (msg.__dict__)
        return render_template("email.html", data = msg)
'''
