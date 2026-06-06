#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成示例数据
"""

import os
import random
from datetime import date, timedelta

from models import init_db, get_session, Supplier, Qualification, PerformanceRecord, QualityIssue, Transaction
from config import UPLOAD_DIR


def generate_sample_data():
    print('正在生成示例数据...')
    init_db()
    db = get_session()

    existing_count = db.query(Supplier).count()

    industries = ['电子信息', '制造业', '高新技术', '服务业', '贸易']
    company_names = [
        '宏达电子科技有限公司', '鑫源精密制造有限公司', '天瑞环保材料有限公司',
        '恒通物流有限公司', '创新软件开发有限公司', '联合包装材料有限公司',
        '鼎盛机械制造有限公司', '华安检测技术有限公司', '盛世化工有限公司',
        '科达电气设备有限公司', '远洋医疗器械有限公司', '恒信办公用品有限公司',
        '绿源农产品有限公司', '智联网络科技有限公司', '通达建筑材料有限公司'
    ]

    levels = ['S', 'A', 'B', 'C']
    statuses = ['approved', 'approved', 'approved', 'approved', 'pending']

    suppliers = []
    for i, name in enumerate(company_names):
        supplier = Supplier(
            supplier_code=f'SAM{date.today().strftime("%Y%m%d")}{existing_count + i + 1:04d}',
            supplier_name=name,
            contact_person=f'联系人{i+1}',
            contact_phone=f'138{random.randint(10000000, 99999999)}',
            contact_email=f'contact{i+1}@example.com',
            address=f'北京市海淀区中关村大街{i+1}号',
            industry=random.choice(industries),
            registered_capital=random.choice([1000000, 5000000, 10000000, 50000000, 100000000]),
            establishment_date=date(2010 + i % 10, (i % 12) + 1, (i % 28) + 1),
            status=random.choice(statuses),
            level=random.choice(levels) if random.choice(statuses) == 'approved' else None,
            total_score=round(random.uniform(60, 98), 2),
            quality_score=round(random.uniform(60, 100), 2),
            environmental_score=round(random.uniform(60, 100), 2),
            financial_score=round(random.uniform(60, 100), 2),
            admission_date=date.today() - timedelta(days=random.randint(30, 365)),
            last_review_date=date.today() - timedelta(days=random.randint(0, 30)),
            next_review_date=date.today() + timedelta(days=random.randint(0, 365)),
            is_active=True
        )
        db.add(supplier)
        suppliers.append(supplier)
    db.flush()

    qual_types = ['ISO9001', 'ISO14001', 'ISO45001', 'BusinessLicense', 'Financial']
    for supplier in suppliers:
        for j, qual_type in enumerate(qual_types):
            qual = Qualification(
                supplier_id=supplier.id,
                qual_type=qual_type,
                cert_number=f'CERT{supplier.id:04d}{j:02d}',
                issue_date=date.today() - timedelta(days=random.randint(30, 365)),
                expiry_date=date.today() + timedelta(days=random.randint(30, 1095)),
                issuing_authority=random.choice(['中国质量认证中心', '国家环保认证中心', '市场监督管理局', '会计师事务所']),
                file_path=os.path.join(UPLOAD_DIR, f'{supplier.supplier_code}_{qual_type}.pdf'),
                ocr_result='{"success": true}',
                is_verified=random.choice([True, True, True, False])
            )
            db.add(qual)
    db.flush()

    for supplier in suppliers:
        for m in range(12):
            perf = PerformanceRecord(
                supplier_id=supplier.id,
                record_year=date.today().year,
                record_month=m + 1,
                on_time_rate=round(random.uniform(85, 99), 2),
                quality_pass_rate=round(random.uniform(88, 99.5), 2),
                response_time_hours=round(random.uniform(1, 12), 2),
                total_orders=random.randint(5, 50),
                total_amount=round(random.uniform(50000, 500000), 2),
                complaint_count=random.randint(0, 3)
            )
            db.add(perf)
    db.flush()

    for supplier in suppliers[:5]:
        for k in range(random.randint(0, 3)):
            issue = QualityIssue(
                supplier_id=supplier.id,
                issue_date=date.today() - timedelta(days=random.randint(1, 180)),
                issue_type=random.choice(['产品质量不合格', '交货延迟', '包装破损', '规格不符']),
                severity=random.choice(['normal', 'normal', 'major']),
                description=f'批次产品出现{random.choice(["外观瑕疵", "性能不达标", "尺寸偏差"])}问题',
                affected_orders=f'PO{random.randint(1000, 9999)}',
                is_resolved=random.choice([True, True, False])
            )
            db.add(issue)
    db.flush()

    for supplier in suppliers:
        for t in range(10):
            trans = Transaction(
                supplier_id=supplier.id,
                transaction_date=date.today() - timedelta(days=random.randint(1, 180)),
                order_number=f'PO{date.today().strftime("%Y%m%d")}{t:04d}',
                product_name=f'产品{random.choice(["A", "B", "C", "D"])}型号{t+1}',
                quantity=random.randint(10, 1000),
                unit_price=round(random.uniform(10, 1000), 2),
                total_amount=round(random.uniform(1000, 100000), 2),
                is_on_time=random.choice([True, True, True, False]),
                quality_grade=random.choice(['优秀', '良好', '合格', '合格'])
            )
            db.add(trans)

    db.commit()
    print(f'生成完成: {len(suppliers)} 家供应商')
    print(f'  - 资质证书: {len(suppliers) * 5} 份')
    print(f'  - 绩效记录: {len(suppliers) * 12} 条')
    print(f'  - 质量问题: {db.query(QualityIssue).count()} 条')
    print(f'  - 交易记录: {db.query(Transaction).count()} 条')
    db.close()


if __name__ == '__main__':
    generate_sample_data()
