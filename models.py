from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="submitter")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    submissions = db.relationship("Submission", back_populates="author")


class Issue(db.Model):
    __tablename__ = "issues"

    id = db.Column(db.Integer, primary_key=True)
    volume = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.String(10), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    editor_note = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="draft")
    published_at = db.Column(db.DateTime(timezone=True))

    submissions = db.relationship("Submission", back_populates="issue")


class Submission(db.Model):
    __tablename__ = "submissions"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    issue_id = db.Column(db.Integer, db.ForeignKey("issues.id"))
    title = db.Column(db.String(300), nullable=False)
    submission_type = db.Column(db.String(30), nullable=False)
    discipline = db.Column(db.String(50), nullable=False)
    coauthors = db.Column(db.String(500))
    mentor = db.Column(db.String(200), nullable=False)
    abstract = db.Column(db.Text)
    status = db.Column(db.String(30), nullable=False, default="submitted")
    decision_note = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    author = db.relationship("User", back_populates="submissions")
    issue = db.relationship("Issue", back_populates="submissions")
    reviews = db.relationship("Review", back_populates="submission")
    versions = db.relationship(
        "SubmissionVersion",
        back_populates="submission",
        order_by="SubmissionVersion.version_number",
    )


class SubmissionVersion(db.Model):
    __tablename__ = "submission_versions"
    __table_args__ = (db.UniqueConstraint("submission_id", "version_number"),)

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submissions.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    response_note = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    submission = db.relationship("Submission", back_populates="versions")
    files = db.relationship("SubmissionFile", back_populates="version")


class SubmissionFile(db.Model):
    __tablename__ = "submission_files"

    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey("submission_versions.id"), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)

    version = db.relationship("SubmissionVersion", back_populates="files")


class Review(db.Model):
    __tablename__ = "reviews"
    __table_args__ = (db.UniqueConstraint("submission_id", "reviewer_id"),)

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submissions.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    status = db.Column(db.String(20), nullable=False, default="not-started")
    recommendation = db.Column(db.String(30))
    author_comments = db.Column(db.Text)
    editor_comments = db.Column(db.Text)
    annotated_file = db.Column(db.String(500))
    submitted_at = db.Column(db.DateTime(timezone=True))

    submission = db.relationship("Submission", back_populates="reviews")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
    assigner = db.relationship("User", foreign_keys=[assigned_by])