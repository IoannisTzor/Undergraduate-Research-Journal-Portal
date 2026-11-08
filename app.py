import os
from functools import wraps

from flask import Flask, render_template, session, redirect, url_for, request, abort, g, flash
from dotenv import load_dotenv
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from seed import seed_command
from datetime import date, datetime, timezone
from models import db, User, Submission, SubmissionVersion, SubmissionFile, Review, Issue
from submission_types import SUBMISSION_TYPES, DISCIPLINES, RECOMMENDATIONS
from uploads import file_extension, is_valid_file, save_upload

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
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

def parse_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None

DECISIONS = ["accepted", "revisions-requested", "rejected"]

def assign_reviewer(submission):
    reviewer_id = request.form.get("reviewer_id", type=int)
    reviewer = db.session.get(User, reviewer_id) if reviewer_id else None
    due_date = parse_date(request.form.get("due_date", ""))

    errors = []
    if reviewer is None or reviewer.role != "reviewer":
        errors.append("Please choose a reviewer.")
    elif any(review.reviewer_id == reviewer.id for review in submission.current_reviews):
        errors.append(f"{reviewer.first_name} {reviewer.last_name} is already reviewing this version.")
    if due_date is None:
        errors.append("Please choose a due date.")
    elif due_date <= date.today():
        errors.append("The due date must be in the future.")

    if errors:
        for error in errors:
            flash(error, "error")
        return

    db.session.add(Review(
        submission=submission,
        reviewer=reviewer,
        assigner=g.user,
        due_date=due_date,
        review_round=submission.current_round,
    ))
    if submission.status in ["submitted", "revised"]:
        submission.status = "under-review"
    db.session.commit()
    flash(f"{reviewer.first_name} {reviewer.last_name} was assigned to review this study.", "success")


def record_decision(submission):
    decision = request.form.get("decision", "")
    note = request.form.get("decision_note", "").strip()

    errors = []
    if decision not in DECISIONS:
        errors.append("Please choose a decision.")
    if not note:
        errors.append("Please write a message to the author.")

    if errors:
        for error in errors:
            flash(error, "error")
        return

    submission.status = decision
    submission.decision_note = note
    db.session.commit()
    flash("Your decision was sent to the author.", "success")
    
def file_errors(files, type_info):
    errors = []
    if not files:
        errors.append("Please choose a file to upload.")
    elif len(files) > 1 and not type_info["multiple_files"]:
        errors.append("Please upload a single file.")
    for file in files:
        if not is_valid_file(file, type_info["file_formats"]):
            formats = " or ".join(type_info["file_formats"]).upper()
            errors.append(f"{file.filename} isn't a valid {formats} file.")
    return errors

def render_submission_details(submission, form):
    reviews = [review for review in submission.reviews if review.status == "submitted"]
    return render_template("submission_details.html", submission=submission, reviews=reviews, form=form)

def upload_corrections(submission):
    if submission.status != "revisions-requested":
        flash("You can only upload corrections when the editor has requested revisions.", "error")
        return redirect(url_for("submission_details", submission_id=submission.id))

    type_info = SUBMISSION_TYPES[submission.submission_type]
    response = request.form.get("response", "").strip()
    files = [file for file in request.files.getlist("revised_files") if file.filename]

    errors = []
    if not response:
        errors.append("Please explain what you changed.")
    errors += file_errors(files, type_info)

    if errors:
        for error in errors:
            flash(error, "error")
        return render_submission_details(submission, request.form)

    next_number = submission.current_round + 1
    version = SubmissionVersion(submission=submission, version_number=next_number, response_note=response)

    saved_paths = []
    try:
        for file in files:
            stored_name = save_upload(file, app.config["UPLOAD_FOLDER"])
            saved_paths.append(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
            SubmissionFile(version=version, file_path=stored_name, original_name=file.filename[:255])
        db.session.add(version)
        submission.status = "revised"
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in saved_paths:
            if os.path.exists(path):
                os.remove(path)
        flash("Something went wrong while uploading your corrections. Please try again.", "error")
        return render_submission_details(submission, request.form)

    flash("Your corrections were uploaded. The editor will take it from here.", "success")
    return redirect(url_for("submission_details", submission_id=submission.id))

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

@app.route("/past-issues")
def past_issues():
    published = db.session.scalars(
        db.select(Issue)
        .where(Issue.status == "published")
        .order_by(Issue.published_at.desc())
    ).all()
    return render_template("past_issues.html", issues=published[1:])

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
    flash(f"Now viewing as {user.first_name} {user.last_name}.", "success")
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
        "disciplines": DISCIPLINES,
        "recommendations": RECOMMENDATIONS,
    }

@app.template_filter("date")
def format_date(value):
    if value is None:
        return ""
    return f"{value.strftime('%B')} {value.day}, {value.year}"

