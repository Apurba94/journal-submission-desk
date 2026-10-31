# Journal Submission Desk

Keep every paper's journey in one place: where it is, how long it has been there, what the reviewers asked for, and where it should go
next.

* **Desk:** everything under review, with a flag when a paper has waited well past the journal's usual time.
* **Journals:** your own list with fit, impact, acceptance rate, time to decision and fees. **Where to submit next** ranks them by the
  weights you choose, and leaves out journals that already saw this manuscript.
* **Submissions:** each round and decision, building a history for each paper and your own typical decision time.
* **Reviewer comments:** track every comment as to do, changed, or disagree with reason, along with your response and where it was
  addressed.
* **Letters:** builds a response-to-reviewers letter that quotes each comment, grouped by reviewer, warns you about comments still
  unanswered, and also drafts cover letters and a pre-submission checklist.

You enter your own journal figures, so the numbers are the ones you trust. `--demo` opens a temporary database with fictional data.

## From source

```bash
python -m journal_submission_desk
python -m unittest discover -s tests -t .
python build_exe.py
```

## Limits

The program does not connect to journal systems, and it holds no database of journals. The score is only a way to weigh your own
priorities. Read the declarations in a generated cover letter and edit them so that they are true for your paper.

## License

MIT
