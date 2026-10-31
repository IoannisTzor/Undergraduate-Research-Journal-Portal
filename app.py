import os
from functools import wraps

from flask import Flask, render_template, session, redirect, url_for, request, abort, g
from dotenv import load_dotenv
from flask_migrate import Migrate
from sqlalchemy import text
from submission_types import SUBMISSION_TYPES
from seed import seed_command
from models import db, User, Submission, Review, Issue

from models import db

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]

db.init_app(app)
migrate = Migrate(app, db)
app.cli.add_command(seed_command)

@app.before_request
def load_current_user():
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None

ROLES = ["guest", "submitter", "reviewer", "editor", "admin"]

def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None or g.user.role != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator



@app.route("/")
def home():
    current_issue = db.session.scalars(
        db.select(Issue)
        .where(Issue.status == "published")
        .order_by(Issue.published_at.desc())
    ).first()
    return render_template("index.html", current_issue=current_issue)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/past_issues")
def past_issues():
    return render_template("past_issues.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")

@app.route("/dev/login/<int:user_id>")
def dev_login(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    session["user_id"] = user.id
    return redirect(request.referrer or url_for("home"))


@app.route("/dev/logout")
def dev_logout():
    session.pop("user_id", None)
    return redirect(url_for("home"))


@app.context_processor
def inject_role():
    return {
        "current_user": g.user,
        "current_role": g.user.role if g.user else "guest",
        "roles": ROLES,
        "dev_users": db.session.scalars(db.select(User).order_by(User.role, User.last_name)).all(),
        "submission_types": SUBMISSION_TYPES,
    }

@app.template_filter("date")
def format_date(value):
    if value is None:
        return ""
    return f"{value.strftime('%B')} {value.day}, {value.year}"

@app.route("/submit/<submission_type>")
@role_required("submitter")
def submit_study(submission_type):
    type_info = SUBMISSION_TYPES.get(submission_type)
    if type_info is None:
        abort(404)
    return render_template("submit_study.html", type_key=submission_type, type_info=type_info)

@app.route("/my-submissions")
@role_required("submitter")
def my_submissions():
    submissions = db.session.scalars(
        db.select(Submission)
        .where(Submission.author_id == g.user.id)
        .order_by(Submission.submitted_at.desc())
    ).all()
    return render_template("my_submissions.html", submissions=submissions)

@app.route("/my-submissions/<int:submission_id>")
@role_required("submitter")
def submission_details(submission_id):
    submission = db.session.get(Submission, submission_id)
    if submission is None or submission.author_id != g.user.id:
        abort(404)
    reviews = [review for review in submission.reviews if review.status == "submitted"]
    return render_template("submission_details.html", submission=submission, reviews=reviews)
    abort(404)

@app.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403

@app.route("/assignments")
@role_required("reviewer")
def my_assignments():
    reviews = db.session.scalars(
        db.select(Review)
        .where(Review.reviewer_id == g.user.id)
        .order_by(Review.due_date)
    ).all()
    return render_template("my_assignments.html", reviews=reviews)

@app.route("/assignments/<int:review_id>")
@role_required("reviewer")
def write_review(review_id):
    review = db.session.get(Review, review_id)
    if review is None or review.reviewer_id != g.user.id:
        abort(404)
    return render_template("write_review.html", review=review)
    abort(404)

@app.route("/editor/submissions")
@role_required("editor")
def all_submissions():
    submissions = db.session.scalars(
        db.select(Submission).order_by(Submission.submitted_at.desc())
    ).all()
    return render_template("all_submissions.html", submissions=submissions)

@app.route("/editor/submissions/<int:submission_id>")
@role_required("editor")
def manage_submission(submission_id):
    submission = db.session.get(Submission, submission_id)
    if submission is None:
        abort(404)

    assigned_ids = [review.reviewer_id for review in submission.reviews]
    reviewer_options = db.session.scalars(
        db.select(User)
        .where(User.role == "reviewer", User.id.not_in(assigned_ids))
        .order_by(User.last_name)
    ).all()

    submitted_reviews = [review for review in submission.reviews if review.status == "submitted"]
    return render_template(
        "manage_submission.html",
        submission=submission,
        reviewer_options=reviewer_options,
        submitted_reviews=submitted_reviews,
    )

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

@app.route("/editor/build-issue")
@role_required("editor")
def build_issue():
    accepted = db.session.scalars(
        db.select(Submission)
        .where(Submission.status == "accepted", Submission.issue_id.is_(None))
        .order_by(Submission.title)
    ).all()
    return render_template("build_issue.html", accepted=accepted)

@app.route("/admin/users")
@role_required("admin")
def manage_users():
    users = db.session.scalars(
        db.select(User).order_by(User.role, User.last_name)
    ).all()
    return render_template("manage_users.html", users=users)

@app.route("/guidelines")
def guidelines():
    return render_template("guidelines.html", submission_types=SUBMISSION_TYPES)