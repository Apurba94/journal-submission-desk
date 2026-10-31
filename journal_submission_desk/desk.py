"""Submission logic: ranking journals for a manuscript, tracking waits, and building response letters."""
import datetime

MANUSCRIPT_STATUS = ["Drafting", "Ready", "Under review", "Revising", "Accepted", "Published", "Shelved"]
DECISIONS = ["Waiting", "Desk rejected", "Rejected after review", "Major revisions", "Minor revisions", "Accepted", "Withdrawn"]
COMMENT_STATUS = ["To do", "Changed", "Disagree, with reason", "Not applicable"]
OPEN = ("Waiting",)
REVISE = ("Major revisions", "Minor revisions")


def days_between(a, b):
    return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days


def journal_score(j, priorities):
    """0-100 weighted score. priorities: {'fit', 'prestige', 'speed', 'acceptance', 'cost'} weights from 0 to 5.
    Missing journal data scores as average, not as zero, so that unknown does not mean bad."""
    parts = {
        "fit": ((j.get("fit") or 3) - 1) / 4.0,
        "prestige": min(1.0, (j.get("impact") or 0) / 10.0) if j.get("impact") is not None else 0.5,
        "speed": max(0.0, 1 - (j.get("median_days") or 120) / 240.0),
        "acceptance": min(1.0, (j.get("acceptance") or 25) / 50.0),
        "cost": max(0.0, 1 - (j.get("apc") or 0) / 4000.0),
    }
    total = sum(priorities.values()) or 1
    return round(100 * sum(parts[k] * priorities.get(k, 0) for k in parts) / total, 1)


def rank_journals(journals, priorities, tried=()):
    """Best first. Journals already tried for this manuscript are left out."""
    rows = [(journal_score(j, priorities), j) for j in journals if j["id"] not in tried]
    return sorted(rows, key=lambda r: -r[0])


def waiting(submissions, journals, today):
    """Open submissions, longest first, with a nudge when they run past the journal's usual time."""
    by_id = {j["id"]: j for j in journals}
    out = []
    for s in submissions:
        if s["decision"] not in OPEN or not s.get("submitted"):
            continue
        d = days_between(s["submitted"], today)
        j = by_id.get(s["journal_id"]) or {}
        usual = j.get("median_days") or 120
        out.append({"submission": s, "journal": j, "days": d, "usual": usual, "overdue": d > 1.5 * usual})
    return sorted(out, key=lambda r: -r["days"])


def stats(submissions):
    decided = [s for s in submissions if s["decision"] not in OPEN and s.get("submitted") and s.get("decided")]
    durations = sorted(days_between(s["submitted"], s["decided"]) for s in decided)
    desk = sum(1 for s in decided if s["decision"] == "Desk rejected")
    good = sum(1 for s in decided if s["decision"] in REVISE + ("Accepted",))
    return {"total": len(submissions), "decided": len(decided), "desk": desk, "positive": good, "median_days": durations[len(durations) // 2] if durations else None,
            "open": sum(1 for s in submissions if s["decision"] in OPEN)}


def manuscript_history(manuscript_id, submissions, journals):
    by_id = {j["id"]: j["name"] for j in journals}
    return [{"journal": by_id.get(s["journal_id"], "?"), "submitted": s["submitted"], "round": s.get("round") or 1, "decision": s["decision"], "decided": s.get("decided")}
            for s in sorted(submissions, key=lambda x: x["submitted"] or "") if s["manuscript_id"] == manuscript_id]


def review_progress(comments):
    done = sum(1 for c in comments if c["status"] != "To do")
    missing = sum(1 for c in comments if c["status"] != "To do" and not (c.get("response") or "").strip())
    return {"total": len(comments), "done": done, "fraction": done / len(comments) if comments else 0.0, "no_text": missing}


def response_letter(manuscript, journal, comments, author="", editor="Editor"):
    """A response-to-reviewers document, grouped by reviewer, with each comment quoted."""
    rows = ["Dear %s," % editor, "",
            'Thank you for the opportunity to revise our manuscript "%s" for %s. We have addressed the comments of the reviewers as set out below.' % (manuscript, journal), ""]
    groups = {}
    for c in comments:
        groups.setdefault(c.get("reviewer") or "Reviewer", []).append(c)
    for reviewer in sorted(groups):
        rows += [reviewer, "-" * len(reviewer), ""]
        for i, c in enumerate(groups[reviewer], 1):
            rows.append("Comment %d: %s" % (i, (c.get("comment") or "").strip()))
            rows.append("")
            response = (c.get("response") or "").strip() or "[Write your response here.]"
            rows.append("Response: %s" % response)
            if c.get("location"):
                rows.append("(See %s.)" % c["location"])
            rows.append("")
    rows += ["We look forward to your decision.", "", "Yours sincerely,", author or "[Your name]", ""]
    return "\n".join(rows)


def cover_letter(manuscript, journal, kind, summary, author, editor="Editor"):
    return ("Dear %s,\n\nPlease consider our %s, \"%s\", for publication in %s.\n\n%s\n\nThis manuscript has not been published and is not under consideration elsewhere. "
            "All authors have approved the submission and declare no conflicts of interest. [Edit this declaration so that it is true for your paper.]\n\n"
            "Yours sincerely,\n%s\n" % (editor, kind or "manuscript", manuscript, journal, summary or "[Say why this work suits this journal and its readers.]", author or "[Your name]"))


def checklist(manuscript):
    return ["Formatted to the journal's author guidelines", "Word and abstract limits met", "References in the journal's style", "Figures at the required resolution", "Ethics approval stated",
            "Funding and conflicts declared", "Data availability statement included", "All co-authors have approved this version", "Cover letter tailored to this journal",
            "Suggested reviewers prepared, if asked for"]


def next_step(sub):
    d = sub["decision"]
    if d == "Waiting":
        return "Wait. Send a polite status enquiry once it has run well past the journal's usual time."
    if d == "Desk rejected":
        return "Check the journal's scope and move on to the next target. Editors' reasons are worth reading."
    if d == "Rejected after review":
        return "Use the reviews to improve the paper before the next journal."
    if d in REVISE:
        return "Make a list of every comment and answer each one in the response letter."
    if d == "Accepted":
        return "Check the proofs, pay any charges, and record the DOI."
    return ""
