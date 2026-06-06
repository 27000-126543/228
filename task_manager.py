import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from models import (
    Task, Supplier, QualityIssue, PerformanceRecord,
    LevelChange, Transaction, SupplierAlternative, OperationLog, get_session
)
from scoring_engine import ScoringEngine
from config import THRESHOLDS, QUALITY_ISSUE_THRESHOLD


class TaskManager:
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or get_session()
        self.scoring_engine = ScoringEngine()

    def process_daily_tasks(self):
        self._process_reminders()
        self._process_abandoned_tasks()
        self._check_quality_issues()
        self._check_yearly_reviews()

    def _process_reminders(self):
        pending_tasks = self.db.query(Task).filter(
            Task.status == 'pending',
            Task.task_type == 'document_reminder'
        ).all()

        for task in pending_tasks:
            days_since_last = (date.today() - task.last_reminder_date).days if task.last_reminder_date else 999
            if days_since_last >= THRESHOLDS['reminder_interval_days']:
                task.reminder_count += 1
                task.last_reminder_date = date.today()
                self._send_reminder(task)
                print(f'[提醒] 发送第{task.reminder_count}次提醒: {task.title}')

        self.db.flush()

    def _process_abandoned_tasks(self):
        expired_tasks = self.db.query(Task).filter(
            Task.status == 'pending',
            Task.due_date < date.today()
        ).all()

        for task in expired_tasks:
            days_overdue = (date.today() - task.due_date).days
            if days_overdue >= 0:
                supplier = self.db.query(Supplier).filter(Supplier.id == task.supplier_id).first()
                if supplier and supplier.status == 'pending':
                    supplier.status = 'abandoned'
                    task.status = 'cancelled'
                    print(f'[放弃] 供应商{supplier.supplier_name}超期未补齐资料，标记为放弃')

                    self._log_operation(
                        operator='system',
                        operation_type='abandon',
                        target_type='supplier',
                        target_id=supplier.id,
                        description=f'供应商超期未补齐资料，自动标记为放弃'
                    )

        self.db.flush()

    def _send_reminder(self, task: Task):
        supplier = self.db.query(Supplier).filter(Supplier.id == task.supplier_id).first()
        if supplier and supplier.contact_email:
            print(f'[邮件] 发送催办提醒给 {supplier.contact_email}')
            print(f'  主题: 资质文件补充提醒 (第{task.reminder_count}次)')
            print(f'  内容: {task.description}')

    def _check_quality_issues(self):
        approved_suppliers = self.db.query(Supplier).filter(
            Supplier.status == 'approved',
            Supplier.is_active == True
        ).all()

        for supplier in approved_suppliers:
            recent_major_issues = self.db.query(QualityIssue).filter(
                QualityIssue.supplier_id == supplier.id,
                QualityIssue.severity == 'major',
                QualityIssue.issue_date >= date.today() - timedelta(days=365)
            ).order_by(QualityIssue.issue_date.desc()).limit(QUALITY_ISSUE_THRESHOLD).all()

            if len(recent_major_issues) >= QUALITY_ISSUE_THRESHOLD:
                self._suspend_supplier(supplier, recent_major_issues)

    def _suspend_supplier(self, supplier: Supplier, issues: List):
        supplier.is_active = False
        supplier.status = 'suspended'

        self._notify_in_transit_orders(supplier)
        alternatives = self._generate_alternatives(supplier)

        print(f'[暂停] 供应商{supplier.supplier_name}因连续重大质量问题被暂停合作')
        print(f'  涉及重大问题数量: {len(issues)}')
        print(f'  推荐替代供应商: {len(alternatives)}家')

        self._log_operation(
            operator='system',
            operation_type='suspend',
            target_type='supplier',
            target_id=supplier.id,
            description=f'因连续{len(issues)}次重大质量问题，自动暂停合作'
        )

        self.db.flush()

    def _notify_in_transit_orders(self, supplier: Supplier):
        print(f'  [通知] 通知所有在途采购订单负责人: {supplier.supplier_name}')
        in_transit_orders = self.db.query(Transaction).filter(
            Transaction.supplier_id == supplier.id,
            Transaction.transaction_date >= date.today() - timedelta(days=30)
        ).all()
        print(f'  涉及在途订单: {len(in_transit_orders)}笔')

    def _generate_alternatives(self, supplier: Supplier) -> List:
        alternatives = self.db.query(Supplier).filter(
            Supplier.id != supplier.id,
            Supplier.status == 'approved',
            Supplier.is_active == True,
            Supplier.industry == supplier.industry,
            Supplier.level.in_(['S', 'A'])
        ).limit(5).all()

        result = []
        for alt in alternatives:
            match_score = 0
            if alt.level == 'S':
                match_score += 50
            elif alt.level == 'A':
                match_score += 40
            if alt.industry == supplier.industry:
                match_score += 30
            if alt.total_score and supplier.total_score:
                score_diff = abs(alt.total_score - supplier.total_score)
                match_score += max(0, 20 - score_diff // 5)

            alternative = SupplierAlternative(
                original_supplier_id=supplier.id,
                alternative_supplier_id=alt.id,
                match_score=match_score,
                recommendation_reason=f'同行业{alt.level}级供应商，综合评分{alt.total_score}'
            )
            self.db.add(alternative)
            result.append({
                'supplier_id': alt.id,
                'name': alt.supplier_name,
                'level': alt.level,
                'match_score': match_score
            })

        self.db.flush()
        return result

    def _check_yearly_reviews(self):
        due_reviews = self.db.query(Supplier).filter(
            Supplier.status == 'approved',
            Supplier.is_active == True,
            Supplier.next_review_date <= date.today()
        ).all()

        for supplier in due_reviews:
            self._perform_yearly_review(supplier)

    def _perform_yearly_review(self, supplier: Supplier):
        qualifications = supplier.qualifications
        quality_issues = supplier.quality_issues
        performance_records = supplier.performance_records

        if not performance_records:
            performance_records = self._simulate_performance_data(supplier)

        review_result = self.scoring_engine.calculate_yearly_review_score(
            supplier, qualifications, quality_issues, performance_records
        )

        new_level, _ = self.scoring_engine.determine_level(review_result['total_score'])
        old_level_score = self.scoring_engine.get_level_score(supplier.level)
        score_drop_ratio = (old_level_score - review_result['total_score']) / old_level_score if old_level_score > 0 else 0

        if score_drop_ratio >= THRESHOLDS['downgrade_trigger']:
            level_change = LevelChange(
                supplier_id=supplier.id,
                old_level=supplier.level,
                new_level=new_level,
                change_type='downgrade',
                reason=f'年度再评估得分下降{score_drop_ratio*100:.1f}%，触发降级建议',
                score_before=supplier.total_score,
                score_after=review_result['total_score'],
                status='pending'
            )
            self.db.add(level_change)
            print(f'[降级建议] 供应商{supplier.supplier_name}得分下降{score_drop_ratio*100:.1f}%，建议从{supplier.level}降级到{new_level}')
        else:
            if new_level != supplier.level:
                level_change = LevelChange(
                    supplier_id=supplier.id,
                    old_level=supplier.level,
                    new_level=new_level,
                    change_type='adjust',
                    reason='年度再评估等级调整',
                    score_before=supplier.total_score,
                    score_after=review_result['total_score'],
                    status='approved',
                    approval_date=date.today()
                )
                self.db.add(level_change)
                supplier.level = new_level

        supplier.total_score = review_result['total_score']
        supplier.last_review_date = date.today()
        supplier.next_review_date = date(date.today().year + 1, date.today().month, date.today().day)

        self._log_operation(
            operator='system',
            operation_type='yearly_review',
            target_type='supplier',
            target_id=supplier.id,
            description=f'年度再评估完成，得分: {review_result["total_score"]}',
            old_value=str(supplier.total_score),
            new_value=str(review_result['total_score'])
        )

        self.db.flush()

    def _simulate_performance_data(self, supplier: Supplier) -> List:
        records = []
        for i in range(12):
            month = date.today().month - i
            year = date.today().year
            if month <= 0:
                month += 12
                year -= 1

            record = PerformanceRecord(
                supplier_id=supplier.id,
                record_year=year,
                record_month=month,
                on_time_rate=90 + (hash(f'{supplier.id}{year}{month}') % 10),
                quality_pass_rate=92 + (hash(f'{supplier.id}{year}{month}q') % 8),
                response_time_hours=2 + (hash(f'{supplier.id}{year}{month}r') % 6),
                total_orders=10 + (hash(f'{supplier.id}{year}{month}o') % 20),
                total_amount=100000 + (hash(f'{supplier.id}{year}{month}a') % 500000)
            )
            self.db.add(record)
            records.append(record)

        self.db.flush()
        return records

    def approve_level_change(self, level_change_id: int, approver: str) -> Dict:
        level_change = self.db.query(LevelChange).filter(LevelChange.id == level_change_id).first()
        if not level_change:
            return {'success': False, 'error': '等级变更记录不存在'}

        supplier = self.db.query(Supplier).filter(Supplier.id == level_change.supplier_id).first()
        if not supplier:
            return {'success': False, 'error': '供应商不存在'}

        level_change.status = 'approved'
        level_change.approver = approver
        level_change.approval_date = date.today()

        supplier.level = level_change.new_level
        supplier.total_score = level_change.score_after

        print(f'[审批通过] 供应商{supplier.supplier_name}等级从{level_change.old_level}调整为{level_change.new_level}')

        self._log_operation(
            operator=approver,
            operation_type='approve',
            target_type='level_change',
            target_id=level_change_id,
            description=f'审批通过等级变更: {level_change.old_level} -> {level_change.new_level}'
        )

        self.db.flush()
        return {'success': True, 'message': '审批通过'}

    def get_pending_approvals(self) -> List[Dict]:
        pending = self.db.query(LevelChange).filter(LevelChange.status == 'pending').all()
        return [
            {
                'id': lc.id,
                'supplier_id': lc.supplier_id,
                'supplier_name': self.db.query(Supplier).filter(Supplier.id == lc.supplier_id).first().supplier_name if self.db.query(Supplier).filter(Supplier.id == lc.supplier_id).first() else '',
                'old_level': lc.old_level,
                'new_level': lc.new_level,
                'change_type': lc.change_type,
                'reason': lc.reason,
                'score_before': lc.score_before,
                'score_after': lc.score_after,
                'created_at': lc.created_at
            } for lc in pending
        ]

    def _log_operation(self, operator: str, operation_type: str, target_type: str,
                       target_id: int, description: str, old_value: str = None, 
                       new_value: str = None, ip_address: str = None):
        log = OperationLog(
            operator=operator,
            operation_type=operation_type,
            target_type=target_type,
            target_id=target_id,
            description=description,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address
        )
        self.db.add(log)

    def commit(self):
        self.db.commit()

    def close(self):
        self.db.close()
