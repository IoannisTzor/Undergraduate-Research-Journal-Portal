from datetime import date

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from datetime import date, datetime, timedelta, timezone

from models import db, User, Issue, Submission, SubmissionVersion, SubmissionFile, Review, Advisor, SubmissionWindow


@click.command("seed")
@with_appcontext
def seed_command():
    """Delete all data and fill the database with test data."""

    # Delete existing rows, children before parents
    for model in [SubmissionFile, SubmissionVersion, Review, Submission, Issue, Advisor, User]:
        db.session.query(model).delete()

    # Users (every test account has the password "password123")
    password = generate_password_hash("password123")
    jane = User(first_name="Jane", last_name="Doe", email="jane@example.com", password_hash=password, role="submitter")
    alex = User(first_name="Alex", last_name="Lee", email="alex@example.com", password_hash=password, role="submitter")
    maria = User(first_name="Maria", last_name="Lopez", email="maria@example.com", password_hash=password, role="reviewer", preferred_discipline="biology")
    sam = User(first_name="Sam", last_name="Carter", email="sam@example.com", password_hash=password, role="reviewer", preferred_discipline="computer-science")
    erin = User(first_name="Erin", last_name="Walsh", email="erin@example.com", password_hash=password, role="editor")
    admin = User(first_name="Site", last_name="Admin", email="admin@example.com", password_hash=password, role="admin")


    # A published issue
    spring = Issue(volume=1, semester="spring", year=2026, status="published",
                   published_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
                   editor_note="Welcome to the first issue of the STEM Student Journal.")

    # Submissions
    soil = Submission(author=jane, title="How soil microbes respond to drought",
                      submission_type="research-paper", discipline="biology", mentor="Dr. Ruth Adams",
                      abstract="We compared microbial activity in watered and dry soil over six weeks.",
                      status="revisions-requested")
    cache = Submission(author=alex, title="Measuring cache effects in sorting algorithms",
                       submission_type="research-paper", discipline="computer-science", mentor="Dr. Ken Wu",
                       abstract="A small study of how memory affects how fast sorting really is.",
                       status="under-review")
    river = Submission(author=jane, title="Tracking sediment in the Chippewa River",
                       submission_type="poster", discipline="environmental-science", mentor="Dr. Ruth Adams",
                       abstract="Sediment levels at five sites after spring storms.",
                       status="published", issue=spring)
    solar = Submission(author=alex, title="Solar panel efficiency in Michigan winters",
                       submission_type="review-paper", discipline="engineering", mentor="Dr. Omar Haddad",
                       abstract="A review of published studies on cold-weather solar performance.",
                       status="submitted")
    honey = Submission(author=alex, title="Antibacterial properties of local honey",
                       submission_type="other", discipline="chemistry", mentor="Dr. Lena Fischer",
                       abstract="An interview and photo essay on testing honey from three local farms.",
                       status="accepted")

    # One original version, with one file, for each submission
    for submission in [soil, cache, river, solar, honey]:
        extension = "png" if submission.submission_type == "poster" else "pdf"
        version = SubmissionVersion(submission=submission, version_number=1)
        SubmissionFile(version=version, file_path=f"uploads/test-{submission.title[:10]}.{extension}",
                       original_name=f"study.{extension}")

    # Reviews
    Review(submission=soil, reviewer=maria, assigner=erin, due_date=date(2026, 10, 10),
           status="submitted", recommendation="minor-revisions",
           author_comments="Clear question and good sampling design. Please explain how soil moisture was measured.",
           editor_comments="Figure 2 looks very similar to one in a 2021 paper. Worth checking.")
    Review(submission=soil, reviewer=sam, assigner=erin, due_date=date(2026, 10, 10),
           status="submitted", recommendation="minor-revisions",
           author_comments="Strong discussion section. The abstract should mention the six-week timeframe.")
    Review(submission=cache, reviewer=maria, assigner=erin, due_date=date(2026, 11, 15),
           status="not-started")


    #Advisors
    advisors = [
    Advisor(first_name="Ruth", last_name="Adams", email="adams1r@example.edu", discipline="biology"),
    Advisor(first_name="Ken", last_name="Wu", email="wu1k@example.edu", discipline="computer-science"),
    Advisor(first_name="Omar", last_name="Haddad", email="hadda1o@example.edu", discipline="engineering"),
    Advisor(first_name="Lena", last_name="Fischer", email="fisch1l@example.edu", discipline="chemistry"),
    ]
    db.session.add_all([jane, alex, maria, sam, erin, admin, spring, *advisors])
    db.session.commit()
    click.echo("Database seeded with test data.")

    #submissionWindow
    window = SubmissionWindow(
    opens_on=date.today() - timedelta(days=30),
    closes_on=date.today() + timedelta(days=60),
    )