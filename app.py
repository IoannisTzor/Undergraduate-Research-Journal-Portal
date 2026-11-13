import os
from functools import wraps

from flask import Flask, render_template, session, redirect, url_for, request, abort, g, flash, send_from_directory
from dotenv import load_dotenv
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from seed import seed_command
from datetime import date, datetime, timezone
from models import db, User, Submission, SubmissionVersion, SubmissionFile, Review, Issue, Advisor
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
ASSIGNABLE_ROLES = [role for role in ROLES if role != "guest"]

def change_role(user):
    new_role = request.form.get("role", "")
    if new_role not in ASSIGNABLE_ROLES:
        flash("Please choose a valid role.", "error")
        return
    if user.id == g.user.id:
        flash("You can't change your own role.", "error")
        return
    if new_role == user.role:
        flash(f"{user.first_name} {user.last_name} is already a {new_role}.", "error")
        return

    user.role = new_role
    db.session.commit()
    flash(f"{user.first_name} {user.last_name} is now a {new_role}.", "success")


def delete_user(user):
    name = f"{user.first_name} {user.last_name}"
    if user.id == g.user.id:
        flash("You can't delete your own account.", "error")
        return

    has_reviews = db.session.scalars(
        db.select(Review).where(db.or_(Review.reviewer_id == user.id, Review.assigned_by == user.id))
    ).first()
    if user.submissions or has_reviews:
        flash(f"{name} has submissions or reviews on the site, so their account can't be deleted. You can change their role instead.", "error")
        return

    db.session.delete(user)
    db.session.commit()
    flash(f"The account for {name} was deleted.", "success")


def set_discipline(user):
    discipline = request.form.get("discipline", "")
    if user.role != "reviewer":
        flash("Only reviewers have a preferred discipline.", "error")
        return
    if discipline and discipline not in DISCIPLINES:
        flash("Please choose a valid discipline.", "error")
        return

    user.preferred_discipline = discipline or None
    db.session.commit()
    if discipline:
        flash(f"{user.first_name} {user.last_name} now prefers {DISCIPLINES[discipline]}.", "success")
    else:
        flash(f"{user.first_name} {user.last_name} no longer has a preferred discipline.", "success")

def render_advisors(form):
    advisors = db.session.scalars(
        db.select(Advisor).order_by(Advisor.discipline, Advisor.last_name)
    ).all()
    return render_template("advisors.html", advisors=advisors, form=form)


def add_advisor():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    discipline = request.form.get("discipline", "")

    errors = []
    if not first_name or not last_name:
        errors.append("Please enter the advisor's first and last name.")
    if "@" not in email or "." not in email.split("@")[-1]:
        errors.append("Please enter a valid email address.")
    if discipline not in DISCIPLINES:
        errors.append("Please choose a discipline.")

    if not errors:
        existing = db.session.scalars(
            db.select(Advisor).where(Advisor.email == email, Advisor.discipline == discipline)
        ).first()
        if existing:
            errors.append(f"{existing.first_name} {existing.last_name} is already an advisor for {DISCIPLINES[discipline]}.")

    if errors:
        for error in errors:
            flash(error, "error")
        return render_advisors(request.form)

    db.session.add(Advisor(first_name=first_name, last_name=last_name, email=email, discipline=discipline))
    db.session.commit()
    flash(f"{first_name} {last_name} was added as an advisor for {DISCIPLINES[discipline]}.", "success")
    return redirect(url_for("manage_advisors"))


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
WITHDRAWABLE = ["submitted", "under-review", "revisions-requested", "revised", "accepted"]

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

def approve_rubric(submission):
    review = db.session.get(Review, request.form.get("review_id", type=int) or 0)
    if review is None or review.submission_id != submission.id or not review.rubric_file:
        abort(404)
    review.rubric_approved = True
    db.session.commit()
    flash(f"The rubric from {review.reviewer.first_name} {review.reviewer.last_name} is now visible to the author.", "success")

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
    can_withdraw = submission.status in WITHDRAWABLE and submission.issue_id is None
    return render_template(
        "submission_details.html",
        submission=submission,
        reviews=reviews,
        form=form,
        can_withdraw=can_withdraw,
    )

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

def withdraw_submission(submission):
    if submission.status not in WITHDRAWABLE:
        flash("This submission can no longer be withdrawn.", "error")
        return redirect(url_for("submission_details", submission_id=submission.id))
    if submission.issue_id is not None:
        flash("This study is already part of an issue being prepared. Please contact the editor to withdraw it.", "error")
        return redirect(url_for("submission_details", submission_id=submission.id))

    submission.status = "withdrawn"
    for review in submission.reviews:
        if review.status == "not-started":
            review.status = "cancelled"
    db.session.commit()

    flash("Your submission was withdrawn.", "success")
    return redirect(url_for("submission_details", submission_id=submission.id))

