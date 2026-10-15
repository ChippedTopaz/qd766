import copy
import unittest
from datetime import datetime,timezone
from sqlalchemy import select,func,event
from qd766.backend.source_monitor_labels import describe_changes,alert_summary
from qd766.backend.source_monitor import structure_profile,observe_profile
from qd766.backend.models import SourceMonitorAlert,SourceMonitorBaseline,AdminAudit
from test_source_monitor import metric_data,MonitorDatabaseFixture
import test_trial_admin


class SourceLabelTests(MonitorDatabaseFixture,unittest.TestCase):
    def test_captured_names_group_and_parameter_do_not_change_detection(self):
        raw=metric_data();old=structure_profile(raw);raw['overview']['metrics'][0]['maxScore']=8
        with self.factory.begin() as db:
            item=observe_profile(db,'label',structure_profile(raw),{'rootId':'x','periodType':'month','group':'handling-satisfaction'},seed=old)
            self.assertEqual(item.details['changeCount'],1)
            change=item.details['changes'][0]
            self.assertEqual(change['field'],'root/metric:A:maxScore')
            self.assertEqual(change['before'],['6']);self.assertEqual(change['after'],['8'])
            self.assertEqual(change['display']['groupName'],'Mức độ hài lòng')
            self.assertEqual(change['display']['indicatorName'],'Chỉ tiêu A')
            self.assertEqual(change['display']['parameterName'],'Điểm tối đa của chỉ tiêu')
        with self.factory.begin() as db:
            self.assertIsNone(observe_profile(db,'label',structure_profile(raw),{'rootId':'x','periodType':'month','group':'handling-satisfaction'}))
            self.assertEqual(db.scalar(select(func.count()).select_from(SourceMonitorAlert)),1)

    def test_deleted_added_renamed_indicator_and_unknown_field(self):
        changes=[{'field':'root/metric:NEW:name','before':None,'after':['Tên mới'],'change':'added'},
            {'field':'root/metric:NEW','before':None,'after':[True],'change':'added'},
            {'field':'root/metric:OLD:name','before':['Tên cũ'],'after':None,'change':'removed'},
            {'field':'root/metric:OLD:maxScore','before':['3'],'after':None,'change':'removed'},
            {'field':'root/futureField','before':None,'after':['x'],'change':'added'}]
        before=copy.deepcopy(changes)
        labelled=describe_changes(changes,[{'group':'dossier-digitized'}])
        self.assertEqual(changes,before,'Presentation does not mutate evidence')
        self.assertEqual(labelled[1]['display']['indicatorName'],'Tên mới')
        self.assertEqual(labelled[3]['display']['indicatorName'],'Tên cũ')
        self.assertIn('chưa có tên',labelled[4]['display']['parameterName'])
        self.assertEqual(labelled[4]['display']['sourcePath'],'root/futureField')

    def test_group_total_national_and_closed_period_are_not_metric_scores(self):
        changes=describe_changes([{'field':'root/totalMaxScore','before':['18'],'after':['20']}],[{'group':'transparency'}])
        self.assertEqual(changes[0]['display']['parameterName'],'Điểm tối đa của nhóm')
        closed=describe_changes([{'field':'province/TTTT','before':'7.2','after':'7.4'}],province_names={'province':'Tỉnh mẫu'})
        self.assertEqual(closed[0]['display']['groupName'],'Thanh toán trực tuyến')
        self.assertEqual(closed[0]['display']['indicatorName'],'Điểm nhóm chỉ tiêu')
        self.assertEqual(closed[0]['display']['entityName'],'Tỉnh mẫu')
        national=describe_changes([{'field':'root/groupCodes','before':[['CKMB']],'after':[['CKMB','NEW']]}])
        self.assertEqual(national[0]['display']['parameterName'],'Danh sách nhóm chỉ tiêu')

    def test_preserve_captured_name_when_newer_profile_changes_it(self):
        change={'field':'root/metric:A:maxScore','display':{'groupName':'Nhóm cũ','indicatorName':'Tên lúc phát hiện','parameterName':'Điểm tối đa'}}
        self.assertEqual(describe_changes([change],profiles=[{'root/metric:A:name':['Tên hôm nay']}])[0]['display']['indicatorName'],'Tên lúc phát hiện')
        self.assertEqual(alert_summary({'changes':[change]})['groups'],['Nhóm cũ'])


class SourceLabelApiTests(unittest.TestCase):
    def setUp(self):
        self.f=test_trial_admin.TrialAdminTests();self.f.setUp()
        with self.f.app.state.session_factory.begin() as db:
            baseline=structure_profile(metric_data())
            db.add(SourceMonitorBaseline(key='province:month:handling-satisfaction',profile=baseline,fingerprint='x'))
            row=SourceMonitorAlert(kind='structure',title='Max score changed',dedupe_key='labels',details={'changeCount':1,
                'contexts':[{'rootId':'province','periodType':'month','group':'handling-satisfaction'}],
                'changes':[{'field':'root/metric:A:maxScore','before':['6'],'after':['8'],'change':'changed'}]})
            db.add(row);db.flush();self.identifier=str(row.id)

    def tearDown(self):self.f.tearDown()

    def test_old_alert_names_enriched_on_read_without_writes(self):
        sql=[];engine=self.f.app.state.engine;listener=lambda *a:sql.append(a[2]);event.listen(engine,'before_cursor_execute',listener)
        try:
            page=self.f.client.get('/api/v1/admin/source-monitor').json()
            self.assertEqual(page['items'][0]['groups'],['Mức độ hài lòng'])
            self.assertEqual(page['items'][0]['subjects'][0]['indicatorName'],'Chỉ tiêu A')
            self.assertNotIn('details',page['items'][0])
            row=self.f.client.get('/api/v1/admin/source-monitor/'+self.identifier).json()
            display=row['details']['changes'][0]['display']
            self.assertEqual(display['metricCode'],'A');self.assertEqual(display['parameterName'],'Điểm tối đa của chỉ tiêu')
            self.assertFalse(any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')) for s in sql))
        finally:event.remove(engine,'before_cursor_execute',listener)
        with self.f.app.state.session_factory() as db:
            item=db.scalar(select(SourceMonitorAlert))
            self.assertNotIn('display',item.details['changes'][0]);self.assertEqual(db.scalar(select(func.count()).select_from(AdminAudit)),0)
