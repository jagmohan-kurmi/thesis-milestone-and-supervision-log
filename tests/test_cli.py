import tempfile, unittest
from pathlib import Path
from thesis_milestone_and_supervision_log.cli import add_milestone,add_action,add_meeting,connect,report,set_status,LogError

class ThesisTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.db=connect(Path(self.tmp.name)/"test.sqlite")
 def tearDown(self): self.db.close(); self.tmp.cleanup()
 def test_overdue_boundary_and_completion(self):
  mid=add_milestone(self.db,"Proposal","2026-11-19")
  aid=add_action(self.db,"Revise chapter","Student","2026-11-18")
  r=report(self.db,"2026-11-19")
  self.assertTrue(r["milestones"][0]["overdue"] is False) # due today is not overdue
  self.assertTrue(r["actions"][0]["overdue"])
  set_status(self.db,mid,"done")
  self.assertFalse(report(self.db,"2026-11-20")["milestones"][0]["overdue"])
 def test_dependencies_and_meeting(self):
  first=add_milestone(self.db,"Ethics","2027-01-01")
  second=add_milestone(self.db,"Fieldwork","2027-02-01","planned","",[first])
  meeting=add_meeting(self.db,"2026-11-19","Student, supervisor","Agree scope")
  add_action(self.db,"Submit ethics","Student","2026-12-01",meeting)
  r=report(self.db,"2026-11-19")
  self.assertEqual([first],r["milestones"][1]["dependencies"])
  self.assertEqual(1,len(r["meetings"]))
 def test_malformed_dates_and_self_dependency(self):
  with self.assertRaises(LogError): add_milestone(self.db,"Bad","2026-02-30")
  mid=add_milestone(self.db,"A","2027-01-01")
  with self.assertRaises(Exception): add_milestone(self.db,"B","2027-01-02","planned","",[999])
  with self.assertRaises(LogError): set_status(self.db,mid,"unknown")
if __name__=="__main__": unittest.main()
