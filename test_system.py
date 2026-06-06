#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统功能测试
"""

from models import get_session, Supplier
from report_generator import ReportGenerator
from supplier_manager import SupplierManager


def test_query():
    print('=' * 60)
    print('测试: 供应商查询')
    print('=' * 60)

    db = get_session()
    count = db.query(Supplier).count()
    print(f'总供应商数: {count}')

    sm = SupplierManager(db)
    results = sm.search_suppliers(status='approved')
    print(f'已通过审核: {len(results)} 家')
    for s in results[:5]:
        print(f"  - {s['name']} (等级: {s['level']}, 得分: {s['total_score']})")

    return sm, [s['id'] for s in results]


def test_batch_export(sm, supplier_ids):
    print('\n' + '=' * 60)
    print('测试: 批量导出')
    print('=' * 60)

    rg = ReportGenerator(sm.db)
    result = rg.batch_export_suppliers(supplier_ids)
    print(f'批量导出结果: {result["success"]}')
    if result['success']:
        print(f'导出文件: {result["export_path"]}')
        print(f'导出数量: {result["count"]} 家')


def test_logs(sm):
    print('\n' + '=' * 60)
    print('测试: 操作日志')
    print('=' * 60)

    rg = ReportGenerator(sm.db)
    logs = rg.get_operation_logs()
    print(f'操作日志总数: {len(logs)}')
    for log in logs[:5]:
        print(f"  [{log['created_at'].strftime('%Y-%m-%d %H:%M')}] {log['operator']} - {log['description']}")


def test_daily_tasks(sm):
    print('\n' + '=' * 60)
    print('测试: 每日任务')
    print('=' * 60)

    from task_manager import TaskManager
    tm = TaskManager(sm.db)
    tm.process_daily_tasks()
    tm.commit()
    print('每日任务执行完成')


def main():
    sm, ids = test_query()
    if ids:
        test_batch_export(sm, ids)
    test_logs(sm)
    test_daily_tasks(sm)
    sm.close()
    print('\n所有测试完成！')


if __name__ == '__main__':
    main()
