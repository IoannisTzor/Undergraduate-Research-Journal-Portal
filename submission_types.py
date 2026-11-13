SUBMISSION_TYPES = {
    "research-paper": {
        "label": "Research paper",
        "description": "A research paper details original research conducted by the author(s), including in-depth analysis and evaluation.",
        "format_note": "APA 7th Edition | PDF",
        "file_formats": ["pdf"],
        "multiple_files": False,
        "required_elements": ["title page", "abstract", "introduction", "methodology", "results", "analysis", "conclusion", "references"],
        "max_pages": 20,
        "abstract_label": "Abstract",
        "abstract_required": True,
        "submit_label" : "Submit a Reasearch Paper",
        "rubric_file": "rubrics/research-paper.docx"
    },
    "review-paper": {
        "label": "Review paper",
        "description": "A review paper is a synthesis of existing literature, aiming to analyze or discover gaps, not add additional findings.",
        "format_note": "APA 7th Edition | PDF",
        "file_formats": ["pdf"],
        "multiple_files": False,
        "required_elements": ["title page", "abstract", "analysis", "conclusion", "references"],
        "max_pages": 10,
        "abstract_label": "Abstract",
        "abstract_required": True,
        "submit_label" : "Submit a Review",
        "rubric_file": "rubrics/review-paper.docx"
    },
    "poster": {
        "label": "Poster",
        "description": "A poster is a visual summary of a research project.",
        "format_note": "48 x 36 inches or 36 x 48 inches | PNG",
        "file_formats": ["png"],
        "multiple_files": False,
        "required_elements": ["research question", "background", "method", "results", "conclusion", "acknowledgements", "references"],
        "max_pages": None,
        "abstract_label": "Short description",
        "abstract_required": False,
        "submit_label" : "Submit a Poster",
        "rubric_file": "rubrics/poster.docx"
    },
    "other": {
        "label": "Other",
        "description": "If your submission does not fall into the categories above, but you still feel it would be a good fit for our journal, you are welcome to submit. This may include creative projects, interviews, visualization of findings, or other alternative ways of sharing STEM work.",
        "format_note": "APA 7th Edition, when applicable (such as references) | PDF or PNG(s)",
        "file_formats": ["pdf", "png"],
        "multiple_files": True,
        "required_elements": ["summary or abstract"],
        "max_pages": 15,
        "abstract_label": "Summary or abstract",
        "abstract_required": True,
        "submit_label" : "Submit Another Kind of Work",
        "rubric_file": "rubrics/other.docx"
    },
    
}
DISCIPLINES = {
    "biology": "Biology",
    "chemistry": "Chemistry",
    "computer-science": "Computer Science",
    "engineering": "Engineering",
    "environmental-science": "Environmental Science",
    "mathematics": "Mathematics",
    "physics": "Physics",
}

RECOMMENDATIONS = {
    "accept": "Accept",
    "minor-revisions": "Minor revisions",
    "major-revisions": "Major revisions",
    "reject": "Reject",
}