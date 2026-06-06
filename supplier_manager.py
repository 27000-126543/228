import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from models import Supplier, Qualification, Task, LevelChange, OperationLog, get_session
from ocr_engine import OCREngine, QualificationVerifier
from scoring_engine import ScoringEngine
from config import THRESHOLDS, UPLOAD_DIR


class SupplierManager:
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or get_session()
        self.ocr_engine = OCREngine()
        self.verifier = QualificationVerifier()
        self.scoring_engine = ScoringEngine()

    def generate_supplier_code(self) -> str:
        count = self.db.query(Supplier).count()
        return f'SUP{datetime.now().strftime("%Y%m%d")}{count + 1:04d}'

    def create_supplier(self, supplier_data: Dict) -> Supplier:
        supplier_code = supplier_data.get('supplier_code') or self.generate_supplier_code()
        supplier = Supplier(
            supplier_code=supplier_code,
            supplier_name=supplier_data['supplier_name'],
            contact_person=supplier_data.get('contact_person'),
            contact_phone=supplier_data.get('contact_phone'),
            contact_email=supplier_data.get('contact_email'),
            address=supplier_data.get('address'),
            industry=supplier_data.get('industry'),
            registered_capital=supplier_data.get('registered_capital'),
            establishment_date=supplier_data.get('establishment_date'),
            status='pending'
        )
        self.db.add(supplier)
        self.db.flush()

        self._log_operation(
            operator='system',
            operation_type='create',
            target_type='supplier',
            target_id=supplier.id,
            description=f'创建供应商档案: {supplier.supplier_name}'
        )

        return supplier

    def upload_qualification(self, supplier_id: int, qual_type: str, file_path: str) -> Dict:
        supplier = self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            return {'success': False, 'error': '供应商不存在'}

        ocr_result = self.ocr_engine.recognize_file(file_path)
        if not ocr_result.get('success'):
            return {'success': False, 'error': ocr_result.get('error', 'OCR识别失败')}

        extracted_data = ocr_result.get('extracted_data', {})
        is_valid, verification_note, verify_score = self.verifier.verify(
            ocr_result.get('qual_type', qual_type),
            extracted_data
        )

        qualification = Qualification(
            supplier_id=supplier_id,
            qual_type=ocr_result.get('qual_type', qual_type),
            cert_number=extracted_data.get('cert_number'),
            issue_date=extracted_data.get('issue_date'),
            expiry_date=extracted_data.get('expiry_date'),
            issuing_authority=extracted_data.get('issuing_authority'),
            file_path=file_path,
            ocr_result=json.dumps(ocr_result, ensure_ascii=False, default=str),
            is_verified=is_valid,
            verification_note=verification_note
        )
        self.db.add(qualification)
        self.db.flush()

        self._log_operation(
            operator='system',
            operation_type='upload',
            target_type='qualification',
            target_id=qualification.id,
            description=f'上传资质文件: {qualification.qual_type}'
        )

        return {
            'success': True,
            'qualification_id': qualification.id,
            'is_verified': is_valid,
            'verification_note': verification_note,
            'verify_score': verify_score
        }

    def review_admission(self, supplier_id: int) -> Dict:
        supplier = self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            return {'success': False, 'error': '供应商不存在'}

        qualifications = self.db.query(Qualification).filter(Qualification.supplier_id == supplier_id).all()
        quality_issues = []

        missing_docs = self._check_missing_documents(supplier, qualifications)
        if missing_docs:
            task = self._create_reminder_task(supplier_id, missing_docs)
            return {
                'success': True,
                'action': 'pending_docs',
                'missing_documents': missing_docs,
                'task_id': task.id,
                'message': '资料不全，已生成催办任务'
            }

        scores = self.scoring_engine.calculate_admission_score(supplier, qualifications, quality_issues)
        level, level_desc = self.scoring_engine.determine_level(scores['total_score'])

        supplier.quality_score = scores['quality_score']
        supplier.environmental_score = scores['environmental_score']
        supplier.financial_score = scores['financial_score']
        supplier.total_score = scores['total_score']

        if scores['total_score'] < THRESHOLDS['pass_score']:
            supplier.status = 'rejected'
            self._send_rejection_email(supplier, scores)
            action = 'rejected'
            message = '评分低于阈值，申请已退回'
        else:
            supplier.status = 'approved'
            supplier.level = level
            supplier.admission_date = date.today()
            supplier.last_review_date = date.today()
            supplier.next_review_date = date(date.today().year + 1, date.today().month, date.today().day)
            action = 'approved'
            message = f'审核通过，等级: {level} ({level_desc})'

            level_change = LevelChange(
                supplier_id=supplier_id,
                old_level=None,
                new_level=level,
                change_type='admission',
                reason='准入审核通过',
                score_before=None,
                score_after=scores['total_score'],
                status='approved',
                approval_date=date.today()
            )
            self.db.add(level_change)

        self.db.flush()

        self._log_operation(
            operator='system',
            operation_type='review',
            target_type='supplier',
            target_id=supplier.id,
            description=f'准入审核结果: {action}, 得分: {scores["total_score"]}',
            old_value=None,
            new_value=json.dumps(scores, ensure_ascii=False)
        )

        return {
            'success': True,
            'action': action,
            'scores': scores,
            'level': level,
            'level_description': level_desc,
            'message': message
        }

    def _check_missing_documents(self, supplier: Supplier, qualifications: List) -> List[str]:
        missing = []
        qual_types = {q.qual_type for q in qualifications if q.is_verified}

        if 'ISO9001' not in qual_types:
            missing.append('ISO9001质量管理体系认证')
        if 'ISO14001' not in qual_types:
            missing.append('ISO14001环境管理体系认证')
        if 'BusinessLicense' not in qual_types:
            missing.append('营业执照')
        if 'Financial' not in qual_types:
            missing.append('年度财务审计报告')

        return missing

    def _create_reminder_task(self, supplier_id: int, missing_docs: List[str]) -> Task:
        due_date = date.today() + timedelta(days=THRESHOLDS['abandon_days'])
        task = Task(
            supplier_id=supplier_id,
            task_type='document_reminder',
            title='补充资质文件提醒',
            description=f'请补充以下文件: {"; ".join(missing_docs)}',
            status='pending',
            priority='high',
            due_date=due_date,
            last_reminder_date=date.today(),
            reminder_count=1
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _send_rejection_email(self, supplier: Supplier, scores: Dict):
        print(f'[邮件] 发送拒信给 {supplier.contact_email}')
        print(f'  主题: 供应商准入申请结果通知')
        print(f'  内容: 感谢贵司申请成为我司供应商。经综合评估，暂未达到我司准入标准。')
        print(f'  综合得分: {scores["total_score"]}, 最低要求: {THRESHOLDS["pass_score"]}')

    def get_supplier_profile(self, supplier_id: int) -> Dict:
        supplier = self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            return {'success': False, 'error': '供应商不存在'}

        qualifications = self.db.query(Qualification).filter(Qualification.supplier_id == supplier_id).all()
        tasks = self.db.query(Task).filter(Task.supplier_id == supplier_id).order_by(Task.created_at.desc()).all()
        level_changes = self.db.query(LevelChange).filter(LevelChange.supplier_id == supplier_id).order_by(LevelChange.created_at.desc()).all()

        return {
            'success': True,
            'supplier': {
                'id': supplier.id,
                'code': supplier.supplier_code,
                'name': supplier.supplier_name,
                'status': supplier.status,
                'level': supplier.level,
                'total_score': supplier.total_score,
                'quality_score': supplier.quality_score,
                'environmental_score': supplier.environmental_score,
                'financial_score': supplier.financial_score,
                'contact_person': supplier.contact_person,
                'contact_phone': supplier.contact_phone,
                'contact_email': supplier.contact_email,
                'address': supplier.address,
                'industry': supplier.industry,
                'registered_capital': supplier.registered_capital,
                'establishment_date': supplier.establishment_date,
                'admission_date': supplier.admission_date,
                'last_review_date': supplier.last_review_date,
                'next_review_date': supplier.next_review_date
            },
            'qualifications': [
                {
                    'id': q.id,
                    'type': q.qual_type,
                    'cert_number': q.cert_number,
                    'expiry_date': q.expiry_date,
                    'is_verified': q.is_verified
                } for q in qualifications
            ],
            'tasks': [
                {
                    'id': t.id,
                    'title': t.title,
                    'status': t.status,
                    'priority': t.priority,
                    'due_date': t.due_date
                } for t in tasks
            ],
            'level_changes': [
                {
                    'id': lc.id,
                    'old_level': lc.old_level,
                    'new_level': lc.new_level,
                    'change_type': lc.change_type,
                    'status': lc.status,
                    'approval_date': lc.approval_date
                } for lc in level_changes
            ]
        }

    def search_suppliers(self, name: str = None, level: str = None, 
                         status: str = None, start_date: date = None, 
                         end_date: date = None) -> List[Dict]:
        query = self.db.query(Supplier)

        if name:
            query = query.filter(Supplier.supplier_name.like(f'%{name}%'))
        if level:
            query = query.filter(Supplier.level == level)
        if status:
            query = query.filter(Supplier.status == status)
        if start_date:
            query = query.filter(Supplier.admission_date >= start_date)
        if end_date:
            query = query.filter(Supplier.admission_date <= end_date)

        suppliers = query.order_by(Supplier.created_at.desc()).all()

        return [
            {
                'id': s.id,
                'code': s.supplier_code,
                'name': s.supplier_name,
                'level': s.level,
                'status': s.status,
                'total_score': s.total_score,
                'industry': s.industry,
                'admission_date': s.admission_date
            } for s in suppliers
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
