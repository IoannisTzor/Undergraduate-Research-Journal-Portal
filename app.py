from flask import Flask, render_template

from flask import Flask, render_template, session, redirect, url_for, request, abort

from functools import wraps

app = Flask(__name__)
app.secret_key = "dev-only-change-later"

ROLES = ["guest", "submitter", "reviewer", "editor", "admin"]

def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") != role:
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
        "reviews": [
            {
                "reviewer": "Reviewer 1",
                "date": "October 3, 2026",
                "recommendation": "Minor revisions",
                "comments": "Clear question and good sampling design. Please explain how soil moisture was measured, and add error bars to Figure 2.",
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
    },
    {
        "id": 3,
        "title": "Tracking sediment in the Chippewa River",
        "discipline": "Environmental Science",
        "submitted": "April 2, 2026",
        "status": "published",
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

@app.route("/dev/role/<role>")
def switch_role(role):
    if role in ROLES:
        session["role"] = role
    return redirect(request.referrer or url_for("home"))


@app.context_processor
def inject_role():
    return {
        "current_role": session.get("role", "guest"),
        "roles": ROLES,
    }

@app.route("/submit")
@role_required("submitter")
def submit_study():
    return render_template("submit_study.html")

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

