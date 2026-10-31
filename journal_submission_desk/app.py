"""Journal Submission Desk desktop program."""
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import appkit as ak
from . import desk as dk
from .appkit import Entity, Field, entities

SCHEMA = entities(
    Entity("manuscript", "Manuscript", "Manuscripts", "title", [
        Field("title", "Title", required=True, list_col=True, width=40),
        Field("status", "Status", "choice", dk.MANUSCRIPT_STATUS, default="Drafting", list_col=True, width=13),
        Field("kind", "Type", list_col=True, width=16),
        Field("authors", "Authors"),
        Field("summary", "Why it matters", "long"),
        Field("notes", "Notes", "long"),
    ]),
    Entity("journal", "Journal", "Journals", "name", [
        Field("name", "Journal", required=True, list_col=True, width=32),
        Field("fit", "Fit (1-5)", "int", default=3, list_col=True, width=8),
        Field("impact", "Impact factor", "number", list_col=True, width=9),
        Field("acceptance", "Acceptance %", "number", list_col=True, width=11),
        Field("median_days", "Days to decision", "int", list_col=True, width=13),
        Field("apc", "Publication fee", "number", list_col=True, width=12),
        Field("open_access", "Open access", "bool"),
        Field("url", "Author guidelines"),
        Field("notes", "Scope and notes", "long"),
    ], "name"),
    Entity("submission", "Submission", "Submissions", "decision", [
        Field("manuscript_id", "Manuscript", "ref", ref="manuscript", required=True, list_col=True, width=30),
        Field("journal_id", "Journal", "ref", ref="journal", required=True, list_col=True, width=24),
        Field("round", "Round", "int", default=1, list_col=True, width=6),
        Field("submitted", "Submitted", "date", list_col=True, width=11),
        Field("decision", "Decision", "choice", dk.DECISIONS, default="Waiting", list_col=True, width=18),
        Field("decided", "Decided", "date", list_col=True, width=11),
        Field("due", "Revision due", "date", list_col=True, width=11),
        Field("notes", "Notes", "long"),
    ], "COALESCE(submitted, '9999') DESC, id DESC"),
    Entity("comment", "Reviewer comment", "Reviewer comments", "comment", [
        Field("submission_id", "Submission", "ref", ref="submission", required=True),
        Field("reviewer", "Reviewer", default="Reviewer 1", list_col=True, width=12),
        Field("comment", "Comment", "long", required=True, list_col=True, width=46),
        Field("status", "Status", "choice", dk.COMMENT_STATUS, default="To do", list_col=True, width=18),
        Field("location", "Where addressed"),
        Field("response", "Your response", "long"),
    ]),
)


def sample(store):
    day = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
    m1 = store.insert("manuscript", title="Sleep and memory in students (sample)", status="Revising", kind="Empirical article", authors="A. Sample, B. Example",
                      summary="A preregistered replication with a larger sample.")
    m2 = store.insert("manuscript", title="A review of sleep interventions (sample)", status="Under review", kind="Review")
    j1 = store.insert("journal", name="Sample Journal of Sleep", fit=5, impact=4.2, acceptance=22, median_days=90, apc=0)
    j2 = store.insert("journal", name="Example Memory Letters", fit=4, impact=6.8, acceptance=12, median_days=60, apc=2500, open_access=1)
    j3 = store.insert("journal", name="Demo Psychology Review", fit=3, impact=2.1, acceptance=40, median_days=150, apc=0)
    s1 = store.insert("submission", manuscript_id=m1, journal_id=j2, submitted=day(-200), decision="Desk rejected", decided=day(-190))
    s2 = store.insert("submission", manuscript_id=m1, journal_id=j1, submitted=day(-120), decision="Major revisions", decided=day(-20), due=day(40))
    store.insert("submission", manuscript_id=m2, journal_id=j3, submitted=day(-260), decision="Waiting")
    store.insert("comment", submission_id=s2, reviewer="Reviewer 1", comment="The sample size justification is unclear.", status="Changed", response="We added a power analysis.", location="Method, page 7")
    store.insert("comment", submission_id=s2, reviewer="Reviewer 1", comment="Please report effect sizes.", status="To do")
    store.insert("comment", submission_id=s2, reviewer="Reviewer 2", comment="The discussion overreaches.", status="Disagree, with reason", response="We keep the claim and explain why in the limitations.")
    _ = s1


