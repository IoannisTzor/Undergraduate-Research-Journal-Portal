import os
from functools import wraps

from flask import Flask, render_template, session, redirect, url_for, request, abort, g
from models import db, User
from dotenv import load_dotenv
from flask import Flask, render_template, session, redirect, url_for, request, abort
from flask_migrate import Migrate
from sqlalchemy import text
from submission_types import SUBMISSION_TYPES
from seed import seed_command

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

SAMPLE_SUBMISSIONS = [
{
        "id": 1,
        "title": "How soil microbes respond to drought",
        "discipline": "Biology",
        "submitted": "September 12, 2026",
        "status": "revisions-requested",
        "author": "Jane Doe",
        "reviewers": [
            {"name": "Dr. Maria Lopez", "review_status": "submitted"},
            {"name": "Sam Carter", "review_status": "submitted"},
        ],
        "reviews": [
            {
                "reviewer": "Reviewer 1",
                "date": "October 3, 2026",
                "recommendation": "Minor revisions",
                "comments": "Clear question and good sampling design. Please explain how soil moisture was measured, and add error bars to Figure 2.",
                "editor_comments": "Figure 2 looks very similar to one in a 2021 paper. Worth checking with the author.",
            },
            {
                "reviewer": "Reviewer 2",
                "date": "October 6, 2026",
                "recommendation": "Accept after revisions",
                "comments": "Strong discussion section. The abstract should mention the six-week timeframe.",
            },
        ],
    },
    {
        "id": 2,
        "title": "Measuring cache effects in sorting algorithms",
        "discipline": "Computer Science",
        "submitted": "September 30, 2026",
        "status": "under-review",
        "author": "Alex Lee",
        "reviewers": [
            {"name": "Dr. Ken Wu", "review_status": "not-started"},
        ],
    },
    {
        "id": 3,
        "title": "Tracking sediment in the Chippewa River",
        "discipline": "Environmental Science",
        "submitted": "April 2, 2026",
        "status": "published",
        "author": "Priya Shah",
        "reviewers": [
            {"name": "Dr. Maria Lopez", "review_status": "submitted"},
            {"name": "Dr. Ken Wu", "review_status": "submitted"},
        ],
    },
        {
        "id": 4,
        "title": "Solar panel efficiency in Michigan winters",
        "discipline": "Engineering",
        "submitted": "October 18, 2026",
        "status": "submitted",
        "author": "Omar Haddad",
        "reviewers": [],
    },
        {
        "id": 5,
        "title": "Graph coloring for exam scheduling",
        "discipline": "Mathematics",
        "submitted": "August 28, 2026",
        "status": "accepted",
        "author": "Lena Fischer",
        "reviewers": [
            {"name": "Dr. Ana Ruiz", "review_status": "submitted"},
        ],
    },
    {
        "id": 6,
        "title": "Antibacterial properties of local honey",
        "discipline": "Chemistry",
        "submitted": "September 4, 2026",
        "status": "accepted",
        "author": "Marcus Bell",
        "reviewers": [
            {"name": "Sam Carter", "review_status": "submitted"},
            {"name": "Dr. Maria Lopez", "review_status": "submitted"},
        ],
    },
]
SAMPLE_ASSIGNMENTS = [
    {
        "id": 1,
        "submission_id": 1,
        "title": "How soil microbes respond to drought",
        "discipline": "Biology",
        "assigned": "September 20, 2026",
        "due": "October 10, 2026",
        "review_status": "submitted",

    },
    {
        "id": 2,
        "submission_id": 2,
        "title": "Measuring cache effects in sorting algorithms",
        "discipline": "Computer Science",
        "assigned": "October 5, 2026",
        "due": "October 26, 2026",
        "review_status": "not-started",
    },
]
SAMPLE_REVIEWERS = ["Dr. Maria Lopez", "Dr. Ken Wu", "Sam Carter", "Dr. Ana Ruiz"]

SAMPLE_USERS = [
    {"id": 1, "name": "Jane Doe", "email": "doe1j@cmich.edu", "role": "submitter", "joined": "August 30, 2026"},
    {"id": 2, "name": "Dr. Maria Lopez", "email": "lopez1m@cmich.edu", "role": "reviewer", "joined": "August 12, 2026"},
    {"id": 3, "name": "Sam Carter", "email": "carte1s@cmich.edu", "role": "reviewer", "joined": "September 2, 2026"},
    {"id": 4, "name": "Kathryn Bleicher", "email": "bleic1k@cmich.edu", "role": "editor", "joined": "August 1, 2026"},
    {"id": 5, "name": "Site Admin", "email": "admin@cmich.edu", "role": "admin", "joined": "August 1, 2026"},
]

@app.route("/")
def home():
    return render_template("index.html")

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
    }

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
    return render_template("my_submissions.html", submissions=SAMPLE_SUBMISSIONS)

@app.route("/my-submissions/<int:submission_id>")
@role_required("submitter")
def submission_details(submission_id):
    for submission in SAMPLE_SUBMISSIONS:
        if submission["id"] == submission_id:
            return render_template("submission_details.html", submission=submission)
    abort(404)

@app.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403

@app.route("/assignments")
@role_required("reviewer")
def my_assignments():
    return render_template("my_assignments.html", assignments=SAMPLE_ASSIGNMENTS)

@app.route("/assignments/<int:assignment_id>")
@role_required("reviewer")
def write_review(assignment_id):
    for assignment in SAMPLE_ASSIGNMENTS:
        if assignment["id"] == assignment_id:
            return render_template("write_review.html", assignment=assignment)
    abort(404)

@app.route("/editor/submissions")
@role_required("editor")
def all_submissions():
    return render_template("all_submissions.html", submissions=SAMPLE_SUBMISSIONS)

@app.route("/editor/submissions/<int:submission_id>")
@role_required("editor")
def manage_submission(submission_id):
    for submission in SAMPLE_SUBMISSIONS:
        if submission["id"] == submission_id:
            return render_template(
                "manage_submission.html",
                submission=submission,
                reviewer_options=SAMPLE_REVIEWERS,
            )
    abort(404)

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

@app.route("/editor/build-issue")
@role_required("editor")
def build_issue():
    accepted = [s for s in SAMPLE_SUBMISSIONS if s["status"] == "accepted"]
    return render_template("build_issue.html", accepted=accepted)

@app.route("/admin/users")
@role_required("admin")
def manage_users():
    return render_template("manage_users.html", users=SAMPLE_USERS)

@app.route("/guidelines")
def guidelines():
    return render_template("guidelines.html", submission_types=SUBMISSION_TYPES)