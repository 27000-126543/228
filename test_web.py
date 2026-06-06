#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Web应用
"""

from models import init_db, get_session, Supplier
init_db()
db = get_session()
count = db.query(Supplier).count()
print(f'数据库正常，供应商总数: {count}')

from app import app
print('Flask应用初始化成功')
print('\n页面路由:')
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    if not rule.rule.startswith('/static') and not rule.rule.startswith('/api/'):
        methods = rule.methods - {'OPTIONS', 'HEAD'}
        print(f'  {methods} {rule.rule}')

print('\nAPI路由:')
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    if rule.rule.startswith('/api/'):
        methods = rule.methods - {'OPTIONS', 'HEAD'}
        print(f'  {methods} {rule.rule}')

db.close()
print('\n✅ Web应用测试通过！')