class Desk(ttk.Frame):
    title = "Desk"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.top = ttk.Frame(self)
        self.top.pack(fill="x", pady=(0, 8))
        ttk.Label(self, text="Waiting for a decision", style="Muted.TLabel").pack(anchor="w")
        self.wait = ak.Table(self, app, [("m", "Manuscript", 36), ("j", "Journal", 24), ("d", "Days waiting", 11), ("u", "Usual", 7), ("n", "Status", 30)], height=6)
        self.wait.pack(fill="both", expand=True)
        ttk.Label(self, text="Revisions due", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self.rev = ak.Table(self, app, [("m", "Manuscript", 36), ("j", "Journal", 24), ("dec", "Decision", 16), ("due", "Due", 11), ("p", "Comments answered", 16)], height=5)
        self.rev.pack(fill="both", expand=True)

    def refresh(self):
        s = self.app.store
        subs, journals = s.list("submission"), s.list("journal")
        st = dk.stats(subs)
        rows = dk.waiting(subs, journals, ak.today())
        for w in self.top.winfo_children():
            w.destroy()
        ak.tiles(self.top, [("Manuscripts", str(s.count("manuscript")), "%d accepted or published" % s.count("manuscript", "status IN ('Accepted','Published')")),
                            ("Under review", str(st["open"]), ""), ("Overdue", str(sum(1 for r in rows if r["overdue"])), "past 1.5 times the usual wait"),
                            ("Typical decision", "%s days" % st["median_days"] if st["median_days"] is not None else "-", "your median"),
                            ("Positive decisions", "%d of %d" % (st["positive"], st["decided"]), "revise or accept")]).pack(fill="x")
        self.wait.fill([(i, (s.label("manuscript", r["submission"]["manuscript_id"]), r["journal"].get("name", ""), r["days"], r["usual"],
                             "Time for a polite enquiry" if r["overdue"] else "Within the usual time"), "danger" if r["overdue"] else None) for i, r in enumerate(rows)])
        rev = []
        for x in subs:
            if x["decision"] in dk.REVISE:
                p = dk.review_progress(s.list("comment", "submission_id=?", (x["id"],)))
                rev.append((x["id"], (s.label("manuscript", x["manuscript_id"]), s.label("journal", x["journal_id"]), x["decision"], x["due"] or "", "%d of %d" % (p["done"], p["total"]))))
        self.rev.fill(rev)


class Simple(ttk.Frame):
    entity = None

    def __init__(self, parent, app):
        super().__init__(parent)
        self.view = ak.EntityView(self, app, self.entity)
        self.view.pack(fill="both", expand=True)
        self.refresh, self.commit = self.view.refresh, self.view.commit


class Manuscripts(Simple):
    title, entity = "Manuscripts", "manuscript"


class Submissions(Simple):
    title, entity = "Submissions", "submission"


class Journals(ttk.Frame):
    title = "Journals"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.view = ak.EntityView(nb, app, "journal")
        rank = ttk.Frame(nb, padding=8)
        nb.add(self.view, text="Journals")
        nb.add(rank, text="Where to submit next")
        top = ttk.Frame(rank)
        top.pack(fill="x")
        self.m = tk.StringVar()
        self.box = ak.labeled_combo(top, "Manuscript", self.m, [], 34, self.rank)
        self.box.pack(side="left", padx=(0, 10))
        self.w = {}
        for k, label, d in (("fit", "Fit", 5), ("prestige", "Prestige", 2), ("speed", "Speed", 2), ("acceptance", "Odds", 2), ("cost", "Low cost", 1)):
            v = tk.IntVar(value=d)
            f = ttk.Frame(top)
            f.pack(side="left", padx=(0, 6))
            ttk.Label(f, text=label, style="Muted.TLabel").pack(anchor="w")
            ttk.Spinbox(f, from_=0, to=5, width=4, textvariable=v, command=self.rank).pack()
            self.w[k] = v
        ttk.Button(top, text="Rank", style="Accent.TButton", command=self.rank).pack(side="left", anchor="s")
        ttk.Label(rank, text="Journals this manuscript has already tried are left out. Weights run from 0 to 5.", style="Muted.TLabel").pack(anchor="w", pady=4)
        self.table = ak.Table(rank, app, [("s", "Score", 7), ("n", "Journal", 32), ("f", "Fit", 5), ("i", "Impact", 7), ("a", "Acceptance", 10), ("d", "Days", 6), ("c", "Fee", 8)])
        self.table.pack(fill="both", expand=True)
        self.ids = {}

    def rank(self):
        s = self.app.store
        mid = self.ids.get(self.m.get())
        tried = {x["journal_id"] for x in s.list("submission", "manuscript_id=?", (mid,))} if mid else set()
        try:
            pr = {k: float(v.get()) for k, v in self.w.items()}
        except (tk.TclError, ValueError):
            return
        rows = dk.rank_journals(s.list("journal"), pr, tried)
        g = lambda v: "" if v is None else "%g" % v
        self.table.fill([[sc, j["name"], j["fit"] or "", g(j["impact"]), g(j["acceptance"]), j["median_days"] or "", g(j["apc"])] for sc, j in rows])

    def refresh(self):
        self.view.refresh()
        s = self.app.store
        self.ids = {r["title"]: r["id"] for r in s.list("manuscript")}
        self.box.box.configure(values=list(self.ids))
        if self.m.get() not in self.ids and self.ids:
            self.m.set(next(iter(self.ids)))
        self.rank()

    def commit(self):
        return self.view.commit()


class Reviews(ttk.Frame):
    title = "Reviewer comments"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.view = ak.EntityView(self, app, "comment", split=0.55, on_select=None)
        self.view.pack(fill="both", expand=True)
        self.refresh, self.commit = self.view.refresh, self.view.commit


class Letters(ttk.Frame):
    title = "Letters"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        top = ttk.Frame(self)
        top.pack(fill="x")
        self.sub, self.kind, self.author, self.editor = tk.StringVar(), tk.StringVar(value="Response to reviewers"), tk.StringVar(), tk.StringVar(value="Editor")
        self.box = ak.labeled_combo(top, "Submission", self.sub, [], 44, self.build)
        self.box.pack(side="left", padx=(0, 8))
        ak.labeled_combo(top, "Letter", self.kind, ["Response to reviewers", "Cover letter", "Submission checklist"], 20, self.build).pack(side="left", padx=(0, 8))
        ak.labeled_entry(top, "Your name", self.author, 18).pack(side="left", padx=(0, 8))
        ak.labeled_entry(top, "Editor", self.editor, 14).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Build", style="Accent.TButton", command=self.build).pack(side="left", anchor="s")
        frame, self.text = ak.make_text(self, app.colors, height=20)
        frame.pack(fill="both", expand=True, pady=6)
        row = ttk.Frame(self)
        row.pack(fill="x")
        ttk.Button(row, text="Copy", command=self.copy).pack(side="left")
        ttk.Button(row, text="Save as text", command=self.save).pack(side="left", padx=6)
        self.warn = ttk.Label(row, text="", style="Muted.TLabel")
        self.warn.pack(side="left", padx=8)
        self.map = {}

    def build(self):
        s = self.app.store
        sub = self.map.get(self.sub.get())
        if sub is None:
            ak.set_text(self.text, "Add a submission first.")
            return
        m = s.get("manuscript", sub["manuscript_id"])
        j = s.get("journal", sub["journal_id"])
        kind = self.kind.get()
        self.warn.configure(text="")
        if kind == "Response to reviewers":
            cs = s.list("comment", "submission_id=?", (sub["id"],))
            ak.set_text(self.text, dk.response_letter(m["title"], j["name"], cs, self.author.get(), self.editor.get()))
            p = dk.review_progress(cs)
            left = p["total"] - p["done"]
            if left or p["no_text"]:
                self.warn.configure(text="%d comment(s) still to do, %d without a response" % (left, p["no_text"]))
        elif kind == "Cover letter":
            ak.set_text(self.text, dk.cover_letter(m["title"], j["name"], m["kind"], m["summary"], self.author.get(), self.editor.get()))
        else:
            ak.set_text(self.text, "\n".join("[ ] " + c for c in dk.checklist(m)) + "\n")

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(ak.get_text(self.text))
        self.app.status("Copied")

    def save(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".txt", initialfile="letter.txt")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(ak.get_text(self.text))
            self.app.status("Saved " + path)

    def refresh(self):
        s = self.app.store
        self.map = {}
        for x in s.list("submission"):
            self.map["%s > %s, round %s" % (ak.short(s.label("manuscript", x["manuscript_id"]), 30), s.label("journal", x["journal_id"]), x["round"] or 1)] = x
        self.box.box.configure(values=list(self.map))
        if self.sub.get() not in self.map and self.map:
            best = next((k for k, v in self.map.items() if v["decision"] in dk.REVISE), next(iter(self.map)))
            self.sub.set(best)
        self.build()


class APP(ak.BaseApp):
    APP_NAME, ACCENT = "Journal Submission Desk", "#b45309"
    SCHEMA, SAMPLE = SCHEMA, staticmethod(sample)
    VIEWS = [Desk, Manuscripts, Journals, Submissions, Reviews, Letters, ak.DataView]


def main(argv=None):
    return ak.main(APP, argv)
