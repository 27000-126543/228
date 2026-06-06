import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Session

from models import (
    Supplier, PerformanceRecord, QualityIssue, Transaction,
    LevelChange, Qualification, OperationLog, get_session
)
from config import REPORT_DIR, EXPORT_DIR

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.graphics.shapes import Drawing, Line
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class ReportGenerator:
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or get_session()

    def generate_monthly_reports(self):
        today = date.today()
        last_month = today.replace(day=1) - timedelta(days=1)
        year = last_month.year
        month = last_month.month

        suppliers = self.db.query(Supplier).filter(
            Supplier.status == 'approved',
            Supplier.is_active == True
        ).all()

        for supplier in suppliers:
            self.generate_supplier_profile(supplier.id, year, month)
            print(f'[报告] 生成供应商画像报告: {supplier.supplier_name}')

    def generate_supplier_profile(self, supplier_id: int, year: int = None, month: int = None) -> Dict:
        supplier = self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            return {'success': False, 'error': '供应商不存在'}

        if not year:
            year = date.today().year
        if not month:
            month = date.today().month

        profile_data = self._collect_profile_data(supplier, year, month)

        pdf_path = self._generate_pdf_report(supplier, profile_data, year, month)
        excel_path = self._generate_excel_report(supplier, profile_data, year, month)

        return {
            'success': True,
            'supplier_name': supplier.supplier_name,
            'pdf_path': pdf_path,
            'excel_path': excel_path,
            'profile_data': profile_data
        }

    def _collect_profile_data(self, supplier: Supplier, year: int, month: int) -> Dict:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        performance = self.db.query(PerformanceRecord).filter(
            PerformanceRecord.supplier_id == supplier.id,
            (PerformanceRecord.record_year < year) | 
            ((PerformanceRecord.record_year == year) & (PerformanceRecord.record_month <= month))
        ).order_by(PerformanceRecord.record_year, PerformanceRecord.record_month).all()

        issues = self.db.query(QualityIssue).filter(
            QualityIssue.supplier_id == supplier.id,
            QualityIssue.issue_date <= end_date
        ).order_by(QualityIssue.issue_date.desc()).all()

        transactions = self.db.query(Transaction).filter(
            Transaction.supplier_id == supplier.id,
            Transaction.transaction_date >= date(year, 1, 1),
            Transaction.transaction_date <= end_date
        ).all()

        level_changes = self.db.query(LevelChange).filter(
            LevelChange.supplier_id == supplier.id
        ).order_by(LevelChange.created_at.desc()).all()

        qualifications = self.db.query(Qualification).filter(
            Qualification.supplier_id == supplier.id
        ).all()

        total_transaction = sum(t.total_amount or 0 for t in transactions)
        avg_on_time = (sum(p.on_time_rate or 0 for p in performance[-12:]) / len(performance[-12:])) if performance[-12:] else 0
        avg_quality = (sum(p.quality_pass_rate or 0 for p in performance[-12:]) / len(performance[-12:])) if performance[-12:] else 0
        avg_response = (sum(p.response_time_hours or 0 for p in performance[-12:]) / len(performance[-12:])) if performance[-12:] else 0

        score_trend = []
        for p in performance[-12:]:
            score = (p.on_time_rate or 0) * 0.4 + (p.quality_pass_rate or 0) * 0.4 + max(0, 100 - (p.response_time_hours or 24) * 4) * 0.2
            score_trend.append({
                'month': f'{p.record_year}-{p.record_month:02d}',
                'score': round(score, 2)
            })

        return {
            'basic_info': {
                'code': supplier.supplier_code,
                'name': supplier.supplier_name,
                'level': supplier.level,
                'status': supplier.status,
                'total_score': supplier.total_score,
                'contact_person': supplier.contact_person,
                'contact_phone': supplier.contact_phone,
                'industry': supplier.industry,
                'admission_date': supplier.admission_date
            },
            'scores': {
                'total': supplier.total_score,
                'quality': supplier.quality_score,
                'environmental': supplier.environmental_score,
                'financial': supplier.financial_score
            },
            'performance': {
                'avg_on_time_rate': round(avg_on_time, 2),
                'avg_quality_pass_rate': round(avg_quality, 2),
                'avg_response_time': round(avg_response, 2),
                'total_transaction_amount': total_transaction,
                'transaction_count': len(transactions)
            },
            'quality_issues': {
                'total_count': len(issues),
                'major_count': sum(1 for i in issues if i.severity == 'major'),
                'unresolved_count': sum(1 for i in issues if not i.is_resolved),
                'issues': [
                    {
                        'date': i.issue_date,
                        'type': i.issue_type,
                        'severity': i.severity,
                        'description': i.description,
                        'is_resolved': i.is_resolved
                    } for i in issues[:10]
                ]
            },
            'score_trend': score_trend,
            'qualifications': [
                {
                    'type': q.qual_type,
                    'cert_number': q.cert_number,
                    'expiry_date': q.expiry_date,
                    'is_verified': q.is_verified
                } for q in qualifications
            ],
            'level_history': [
                {
                    'date': lc.created_at,
                    'old_level': lc.old_level,
                    'new_level': lc.new_level,
                    'change_type': lc.change_type,
                    'reason': lc.reason
                } for lc in level_changes
            ]
        }

    def _generate_pdf_report(self, supplier: Supplier, data: Dict, year: int, month: int) -> Optional[str]:
        if not REPORTLAB_AVAILABLE:
            return None

        report_dir = os.path.join(REPORT_DIR, str(year), f'{month:02d}')
        os.makedirs(report_dir, exist_ok=True)
        pdf_path = os.path.join(report_dir, f'{supplier.supplier_code}_画像报告_{year}{month:02d}.pdf')

        doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, spaceAfter=20)
        story.append(Paragraph(f'供应商画像报告', title_style))
        story.append(Paragraph(f'{supplier.supplier_name} ({year}年{month}月)', styles['Heading2']))
        story.append(Spacer(1, 0.5*cm))

        basic_data = [
            ['供应商编码', data['basic_info']['code'], '供应商等级', data['basic_info']['level']],
            ['所属行业', data['basic_info']['industry'], '准入日期', str(data['basic_info']['admission_date'])],
            ['联系人', data['basic_info']['contact_person'], '联系电话', data['basic_info']['contact_phone']],
            ['综合评分', str(data['scores']['total']), '状态', data['basic_info']['status']]
        ]
        basic_table = Table(basic_data, colWidths=[3*cm, 4*cm, 3*cm, 4*cm])
        basic_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(Paragraph('一、基本信息', styles['Heading3']))
        story.append(basic_table)
        story.append(Spacer(1, 0.5*cm))

        score_data = [
            ['评分维度', '得分', '权重'],
            ['质量体系', f"{data['scores']['quality']:.2f}", '35%'],
            ['环保资质', f"{data['scores']['environmental']:.2f}", '25%'],
            ['财务状况', f"{data['scores']['financial']:.2f}", '40%'],
            ['综合评分', f"{data['scores']['total']:.2f}", '100%']
        ]
        score_table = Table(score_data, colWidths=[4*cm, 4*cm, 3*cm])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (-1, -1), (-1, -1), colors.lightgreen),
            ('FONTNAME', (-1, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(Paragraph('二、评分详情', styles['Heading3']))
        story.append(score_table)
        story.append(Spacer(1, 0.5*cm))

        perf_data = [
            ['绩效指标', '数值'],
            ['平均准时率', f"{data['performance']['avg_on_time_rate']:.2f}%"],
            ['平均合格率', f"{data['performance']['avg_quality_pass_rate']:.2f}%"],
            ['平均响应时效', f"{data['performance']['avg_response_time']:.2f}小时"],
            ['年度交易额', f"¥{data['performance']['total_transaction_amount']:,.2f}"],
            ['交易次数', str(data['performance']['transaction_count'])]
        ]
        perf_table = Table(perf_data, colWidths=[5*cm, 6*cm])
        perf_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(Paragraph('三、绩效表现（近12个月）', styles['Heading3']))
        story.append(perf_table)
        story.append(Spacer(1, 0.5*cm))

        issue_data = [['日期', '类型', '严重程度', '状态']]
        for issue in data['quality_issues']['issues'][:5]:
            issue_data.append([
                str(issue['date']),
                issue['type'] or '',
                issue['severity'],
                '已解决' if issue['is_resolved'] else '未解决'
            ])
        if len(issue_data) == 1:
            issue_data.append(['无', '无', '无', '无'])
        issue_table = Table(issue_data, colWidths=[2.5*cm, 3*cm, 2.5*cm, 2.5*cm])
        issue_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(Paragraph(f'四、质量问题 (总计: {data["quality_issues"]["total_count"]}个, 重大: {data["quality_issues"]["major_count"]}个)', styles['Heading3']))
        story.append(issue_table)
        story.append(Spacer(1, 0.5*cm))

        story.append(Paragraph(f'报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', styles['Normal']))

        doc.build(story)
        return pdf_path

    def _generate_excel_report(self, supplier: Supplier, data: Dict, year: int, month: int) -> str:
        report_dir = os.path.join(EXPORT_DIR, str(year), f'{month:02d}')
        os.makedirs(report_dir, exist_ok=True)
        excel_path = os.path.join(report_dir, f'{supplier.supplier_code}_画像报告_{year}{month:02d}.xlsx')

        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            basic_df = pd.DataFrame([
                {'项目': '供应商编码', '值': data['basic_info']['code']},
                {'项目': '供应商名称', '值': data['basic_info']['name']},
                {'项目': '供应商等级', '值': data['basic_info']['level']},
                {'项目': '所属行业', '值': data['basic_info']['industry']},
                {'项目': '准入日期', '值': str(data['basic_info']['admission_date'])},
                {'项目': '联系人', '值': data['basic_info']['contact_person']},
                {'项目': '联系电话', '值': data['basic_info']['contact_phone']},
                {'项目': '综合评分', '值': data['scores']['total']},
                {'项目': '状态', '值': data['basic_info']['status']}
            ])
            basic_df.to_excel(writer, sheet_name='基本信息', index=False)

            score_df = pd.DataFrame([
                {'评分维度': '质量体系', '得分': data['scores']['quality'], '权重': '35%'},
                {'评分维度': '环保资质', '得分': data['scores']['environmental'], '权重': '25%'},
                {'评分维度': '财务状况', '得分': data['scores']['financial'], '权重': '40%'},
                {'评分维度': '综合评分', '得分': data['scores']['total'], '权重': '100%'}
            ])
            score_df.to_excel(writer, sheet_name='评分详情', index=False)

            perf_df = pd.DataFrame([
                {'绩效指标': '平均准时率', '数值': f"{data['performance']['avg_on_time_rate']:.2f}%"},
                {'绩效指标': '平均合格率', '数值': f"{data['performance']['avg_quality_pass_rate']:.2f}%"},
                {'绩效指标': '平均响应时效', '数值': f"{data['performance']['avg_response_time']:.2f}小时"},
                {'绩效指标': '年度交易额', '数值': f"¥{data['performance']['total_transaction_amount']:,.2f}"},
                {'绩效指标': '交易次数', '数值': data['performance']['transaction_count']}
            ])
            perf_df.to_excel(writer, sheet_name='绩效表现', index=False)

            if data['quality_issues']['issues']:
                issue_df = pd.DataFrame(data['quality_issues']['issues'])
                issue_df.to_excel(writer, sheet_name='质量问题', index=False)

            if data['score_trend']:
                trend_df = pd.DataFrame(data['score_trend'])
                trend_df.to_excel(writer, sheet_name='评分趋势', index=False)

            if data['qualifications']:
                qual_df = pd.DataFrame(data['qualifications'])
                qual_df.to_excel(writer, sheet_name='资质证书', index=False)

        return excel_path

    def batch_export_suppliers(self, supplier_ids: List[int], export_format: str = 'excel') -> Dict:
        export_data = []
        for sid in supplier_ids:
            supplier = self.db.query(Supplier).filter(Supplier.id == sid).first()
            if supplier:
                export_data.append({
                    '供应商编码': supplier.supplier_code,
                    '供应商名称': supplier.supplier_name,
                    '等级': supplier.level,
                    '状态': supplier.status,
                    '综合评分': supplier.total_score,
                    '质量评分': supplier.quality_score,
                    '环保评分': supplier.environmental_score,
                    '财务评分': supplier.financial_score,
                    '行业': supplier.industry,
                    '联系人': supplier.contact_person,
                    '联系电话': supplier.contact_phone,
                    '准入日期': supplier.admission_date,
                    '最后评估日期': supplier.last_review_date
                })

        if not export_data:
            return {'success': False, 'error': '没有可导出的数据'}

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_path = os.path.join(EXPORT_DIR, f'供应商批量导出_{timestamp}.xlsx')
        os.makedirs(EXPORT_DIR, exist_ok=True)

        df = pd.DataFrame(export_data)
        df.to_excel(export_path, index=False)

        return {
            'success': True,
            'export_path': export_path,
            'count': len(export_data)
        }

    def get_operation_logs(self, start_date: date = None, end_date: date = None, 
                          operator: str = None, operation_type: str = None,
                          target_type: str = None) -> List[Dict]:
        query = self.db.query(OperationLog)

        if start_date:
            query = query.filter(OperationLog.created_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(OperationLog.created_at <= datetime.combine(end_date, datetime.max.time()))
        if operator:
            query = query.filter(OperationLog.operator.like(f'%{operator}%'))
        if operation_type:
            query = query.filter(OperationLog.operation_type == operation_type)
        if target_type:
            query = query.filter(OperationLog.target_type == target_type)

        logs = query.order_by(OperationLog.created_at.desc()).all()
        return [
            {
                'id': log.id,
                'operator': log.operator,
                'operation_type': log.operation_type,
                'target_type': log.target_type,
                'target_id': log.target_id,
                'description': log.description,
                'created_at': log.created_at
            } for log in logs
        ]

    def commit(self):
        self.db.commit()

    def close(self):
        self.db.close()