def render_issue_form(issue, form, selected_ids):
    if issue:
        available = db.or_(Submission.issue_id.is_(None), Submission.issue_id == issue.id)
    else:
        available = Submission.issue_id.is_(None)
    accepted = db.session.scalars(
        db.select(Submission)
        .where(Submission.status == "accepted", available)
        .order_by(Submission.title)
    ).all()
    drafts = []
    if issue is None:
        drafts = db.session.scalars(
            db.select(Issue).where(Issue.status == "draft").order_by(Issue.year, Issue.volume)
        ).all()
    return render_template(
        "build_issue.html",
        issue=issue,
        accepted=accepted,
        drafts=drafts,
        form=form,
        selected_ids=selected_ids,
    )


def save_issue(issue, action):
    volume = request.form.get("volume", type=int)
    semester = request.form.get("semester", "")
    year = request.form.get("year", type=int)
    editor_note = request.form.get("editor_note", "").strip()
    study_ids = request.form.getlist("study_ids", type=int)

    errors = []
    if volume is None or volume < 1:
        errors.append("Please enter a volume number of 1 or more.")
    if semester not in ["fall", "spring"]:
        errors.append("Please choose a semester.")
    if year is None or year < 2025:
        errors.append("Please enter a valid year.")
    if not study_ids:
        errors.append("Please choose at least one study.")

    studies = []
    if study_ids:
        studies = db.session.scalars(db.select(Submission).where(Submission.id.in_(study_ids))).all()
        for study in studies:
            in_another_issue = study.issue_id is not None and (issue is None or study.issue_id != issue.id)
            if study.status != "accepted" or in_another_issue:
                errors.append(f"{study.title} can no longer be added. Please check the list again.")
        if len(studies) != len(set(study_ids)):
            errors.append("One or more of the chosen studies no longer exists.")

    if not errors:
        existing = db.session.scalars(
            db.select(Issue).where(Issue.volume == volume, Issue.semester == semester, Issue.year == year)
        ).first()
        if existing and (issue is None or existing.id != issue.id):
            errors.append(f"{existing.label} already exists.")

    if errors:
        for error in errors:
            flash(error, "error")
        return render_issue_form(issue, request.form, study_ids)

    if issue is None:
        issue = Issue(status="draft")
    issue.volume = volume
    issue.semester = semester
    issue.year = year
    issue.editor_note = editor_note or None
    db.session.add(issue)

    for study in list(issue.submissions):
        if study.id not in study_ids:
            study.issue = None
    for study in studies:
        study.issue = issue

    if action == "publish":
        publish_issue(issue)
    db.session.commit()

    if action == "publish":
        flash(f"{issue.label} is published and now on the homepage.", "success")
        return redirect(url_for("home"))
    flash(f"{issue.label} was saved as a draft.", "success")
    return redirect(url_for("build_issue"))


def delete_draft(issue):
    label = issue.label
    for study in list(issue.submissions):
        study.issue = None
    db.session.delete(issue)
    db.session.commit()
    flash(f"The draft {label} was deleted. Its studies are available again.", "success")
    return redirect(url_for("build_issue"))


def publish_issue(issue):
    issue.status = "published"
    issue.published_at = datetime.now(timezone.utc)
    for study in issue.submissions:
        study.status = "published"