@app.route("/submit/<submission_type>", methods=["GET", "POST"])
@role_required("submitter")
def submit_study(submission_type):
    type_info = SUBMISSION_TYPES.get(submission_type)
    if type_info is None:
        abort(404)

    if request.method == "GET":
        return render_template("submit_study.html", type_key=submission_type, type_info=type_info, form={})

    # Read the form
    title = request.form.get("title", "").strip()
    discipline = request.form.get("discipline", "")
    coauthors = request.form.get("coauthors", "").strip()
    mentor = request.form.get("mentor", "").strip()
    abstract = request.form.get("abstract", "").strip()
    files = [file for file in request.files.getlist("study_files") if file.filename]

    # Check it
    errors = []
    if not title:
        errors.append("Please enter a title.")
    if discipline not in DISCIPLINES:
        errors.append("Please choose a discipline.")
    if not mentor:
        errors.append("Please enter your faculty mentor.")
    if type_info["abstract_required"] and not abstract:
        errors.append(f"Please enter your {type_info['abstract_label'].lower()}.")
    if len(abstract.split()) > 250:
        errors.append(f"Your {type_info['abstract_label'].lower()} must be 250 words or fewer.")
    if not request.form.get("confirm"):
        errors.append("Please confirm the statement at the bottom of the form.")
    errors += file_errors(files, type_info)

    if errors:
        for error in errors:
            flash(error, "error")
        return render_template("submit_study.html", type_key=submission_type, type_info=type_info, form=request.form)

    # Save it
    submission = Submission(
        author=g.user,
        title=title,
        submission_type=submission_type,
        discipline=discipline,
        coauthors=coauthors or None,
        mentor=mentor,
        abstract=abstract or None,
    )
    version = SubmissionVersion(submission=submission, version_number=1)

    saved_paths = []
    try:
        for file in files:
            stored_name = save_upload(file, app.config["UPLOAD_FOLDER"])
            saved_paths.append(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
            SubmissionFile(version=version, file_path=stored_name, original_name=file.filename[:255])
        db.session.add(submission)
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in saved_paths:
            if os.path.exists(path):
                os.remove(path)
        flash("Something went wrong while saving your submission. Please try again.", "error")
        return render_template("submit_study.html", type_key=submission_type, type_info=type_info, form=request.form)

    flash("Your study was submitted! You can follow its progress here.", "success")
    return redirect(url_for("submission_details", submission_id=submission.id))

@app.route("/my-submissions")
@role_required("submitter")
def my_submissions():
    submissions = db.session.scalars(
        db.select(Submission)
        .where(Submission.author_id == g.user.id)
        .order_by(Submission.submitted_at.desc())
    ).all()
    return render_template("my_submissions.html", submissions=submissions)

@app.route("/my-submissions/<int:submission_id>", methods=["GET", "POST"])
@role_required("submitter")
def submission_details(submission_id):
    submission = db.session.get(Submission, submission_id)
    if submission is None or submission.author_id != g.user.id:
        abort(404)

    if request.method == "POST":
        return upload_corrections(submission)

    return render_submission_details(submission, form={})

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

@app.route("/assignments/<int:review_id>", methods=["GET", "POST"])
@role_required("reviewer")
def write_review(review_id):
    review = db.session.get(Review, review_id)
    if review is None or review.reviewer_id != g.user.id:
        abort(404)

    if request.method == "GET":
        return render_template("write_review.html", review=review, form={})

    if review.status == "submitted":
        flash("You've already submitted this review.", "error")
        return redirect(url_for("write_review", review_id=review.id))

    # Read the form
    recommendation = request.form.get("recommendation", "")
    author_comments = request.form.get("author_comments", "").strip()
    editor_comments = request.form.get("editor_comments", "").strip()
    annotated = request.files.get("annotated_file")
    has_file = annotated is not None and annotated.filename != ""

    # Check it
    errors = []
    if recommendation not in RECOMMENDATIONS:
        errors.append("Please choose a recommendation.")
    if not author_comments:
        errors.append("Please write your comments for the author.")
    if has_file and not is_valid_file(annotated, ["pdf", "png"]):
        errors.append(f"{annotated.filename} isn't a valid PDF or PNG file.")

    if errors:
        for error in errors:
            flash(error, "error")
        return render_template("write_review.html", review=review, form=request.form)

    # Save it
    saved_path = None
    try:
        if has_file:
            stored_name = save_upload(annotated, app.config["UPLOAD_FOLDER"])
            saved_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
            review.annotated_file = stored_name
        review.recommendation = recommendation
        review.author_comments = author_comments
        review.editor_comments = editor_comments or None
        review.status = "submitted"
        review.submitted_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback()
        if saved_path and os.path.exists(saved_path):
            os.remove(saved_path)
        flash("Something went wrong while saving your review. Please try again.", "error")
        return render_template("write_review.html", review=review, form=request.form)

    flash("Thank you! Your review was submitted.", "success")
    return redirect(url_for("my_assignments"))

@app.route("/editor/submissions")
@role_required("editor")
def all_submissions():
    submissions = db.session.scalars(
        db.select(Submission).order_by(Submission.submitted_at.desc())
    ).all()
    return render_template("all_submissions.html", submissions=submissions)

@app.route("/editor/submissions/<int:submission_id>", methods=["GET", "POST"])
@role_required("editor")
def manage_submission(submission_id):
    submission = db.session.get(Submission, submission_id)
    if submission is None:
        abort(404)

    if request.method == "POST":
        if submission.status in ["accepted", "rejected", "published"]:
            flash("A decision has already been made on this submission.", "error")
        else:
            action = request.form.get("action")
            if action == "assign":
                assign_reviewer(submission)
            elif action == "decide":
                record_decision(submission)
            else:
                abort(400)
        return redirect(url_for("manage_submission", submission_id=submission.id))

    assigned_ids = [review.reviewer_id for review in submission.current_reviews]
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