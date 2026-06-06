#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
供应商管理系统 Web API
"""

import os
import json
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename

from models import init_db, get_session, Supplier, Qualification, Task, LevelChange, PerformanceRecord, QualityIssue, OperationLog
from supplier_manager import SupplierManager
from task_manager import TaskManager
from report_generator import ReportGenerator
from config import UPLOAD_DIR, REPORT_DIR, EXPORT_DIR, THRESHOLDS

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024


@app.context_processor
def inject_request():
    from flask import request
    return dict(request=request)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'txt'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    return get_session()


@app.template_filter('strftime')
def strftime_filter(value, format='%Y-%m-%d'):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return value.strftime(format)


@app.route('/')
def index():
    return redirect(url_for('supplier_list'))


@app.route('/suppliers')
def supplier_list():
    return render_template('supplier_list.html')


@app.route('/api/suppliers')
def api_supplier_list():
    db = get_db()
    name = request.args.get('name', '')
    level = request.args.get('level', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    sm = SupplierManager(db)
    results = sm.search_suppliers(
        name=name or None,
        level=level or None,
        status=status or None,
        start_date=datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None,
        end_date=datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
    )
    db.close()
    return jsonify({'success': True, 'data': results})


@app.route('/supplier/<int:supplier_id>')
def supplier_detail(supplier_id):
    return render_template('supplier_detail.html', supplier_id=supplier_id)


@app.route('/api/supplier/<int:supplier_id>')
def api_supplier_detail(supplier_id):
    db = get_db()
    sm = SupplierManager(db)
    profile = sm.get_supplier_profile(supplier_id)
    db.close()
    return jsonify(profile)


@app.route('/api/supplier/<int:supplier_id>/performance')
def api_supplier_performance(supplier_id):
    db = get_db()
    records = db.query(PerformanceRecord).filter(
        PerformanceRecord.supplier_id == supplier_id
    ).order_by(PerformanceRecord.record_year, PerformanceRecord.record_month).all()

    data = []
    for r in records:
        data.append({
            'id': r.id,
            'year': r.record_year,
            'month': r.record_month,
            'on_time_rate': r.on_time_rate,
            'quality_pass_rate': r.quality_pass_rate,
            'response_time_hours': r.response_time_hours,
            'total_orders': r.total_orders,
            'total_amount': r.total_amount,
            'complaint_count': r.complaint_count
        })
    db.close()
    return jsonify({'success': True, 'data': data})


@app.route('/api/supplier/<int:supplier_id>/quality_issues')
def api_supplier_quality_issues(supplier_id):
    db = get_db()
    issues = db.query(QualityIssue).filter(
        QualityIssue.supplier_id == supplier_id
    ).order_by(QualityIssue.issue_date.desc()).all()

    data = []
    for i in issues:
        data.append({
            'id': i.id,
            'issue_date': str(i.issue_date),
            'issue_type': i.issue_type,
            'severity': i.severity,
            'description': i.description,
            'affected_orders': i.affected_orders,
            'is_resolved': i.is_resolved,
            'resolution_date': str(i.resolution_date) if i.resolution_date else None
        })
    db.close()
    return jsonify({'success': True, 'data': data})


@app.route('/api/supplier/<int:supplier_id>/logs')
def api_supplier_logs(supplier_id):
    db = get_db()
    logs = db.query(OperationLog).filter(
        OperationLog.target_type == 'supplier',
        OperationLog.target_id == supplier_id
    ).order_by(OperationLog.created_at.desc()).all()

    data = []
    for log in logs:
        data.append({
            'id': log.id,
            'operator': log.operator,
            'operation_type': log.operation_type,
            'description': log.description,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    db.close()
    return jsonify({'success': True, 'data': data})


@app.route('/review')
def review_page():
    return render_template('review.html')


@app.route('/api/pending_suppliers')
def api_pending_suppliers():
    db = get_db()
    suppliers = db.query(Supplier).filter(
        Supplier.status == 'pending'
    ).order_by(Supplier.created_at.desc()).all()

    data = []
    for s in suppliers:
        quals = db.query(Qualification).filter(Qualification.supplier_id == s.id).all()
        data.append({
            'id': s.id,
            'code': s.supplier_code,
            'name': s.supplier_name,
            'industry': s.industry,
            'contact_person': s.contact_person,
            'contact_phone': s.contact_phone,
            'qual_count': len(quals),
            'verified_count': sum(1 for q in quals if q.is_verified),
            'created_at': s.created_at.strftime('%Y-%m-%d %H:%M')
        })
    db.close()
    return jsonify({'success': True, 'data': data})


@app.route('/api/supplier/<int:supplier_id>/qualifications')
def api_supplier_qualifications(supplier_id):
    db = get_db()
    quals = db.query(Qualification).filter(
        Qualification.supplier_id == supplier_id
    ).order_by(Qualification.created_at.desc()).all()

    data = []
    for q in quals:
        try:
            ocr_data = json.loads(q.ocr_result) if q.ocr_result else {}
        except:
            ocr_data = {}
        data.append({
            'id': q.id,
            'qual_type': q.qual_type,
            'cert_number': q.cert_number,
            'issue_date': str(q.issue_date) if q.issue_date else None,
            'expiry_date': str(q.expiry_date) if q.expiry_date else None,
            'issuing_authority': q.issuing_authority,
            'is_verified': q.is_verified,
            'verification_note': q.verification_note,
            'file_path': q.file_path,
            'ocr_result': ocr_data,
            'created_at': q.created_at.strftime('%Y-%m-%d %H:%M')
        })
    db.close()
    return jsonify({'success': True, 'data': data})


@app.route('/api/upload_qualification', methods=['POST'])
def api_upload_qualification():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未选择文件'})
    file = request.files['file']
    supplier_id = request.form.get('supplier_id', type=int)
    qual_type = request.form.get('qual_type', 'Other')

    if not supplier_id:
        return jsonify({'success': False, 'error': '缺少供应商ID'})

    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'})

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f'{supplier_id}_{timestamp}_{filename}'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        db = get_db()
        sm = SupplierManager(db)
        result = sm.upload_qualification(supplier_id, qual_type, filepath)
        sm.commit()
        db.close()
        return jsonify(result)

    return jsonify({'success': False, 'error': '不支持的文件格式'})


@app.route('/api/review/<int:supplier_id>', methods=['POST'])
def api_review_supplier(supplier_id):
    db = get_db()
    sm = SupplierManager(db)
    result = sm.review_admission(supplier_id)
    sm.commit()
    db.close()
    return jsonify(result)


@app.route('/tasks')
def tasks_page():
    return render_template('tasks.html')


@app.route('/api/tasks/reminders')
def api_reminder_tasks():
    db = get_db()
    tasks = db.query(Task).filter(
        Task.task_type == 'document_reminder',
        Task.status == 'pending'
    ).order_by(Task.created_at.desc()).all()

    data = []
    for t in tasks:
        supplier = db.query(Supplier).filter(Supplier.id == t.supplier_id).first()
        data.append({
            'id': t.id,
            'supplier_id': t.supplier_id,
            'supplier_name': supplier.supplier_name if supplier else '',
            'title': t.title,
            'description': t.description,
            'priority': t.priority,
            'due_date': str(t.due_date) if t.due_date else None,
            'reminder_count': t.reminder_count,
            'last_reminder_date': str(t.last_reminder_date) if t.last_reminder_date else None,
            'created_at': t.created_at.strftime('%Y-%m-%d %H:%M')
        })
    db.close()
    return jsonify({'success': True, 'data': data})


@app.route('/api/tasks/approvals')
def api_approval_tasks():
    db = get_db()
    tm = TaskManager(db)
    pending = tm.get_pending_approvals()
    db.close()
    return jsonify({'success': True, 'data': pending})


@app.route('/api/approve_level_change/<int:level_change_id>', methods=['POST'])
def api_approve_level_change(level_change_id):
    db = get_db()
    tm = TaskManager(db)
    approver = request.form.get('approver', '系统管理员')
    result = tm.approve_level_change(level_change_id, approver)
    tm.commit()
    db.close()
    return jsonify(result)


@app.route('/reports')
def reports_page():
    return render_template('reports.html')


@app.route('/api/reports')
def api_reports_list():
    reports = []
    if os.path.exists(REPORT_DIR):
        for year in sorted(os.listdir(REPORT_DIR), reverse=True):
            year_path = os.path.join(REPORT_DIR, year)
            if os.path.isdir(year_path):
                for month in sorted(os.listdir(year_path), reverse=True):
                    month_path = os.path.join(year_path, month)
                    if os.path.isdir(month_path):
                        for filename in os.listdir(month_path):
                            if filename.endswith('.pdf'):
                                filepath = os.path.join(month_path, filename)
                                excel_path = filepath.replace('.pdf', '.xlsx').replace('reports', 'exports')
                                reports.append({
                                    'filename': filename,
                                    'year': year,
                                    'month': month,
                                    'supplier_code': filename.split('_')[0] if '_' in filename else '',
                                    'pdf_path': filepath,
                                    'excel_path': excel_path if os.path.exists(excel_path) else None,
                                    'size': os.path.getsize(filepath) // 1024,
                                    'created': datetime.fromtimestamp(os.path.getctime(filepath)).strftime('%Y-%m-%d %H:%M')
                                })
    return jsonify({'success': True, 'data': reports[:100]})


@app.route('/api/download_report')
def api_download_report():
    filepath = request.args.get('path', '')
    if not filepath or not os.path.exists(filepath):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    return send_file(filepath, as_attachment=True)


@app.route('/api/export_suppliers', methods=['POST'])
def api_export_suppliers():
    data = request.get_json()
    supplier_ids = data.get('ids', []) if data else []

    db = get_db()
    rg = ReportGenerator(db)
    result = rg.batch_export_suppliers(supplier_ids)
    rg.commit()
    db.close()

    if result['success'] and os.path.exists(result['export_path']):
        return send_file(result['export_path'], as_attachment=True)
    return jsonify(result)


@app.route('/api/supplier/create', methods=['POST'])
def api_create_supplier():
    data = request.get_json()
    db = get_db()
    sm = SupplierManager(db)
    try:
        supplier_data = {
            'supplier_name': data['supplier_name'],
            'contact_person': data.get('contact_person'),
            'contact_phone': data.get('contact_phone'),
            'contact_email': data.get('contact_email'),
            'address': data.get('address'),
            'industry': data.get('industry'),
            'registered_capital': float(data.get('registered_capital', 0)) if data.get('registered_capital') else None,
            'establishment_date': datetime.strptime(data['establishment_date'], '%Y-%m-%d').date() if data.get('establishment_date') else None
        }
        supplier = sm.create_supplier(supplier_data)
        sm.commit()
        result = {'success': True, 'supplier_id': supplier.id, 'supplier_code': supplier.supplier_code}
    except Exception as e:
        result = {'success': False, 'error': str(e)}
    db.close()
    return jsonify(result)


@app.route('/api/generate_report/<int:supplier_id>')
def api_generate_report(supplier_id):
    db = get_db()
    rg = ReportGenerator(db)
    result = rg.generate_supplier_profile(supplier_id)
    rg.commit()
    db.close()
    return jsonify(result)


@app.route('/api/daily_tasks', methods=['POST'])
def api_daily_tasks():
    db = get_db()
    tm = TaskManager(db)
    tm.process_daily_tasks()
    tm.commit()
    db.close()
    return jsonify({'success': True, 'message': '每日任务执行完成'})


if __name__ == '__main__':
    init_db()
    print('供应商管理系统 Web 服务启动中...')
    print('访问地址: http://127.0.0.1:5000')
    app.run(debug=True, host='0.0.0.0', port=5000)