def publish_draft():
    issue = db.session.get(Issue, request.form.get("issue_id", type=int) or 0)
    if issue is None or issue.status != "draft":
        abort(404)
    publish_issue(issue)
    db.session.commit()
    flash(f"{issue.label} is published and now on the homepage.", "success")
    return redirect(url_for("home"))

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
        action = request.form.get("action")
        if action == "upload-corrections":
            return upload_corrections(submission)
        if action == "withdraw":
            return withdraw_submission(submission)
        abort(400)

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

    if review.status == "cancelled":
        flash("This review was cancelled because the author withdrew their submission.", "error")
        return redirect(url_for("my_assignments"))

    # Read the form
    recommendation = request.form.get("recommendation", "")
    author_comments = request.form.get("author_comments", "").strip()
    editor_comments = request.form.get("editor_comments", "").strip()
    rubric = request.files.get("rubric_file")
    has_rubric = rubric is not None and rubric.filename != ""

    # Check it
    errors = []
    if recommendation not in RECOMMENDATIONS:
        errors.append("Please choose a recommendation.")
    if not author_comments:
        errors.append("Please write your comments for the author.")
    if not has_rubric:
        errors.append("Please upload your completed rubric.")
    elif not is_valid_file(rubric, ["docx"]):
        errors.append(f"{rubric.filename} isn't a valid Word document.")

    if errors:
        for error in errors:
            flash(error, "error")
        return render_template("write_review.html", review=review, form=request.form)

    # Save it
    saved_path = None
    try:
        stored_name = save_upload(rubric, app.config["UPLOAD_FOLDER"])
        saved_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
        review.rubric_file = stored_name
        review.rubric_approved = False
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
        action = request.form.get("action")
        if action == "approve-rubric":
            approve_rubric(submission)
        elif submission.status in ["accepted", "rejected", "published", "withdrawn"]:
            flash("A decision has already been made on this submission.", "error")
        elif action == "assign":
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

    advisors = db.session.scalars(
        db.select(Advisor)
        .where(Advisor.discipline == submission.discipline)
        .order_by(Advisor.last_name)
    ).all()

    matching_reviewers = [user for user in reviewer_options if user.preferred_discipline == submission.discipline]
    other_reviewers = [user for user in reviewer_options if user.preferred_discipline != submission.discipline]

    submitted_reviews = [review for review in submission.reviews if review.status == "submitted"]
    return render_template(
        "manage_submission.html",
        submission=submission,
        reviewer_options=reviewer_options,
        matching_reviewers=matching_reviewers,
        other_reviewers=other_reviewers,
        submitted_reviews=submitted_reviews,
        advisors=advisors,
    )

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

@app.route("/editor/build-issue", methods=["GET", "POST"])
@role_required("editor")
def build_issue():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "publish-draft":
            return publish_draft()
        if action in ["draft", "publish"]:
            return save_issue(None, action)
        abort(400)
    return render_issue_form(None, form={}, selected_ids=[])


@app.route("/editor/issues/<int:issue_id>/edit", methods=["GET", "POST"])
@role_required("editor")
def edit_issue(issue_id):
    issue = db.session.get(Issue, issue_id)
    if issue is None or issue.status != "draft":
        abort(404)

    if request.method == "POST":
        action = request.form.get("action")
        if action in ["draft", "publish"]:
            return save_issue(issue, action)
        if action == "delete":
            return delete_draft(issue)
        abort(400)

    form = {
        "volume": issue.volume,
        "semester": issue.semester,
        "year": issue.year,
        "editor_note": issue.editor_note or "",
    }
    selected_ids = [study.id for study in issue.submissions]
    return render_issue_form(issue, form, selected_ids)

@app.route("/files/<int:file_id>")
def download_file(file_id):
    file = db.session.get(SubmissionFile, file_id)
    if file is None or not can_view_version(g.user, file.version):
        abort(404)
    return send_from_directory(app.config["UPLOAD_FOLDER"], file.file_path, download_name=file.original_name)

@app.route("/reviews/<int:review_id>/rubric")
def download_rubric(review_id):
    review = db.session.get(Review, review_id)
    if review is None or not review.rubric_file:
        abort(404)
    user = g.user
    allowed = user is not None and (
        user.role == "editor"
        or review.reviewer_id == user.id
        or (review.rubric_approved and review.submission.author_id == user.id)
    )
    if not allowed:
        abort(404)
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        review.rubric_file,
        download_name=f"review-rubric-{review.id}.docx",
    )


@app.route("/admin/users", methods=["GET", "POST"])
@role_required("admin")
def manage_users():
    if request.method == "POST":
        user = db.session.get(User, request.form.get("user_id", type=int) or 0)
        if user is None:
            abort(404)
        action = request.form.get("action")
        if action == "change-role":
            change_role(user)
        elif action == "delete":
            delete_user(user)
        elif action == "set-discipline":
            set_discipline(user)
        else:
            abort(400)
        return redirect(url_for("manage_users"))

    users = db.session.scalars(
        db.select(User).order_by(User.role, User.last_name)
    ).all()
    return render_template("manage_users.html", users=users)

@app.route("/editor/advisors", methods=["GET", "POST"])
@role_required("editor")
def manage_advisors():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            return add_advisor()
        if action == "delete":
            advisor = db.session.get(Advisor, request.form.get("advisor_id", type=int) or 0)
            if advisor is None:
                abort(404)
            name = f"{advisor.first_name} {advisor.last_name}"
            db.session.delete(advisor)
            db.session.commit()
            flash(f"{name} was removed from the advisors list.", "success")
            return redirect(url_for("manage_advisors"))
        abort(400)
    return render_advisors(form={})

@app.route("/guidelines")
def guidelines():
    return render_template("guidelines.html", submission_types=SUBMISSION_TYPES)