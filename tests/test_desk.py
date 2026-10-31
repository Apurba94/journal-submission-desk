import os
import shutil
import tempfile
import tkinter as tk
import unittest

from journal_submission_desk import app as A
from journal_submission_desk import appkit as ak
from journal_submission_desk import desk as dk

EQUAL = {"fit": 1, "prestige": 1, "speed": 1, "acceptance": 1, "cost": 1}


class TestScoring(unittest.TestCase):
    def test_priorities_change_the_order(self):
        fast = {"id": 1, "fit": 3, "impact": 1, "median_days": 30, "acceptance": 40, "apc": 0}
        famous = {"id": 2, "fit": 3, "impact": 10, "median_days": 200, "acceptance": 8, "apc": 3000}
        self.assertEqual(dk.rank_journals([fast, famous], {"prestige": 5})[0][1]["id"], 2)
        self.assertEqual(dk.rank_journals([fast, famous], {"speed": 5})[0][1]["id"], 1)

    def test_tried_journals_are_excluded(self):
        js = [{"id": 1, "fit": 5}, {"id": 2, "fit": 1}]
        self.assertEqual([j["id"] for _, j in dk.rank_journals(js, EQUAL, tried={1})], [2])

    def test_bounds_and_missing_data(self):
        self.assertTrue(0 <= dk.journal_score({"fit": None, "impact": None, "median_days": None, "acceptance": None, "apc": None}, EQUAL) <= 100)
        self.assertEqual(dk.journal_score({"fit": 5, "impact": 50, "median_days": 1, "acceptance": 90, "apc": 0}, {"fit": 1}), 100)
        self.assertEqual(dk.journal_score({"fit": 1}, {"fit": 1}), 0)
        self.assertEqual(dk.journal_score({"fit": 3}, {}), 0)


class TestTracking(unittest.TestCase):
    def test_waiting_and_overdue(self):
        subs = [{"decision": "Waiting", "submitted": "2026-01-01", "journal_id": 1}, {"decision": "Waiting", "submitted": "2026-05-01", "journal_id": 1},
                {"decision": "Accepted", "submitted": "2026-01-01", "journal_id": 1}, {"decision": "Waiting", "submitted": None, "journal_id": 1}]
        rows = dk.waiting(subs, [{"id": 1, "median_days": 60}], "2026-06-01")
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]["days"], rows[0]["overdue"]), (151, True))
        self.assertFalse(rows[1]["overdue"])

    def test_stats(self):
        subs = [{"decision": "Desk rejected", "submitted": "2026-01-01", "decided": "2026-01-11"}, {"decision": "Accepted", "submitted": "2026-01-01", "decided": "2026-04-11"},
                {"decision": "Major revisions", "submitted": "2026-01-01", "decided": "2026-03-02"}, {"decision": "Waiting", "submitted": "2026-01-01", "decided": None}]
        st = dk.stats(subs)
        self.assertEqual((st["total"], st["decided"], st["desk"], st["positive"], st["open"], st["median_days"]), (4, 3, 1, 2, 1, 60))
        self.assertIsNone(dk.stats([])["median_days"])

    def test_history_and_steps(self):
        s = store()
        m = s.list("manuscript", "title LIKE 'Sleep%'")[0]["id"]
        h = dk.manuscript_history(m, s.list("submission"), s.list("journal"))
        self.assertEqual([x["decision"] for x in h], ["Desk rejected", "Major revisions"])
        for d in dk.DECISIONS[:-1]:
            self.assertTrue(dk.next_step({"decision": d}), d)


class TestLetters(unittest.TestCase):
    def test_progress(self):
        c = [{"status": "Changed", "response": "Done."}, {"status": "To do", "response": ""}, {"status": "Changed", "response": " "}]
        p = dk.review_progress(c)
        self.assertEqual((p["total"], p["done"], p["no_text"]), (3, 2, 1))
        self.assertEqual(dk.review_progress([])["fraction"], 0)

    def test_response_letter(self):
        comments = [{"reviewer": "Reviewer 2", "comment": "B", "response": "", "location": None}, {"reviewer": "Reviewer 1", "comment": "A", "response": "Fixed.", "location": "page 3"}]
        t = dk.response_letter("My paper", "J Test", comments, "Ana", "Dr Lee")
        self.assertTrue(t.startswith("Dear Dr Lee,"))
        self.assertLess(t.index("Reviewer 1"), t.index("Reviewer 2"))
        self.assertIn("Comment 1: A", t)
        self.assertIn("Response: Fixed.", t)
        self.assertIn("(See page 3.)", t)
        self.assertIn("[Write your response here.]", t)
        self.assertIn("Ana", t)

    def test_cover_letter_flags_declaration(self):
        t = dk.cover_letter("P", "J", "review", "", "")
        self.assertIn('"P"', t)
        self.assertIn("[Edit this declaration", t)
        self.assertIn("[Your name]", t)


def store():
    s = ak.Store(A.SCHEMA)
    A.sample(s)
    return s


class TestGui(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = ak.Store(A.SCHEMA, os.path.join(self.dir, "t.sqlite3"), A.APP.APP_NAME)
        A.sample(self.store)
        try:
            self.app = A.APP(self.store)
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.errors = []
        self.app.report_callback_exception = lambda e, v, t: self.errors.append(repr(v))
        self.app.update()

    def tearDown(self):
        self.store.close()
        self.app.destroy()
        shutil.rmtree(self.dir, ignore_errors=True)
        self.assertEqual(self.errors, [])

    def test_every_screen_in_both_themes(self):
        for theme in ("Dark", "Light"):
            self.app.set_theme(theme)
            for t in self.app.titles():
                self.app.navigate(t)
                self.app.update()

    def test_desk_flags_overdue(self):
        d = self.app.views["Desk"]
        row = d.wait.tree.item(d.wait.tree.get_children()[0], "values")
        self.assertEqual(row[4], "Time for a polite enquiry")

    def test_journal_ranking_leaves_out_tried(self):
        self.app.navigate("Journals")
        j = self.app.views["Journals"]
        j.m.set("Sleep and memory in students (sample)")
        j.rank()
        names = [j.table.tree.item(i, "values")[1] for i in j.table.tree.get_children()]
        self.assertEqual(names, ["Demo Psychology Review"])

    def test_letter_shows_progress(self):
        self.app.navigate("Letters")
        l = self.app.views["Letters"]
        self.assertIn("Comment 1: The sample size", ak.get_text(l.text))
        self.assertIn("1 comment(s) still to do", l.warn.cget("text"))
        for kind in ("Cover letter", "Submission checklist"):
            l.kind.set(kind)
            l.build()
            self.assertTrue(ak.get_text(l.text).strip())

    def test_empty_database(self):
        self.store.close()
        self.app.destroy()
        self.store = ak.Store(A.SCHEMA, os.path.join(self.dir, "e.sqlite3"), A.APP.APP_NAME)
        self.app = A.APP(self.store)
        for t in self.app.titles():
            self.app.navigate(t)
            self.app.update()


if __name__ == "__main__":
    unittest.main()
