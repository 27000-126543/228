#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
供应商准入与绩效自动化管理系统
"""

import os
import sys
import time
import schedule
from datetime import datetime, date, timedelta

from models import init_db, get_session, Supplier, QualityIssue
from supplier_manager import SupplierManager
from task_manager import TaskManager
from report_generator import ReportGenerator
from config import SCHEDULE_CONFIG


class SupplierManagementSystem:
    def __init__(self):
        self.supplier_manager = SupplierManager()
        self.task_manager = TaskManager()
        self.report_generator = ReportGenerator()
        print('=' * 60)
        print('供应商准入与绩效自动化管理系统 已启动')
        print('=' * 60)

    def run_daily_job(self):
        print(f'\n[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 执行每日任务...')
        self.task_manager.process_daily_tasks()
        self.task_manager.commit()
        print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 每日任务执行完成')

    def run_monthly_report_job(self):
        if date.today().day == SCHEDULE_CONFIG['monthly_report_day']:
            print(f'\n[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 生成月度供应商画像报告...')
            self.report_generator.generate_monthly_reports()
            self.report_generator.commit()
            print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 月度报告生成完成')

    def start_scheduler(self):
        schedule.every().day.at(SCHEDULE_CONFIG['daily_check_time']).do(self.run_daily_job)
        schedule.every().day.at(SCHEDULE_CONFIG['daily_check_time']).do(self.run_monthly_report_job)

        print(f'\n调度系统已启动，每日 {SCHEDULE_CONFIG["daily_check_time"]} 执行任务')
        print('按 Ctrl+C 停止系统\n')

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            print('\n系统正在停止...')
            self.close()
            print('系统已停止')

    def demo_supplier_admission(self):
        print('\n' + '=' * 60)
        print('演示: 供应商准入流程')
        print('=' * 60)

        supplier_data = {
            'supplier_name': '示例电子科技有限公司',
            'contact_person': '张三',
            'contact_phone': '13800138000',
            'contact_email': 'zhangsan@example.com',
            'address': '北京市海淀区中关村大街1号',
            'industry': '电子信息',
            'registered_capital': 50000000,
            'establishment_date': date(2015, 6, 15)
        }

        supplier = self.supplier_manager.create_supplier(supplier_data)
        print(f'\n1. 创建供应商档案: {supplier.supplier_name} (编码: {supplier.supplier_code})')

        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        qual_files = [
            ('ISO9001', 'ISO9001_质量体系认证.pdf'),
            ('ISO14001', 'ISO14001_环境体系认证.pdf'),
            ('ISO45001', 'ISO45001_职业健康认证.pdf'),
            ('BusinessLicense', '营业执照.pdf'),
            ('Financial', '年度财务审计报告.pdf')
        ]

        for qual_type, filename in qual_files:
            file_path = os.path.join(upload_dir, filename)
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f'模拟文件 - {qual_type}')

            result = self.supplier_manager.upload_qualification(supplier.id, qual_type, file_path)
            if result['success']:
                print(f"2. 上传资质: {qual_type} - {'审核通过' if result['is_verified'] else '待审核'}")

        print('\n3. 执行准入审核...')
        review_result = self.supplier_manager.review_admission(supplier.id)
        if review_result['success']:
            print(f"   结果: {review_result['message']}")
            print(f"   综合得分: {review_result['scores']['total_score']}")
            if review_result.get('level'):
                print(f"   等级: {review_result['level']} - {review_result['level_description']}")

        self.supplier_manager.commit()
        print(f'\n供应商ID: {supplier.id}')
        return supplier.id

    def demo_quality_issue(self, supplier_id: int):
        print('\n' + '=' * 60)
        print('演示: 重大质量问题处理')
        print('=' * 60)

        db = get_session()
        supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if supplier:
            for i in range(2):
                issue = QualityIssue(
                    supplier_id=supplier_id,
                    issue_date=date.today() - timedelta(days=30 * i),
                    issue_type='产品质量不合格',
                    severity='major',
                    description=f'批次产品检测不合格，退货率超标准',
                    affected_orders=f'PO20250{i+1:03d}'
                )
                db.add(issue)
                print(f'记录重大质量问题 {i+1}: {issue.description}')
            db.commit()
            print('\n触发质量问题检测...')
            self.task_manager._check_quality_issues()
            self.task_manager.commit()
        db.close()

    def demo_report_generation(self, supplier_id: int):
        print('\n' + '=' * 60)
        print('演示: 供应商画像报告生成')
        print('=' * 60)

        result = self.report_generator.generate_supplier_profile(supplier_id)
        if result['success']:
            print(f"\n报告生成完成:")
            print(f"  供应商: {result['supplier_name']}")
            if result.get('pdf_path'):
                print(f"  PDF报告: {result['pdf_path']}")
            print(f"  Excel报告: {result['excel_path']}")
        self.report_generator.commit()

    def demo_query_and_export(self):
        print('\n' + '=' * 60)
        print('演示: 供应商查询与批量导出')
        print('=' * 60)

        results = self.supplier_manager.search_suppliers(status='approved')
        print(f'\n查询到 {len(results)} 家已通过审核的供应商:')
        for s in results[:5]:
            print(f"  - {s['name']} (等级: {s['level']}, 得分: {s['total_score']})")

        if results:
            export_ids = [s['id'] for s in results]
            export_result = self.report_generator.batch_export_suppliers(export_ids)
            if export_result['success']:
                print(f"\n批量导出完成: {export_result['export_path']}")
                print(f"  导出数量: {export_result['count']} 家")

        logs = self.report_generator.get_operation_logs(operation_type='create')
        print(f'\n最近操作日志 (创建类): {len(logs)} 条')
        for log in logs[:3]:
            print(f"  [{log['created_at'].strftime('%Y-%m-%d %H:%M')}] {log['operator']} - {log['description']}")

    def demo_approval_workflow(self):
        print('\n' + '=' * 60)
        print('演示: 等级变更审批流程')
        print('=' * 60)

        pending = self.task_manager.get_pending_approvals()
        print(f'\n待审批的等级变更: {len(pending)} 条')
        for p in pending:
            print(f"  ID: {p['id']}, 供应商: {p['supplier_name']}, {p['old_level']} -> {p['new_level']}")
            print(f"    原因: {p['reason']}")

        if pending:
            result = self.task_manager.approve_level_change(pending[0]['id'], '审批人-李四')
            print(f"\n审批结果: {result['message']}")
            self.task_manager.commit()

    def close(self):
        self.supplier_manager.close()
        self.task_manager.close()
        self.report_generator.close()


def print_menu():
    print('\n' + '=' * 60)
    print('供应商准入与绩效自动化管理系统')
    print('=' * 60)
    print('1. 运行完整演示流程')
    print('2. 启动定时调度服务')
    print('3. 手动执行每日任务')
    print('4. 手动生成月度报告')
    print('5. 查询供应商')
    print('6. 查看操作日志')
    print('0. 退出系统')
    print('=' * 60)


def main():
    print('正在初始化数据库...')
    init_db()
    print('数据库初始化完成\n')

    system = SupplierManagementSystem()

    if len(sys.argv) > 1:
        if sys.argv[1] == 'demo':
            supplier_id = system.demo_supplier_admission()
            system.demo_quality_issue(supplier_id)
            system.demo_report_generation(supplier_id)
            system.demo_query_and_export()
            system.demo_approval_workflow()
            system.close()
            print('\n演示完成！')
            return
        elif sys.argv[1] == 'scheduler':
            system.start_scheduler()
            return
        elif sys.argv[1] == 'daily':
            system.run_daily_job()
            system.close()
            return
        elif sys.argv[1] == 'report':
            system.run_monthly_report_job()
            system.close()
            return

    while True:
        print_menu()
        choice = input('请选择操作 (0-6): ').strip()

        if choice == '0':
            system.close()
            print('感谢使用，再见！')
            break
        elif choice == '1':
            supplier_id = system.demo_supplier_admission()
            system.demo_report_generation(supplier_id)
            system.demo_query_and_export()
        elif choice == '2':
            system.start_scheduler()
            break
        elif choice == '3':
            system.run_daily_job()
        elif choice == '4':
            system.report_generator.generate_monthly_reports()
            system.report_generator.commit()
            print('月度报告生成完成')
        elif choice == '5':
            name = input('供应商名称 (可选): ').strip()
            level = input('供应商等级 (可选): ').strip()
            status = input('状态 (可选): ').strip()
            results = system.supplier_manager.search_suppliers(
                name=name or None,
                level=level or None,
                status=status or None
            )
            print(f'\n查询到 {len(results)} 条记录:')
            for s in results:
                print(f"  {s['code']} - {s['name']} | 等级: {s['level']} | 状态: {s['status']} | 得分: {s['total_score']}")
        elif choice == '6':
            logs = system.report_generator.get_operation_logs()
            print(f'\n共 {len(logs)} 条操作日志:')
            for log in logs[:20]:
                print(f"  [{log['created_at'].strftime('%Y-%m-%d %H:%M')}] {log['operator']} | {log['operation_type']} | {log['description']}")
        else:
            print('无效选择，请重新输入')


if __name__ == '__main__':
    main()
